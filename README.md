# S3 Vectors 検索システム

AWS S3 Vectors と Amazon Bedrock を使用したセマンティック検索システムのテストです。マークダウンファイルを見出しごとにチャンク分割して埋め込みベクトル化し、意味的類似性による検索を実現します。

## 主な機能

- **マークダウン対応**: `## 見出し` ごとに自動チャンク分割
- **セマンティック検索**: Amazon Titan Embeddings v2 による意味検索
- **Streamlit UI**: 直感的なウェブインターフェース
- **AWS S3 Vectors**: 高速なベクトル検索基盤

## 事前準備

### 1. AWS 環境設定

#### S3 Vectors バケット作成

AWS マネジメントコンソールまたは CLI で以下を実行：

```bash
# S3 Vectors バケット作成
aws s3vectors create-vector-bucket --vector-bucket-name your-vector-bucket --region us-west-2

# インデックス作成（1024次元 for Titan Embeddings v2）
aws s3vectors create-index \
    --vector-bucket-name your-vector-bucket \
    --index-name your-vector-index \
    --index-configuration '{
        "algorithm": "COSINE",
        "dimensions": 1024,
        "metadataConfiguration": {
            "metadataKeys": ["heading", "timestamp", "chunk_index", "full_length"]
        }
    }' \
    --region us-west-2
```

#### Bedrock モデルアクセス許可

1. AWS マネジメントコンソール → Amazon Bedrock
2. 「Model access」→ 「Edit」
3. **Amazon Titan Embed Text v2** にアクセス許可

#### IAM 権限設定

実行ユーザーに以下の権限が必要：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3vectors:*", "bedrock:InvokeModel"],
      "Resource": "*"
    }
  ]
}
```

### 2. 環境変数設定

`.streamlit/secrets.toml` ファイルを作成：

```toml
[aws]
region = "us-west-2"
bucket_name = "your-vector-bucket"
index_name = "your-vector-index"

[bedrock]
embedding_model_id = "amazon.titan-embed-text-v2:0"
```

### 3. Python 環境構築

仮想環境での実行を推奨

```bash
# 依存関係インストール
pip install -r requirements.txt

# アプリケーション起動
streamlit run app.py
```

## アプリケーション使用方法

### マークダウン登録モード

1. **ファイルアップロード**: `.md` または `.txt` ファイルを選択
2. **内容をプレビュー**: チャンク分割結果を事前確認
3. **ベクトル登録**: 見出し（`## タイトル`）ごとに自動分割・登録

### テキスト直接登録モード

1. テキストエリアにマークダウンを直接入力
2. サンプルテキスト機能で動作確認可能
3. ベクトル登録で埋め込み生成・保存

### 検索モード

1. **クエリ入力**: 自然言語で検索内容を記述
2. **取得件数調整**: スライダーで結果数を選択（1-10 件）
3. **検索実行**: 類似度スコア・見出し・内容を表示

## 管理ユーティリティ

### ベクトル数確認

```bash
python vector_count.py
```

現在登録されているベクトル総数を表示します。

### データ完全削除

```bash
python delete_vector_bucket.py
```

⚠️ **警告**: バケット内の全インデックスとベクトルが完全削除されます。

## トラブルシューティング

### 想定エラー

**ValidationException: Malformed input request**

- AWS 認証情報を確認
- Bedrock モデルアクセス許可を確認

**Invalid record: Filterable metadata must have at most 2048 bytes**

- メタデータサイズ制限（2048 バイト）エラー
- 長すぎるテキストが自動で切り詰められます

**検索結果が表示されない**

- ベクトル登録が完了しているか確認
- クエリが適切な日本語・英語で記述されているか確認

### デバッグ情報

- 各モードでプレビュー機能を活用
- 検索結果で詳細メタデータを確認
- `vector_count.py` でデータ登録状況を把握

## プロジェクト構成

```
.
├── app.py                    # メインアプリケーション
├── delete_vector_bucket.py   # データ削除ユーティリティ
├── vector_count.py          # ベクトル数確認ユーティリティ
├── .streamlit/
│   └── secrets.toml         # AWS認証・設定情報
├── data/
│   └── sample_text.md       # サンプルマークダウン（オプション）
└── secrets.toml.template    # 設定テンプレート
```

## 技術仕様

- **埋め込みモデル**: Amazon Titan Embed Text v2 (1024 次元)
- **ベクトル検索**: AWS S3 Vectors (コサイン類似度)
- **チャンク分割**: マークダウン見出し基準（最大 1000 文字）
- **UI フレームワーク**: Streamlit
