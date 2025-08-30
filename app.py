import streamlit as st
import boto3
import json
import uuid
from datetime import datetime
import numpy as np
import re

# ====== 設定の読み込み ======
try:
    AWS_REGION = st.secrets["aws"]["region"]
    BUCKET_NAME = st.secrets["aws"]["bucket_name"]
    INDEX_NAME = st.secrets["aws"]["index_name"]
    EMBEDDING_MODEL_ID = st.secrets["bedrock"]["embedding_model_id"]
except KeyError as e:
    st.error(f"❌ 設定が見つかりません: {e}")
    st.error("`.streamlit/secrets.toml`ファイルを確認してください")
    st.stop()

# ====== AWS クライアント ======
s3vectors = boto3.client("s3vectors", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# ====== TITAN埋め込み生成 ======
def generate_embedding(text: str):
    """Amazon Titan v2でテキストから埋め込み生成 (1024次元)"""
    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=json.dumps({"inputText": text}),
        accept="application/json",
        contentType="application/json"
    )
    return json.loads(response["body"].read())["embedding"]

# ====== queryVectorフォーマット ======
def fix_query_vector_format(embedding):
    """S3 Vectors用に float32 へ変換"""
    if isinstance(embedding, np.ndarray):
        embedding = embedding.astype(np.float32).tolist()
    return {"float32": [float(x) for x in embedding]}

# ====== マークダウンをチャンク分割 ======
def chunk_markdown_by_h2(text):
    """マークダウンテキストを ## 見出しごとにチャンク分割"""
    # ##で始まる行で分割
    chunks = re.split(r'\n(?=##\s)', text)
    
    processed_chunks = []
    for i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk:
            continue
            
        # チャンクが長すぎる場合は文字数で再分割
        max_chunk_size = 1000  # メタデータ制限を考慮
        if len(chunk) > max_chunk_size:
            # 段落単位で分割を試みる
            paragraphs = chunk.split('\n\n')
            current_chunk = ""
            
            for paragraph in paragraphs:
                if len(current_chunk + paragraph) > max_chunk_size and current_chunk:
                    processed_chunks.append(current_chunk.strip())
                    current_chunk = paragraph
                else:
                    current_chunk += "\n\n" + paragraph if current_chunk else paragraph
            
            if current_chunk.strip():
                processed_chunks.append(current_chunk.strip())
        else:
            processed_chunks.append(chunk)
    
    return processed_chunks

# ====== 見出しを抽出 ======
def extract_heading(chunk_text):
    """チャンクから見出し（##）を抽出"""
    lines = chunk_text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('## '):
            return line[3:].strip()  # "## "を除去
        elif line.startswith('##'):
            return line[2:].strip()   # "##"を除去
    return "見出しなし"

# ====== ベクトル登録 ======
def upload_markdown_as_vectors(text: str):
    """マークダウンテキストを分割し、各チャンクを埋め込み→S3 Vectorsに登録"""
    chunks = chunk_markdown_by_h2(text)
    
    vectors = []
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)
        
        # 見出しを抽出
        heading = extract_heading(chunk)
        
        # メタデータのテキストを制限（2048バイト制限対応）
        max_metadata_text = 400  # 見出し情報も含めるため少し小さく
        truncated_text = chunk[:max_metadata_text]
        if len(chunk) > max_metadata_text:
            truncated_text += "..."
        
        vectors.append({
            "key": f"{uuid.uuid4()}",
            "data": {"float32": embedding},
            "metadata": {
                "source_text": truncated_text,
                "heading": heading,
                "timestamp": datetime.now().isoformat(),
                "chunk_index": i,
                "full_length": len(chunk)
            }
        })

    s3vectors.put_vectors(
        vectorBucketName=BUCKET_NAME,
        indexName=INDEX_NAME,
        vectors=vectors
    )
    return len(vectors)

# ====== 検索 ======
def semantic_search(query: str, top_k=5):
    query_embedding = generate_embedding(query)
    query_vector = fix_query_vector_format(query_embedding)

    results = s3vectors.query_vectors(
        vectorBucketName=BUCKET_NAME,
        indexName=INDEX_NAME,
        queryVector=query_vector,
        topK=top_k,
        returnDistance=True,
        returnMetadata=True
    )

    # 類似度スコアに変換
    for v in results["vectors"]:
        v["similarity"] = 1.0 - v["distance"]
    return results["vectors"]

# ====== Streamlit UI ======
st.title("S3 Vectors マークダウン検索デモ")

# 設定情報を表示（デバッグ用）
st.sidebar.header("メニュー")
mode = st.sidebar.radio("操作を選んでください", ["マークダウン登録", "テキスト登録", "検索"])

if mode == "マークダウン登録":
    st.subheader("マークダウンファイルをアップロードして登録")
    uploaded_file = st.file_uploader("マークダウンファイルを選択", type=["md", "txt"])
    
    if uploaded_file is not None:
        # ファイル内容を読み込み
        text_content = uploaded_file.read().decode('utf-8')
        
        # プレビュー機能
        if st.button("内容をプレビュー"):
            st.write("### 📄 ファイル内容プレビュー")
            st.text(text_content[:1000])
            st.write(f"**総文字数:** {len(text_content)}")
            
            # チャンク分割プレビュー
            chunks = chunk_markdown_by_h2(text_content)
            st.write(f"**予想チャンク数:** {len(chunks)}")
            
            st.write("### 📋 チャンク見出しリスト")
            for i, chunk in enumerate(chunks[:10]):  # 最初の10個だけ表示
                heading = extract_heading(chunk)
                st.write(f"{i+1}. {heading}")
            if len(chunks) > 10:
                st.write(f"... および {len(chunks) - 10} 個の追加チャンク")
        
        if st.button("ベクトル登録"):
            if text_content.strip():
                n_chunks = upload_markdown_as_vectors(text_content)
                st.success(f"✅ {n_chunks} チャンクを登録しました")
            else:
                st.warning("⚠️ ファイル内容が空です")

elif mode == "テキスト登録":
    st.subheader("マークダウンテキストを直接入力")
    st.write("💡 `## 見出し` 形式で書くと、見出しごとにチャンク分割されます")

    # サンプルテキストをロード
    with open("data/sample_text.md", "r", encoding="utf-8") as f:
        sample_content = f.read()

    # サンプルを確認用に表示
    if st.button("サンプルを表示"):
        st.markdown(sample_content)

    # サンプルをフォームにセット
    if st.button("サンプルを使用"):
        st.session_state.markdown_input = sample_content

    # テキストエリア（フォーム本体）
    text_input = st.text_area(
        "マークダウンテキストを入力",
        value=st.session_state.get("markdown_input", ""),
        height=300
)

    
    if st.button("ベクトル登録"):
        if text_input.strip():
            n_chunks = upload_markdown_as_vectors(text_input.strip())
            st.success(f"✅ {n_chunks} チャンクを登録しました")
        else:
            st.warning("⚠️ 空のテキストは登録できません")

elif mode == "検索":
    st.subheader("検索")
    query = st.text_input("検索クエリを入力")
    top_k = st.slider("取得件数", 1, 10, 5)

    if st.button("検索実行"):
        if query.strip():
            results = semantic_search(query, top_k)
            st.write("### 🔍 検索結果")
            
            if not results:
                st.warning("⚠️ 検索結果が見つかりませんでした")
            else:
                for i, r in enumerate(results):
                    st.markdown(f"### 結果 {i+1}")
                    st.markdown(f"**スコア:** {r['similarity']:.4f}")
                    
                    # メタデータの詳細表示
                    metadata = r.get("metadata", {})
                    heading = metadata.get('heading', '見出しなし')
                    st.markdown(f"**📂 見出し:** {heading}")
                    st.write(f"**チャンク番号:** {metadata.get('chunk_index', 'N/A')}")
                    st.write(f"**登録日時:** {metadata.get('timestamp', 'N/A')}")
                    st.write(f"**元の長さ:** {metadata.get('full_length', 'N/A')}文字")
                    
                    # テキスト内容
                    source_text = metadata.get("source_text", "")
                    st.write("**内容:**")
                    st.markdown(source_text)
                    
                    st.caption(f"Key: {r['key']}")
                    st.divider()
        else:
            st.warning("⚠️ クエリを入力してください")