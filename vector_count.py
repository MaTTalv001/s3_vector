# python vector_count.py を実行することでベクトル数をカウントができる

import boto3
import streamlit as st

def count_vectors_in_index(region, index_arn=None, bucket_name=None, index_name=None):
    """
    S3 Vectors インデックス内のベクトル数を取得します。

    index_arn を指定すれば優先的に使用し、
    指定がなければ bucket_name と index_name の組み合わせを使用します。
    """
    client = boto3.client("s3vectors", region_name=region)
    num_vectors = 0
    next_token = None

    while True:
        params = {
            "returnData": False,        # データ自体は取得不要なら False に
            "returnMetadata": False     # メタデータ取得不要なら False に
        }
        if index_arn:
            params["indexArn"] = index_arn
        else:
            params["vectorBucketName"] = bucket_name
            params["indexName"] = index_name

        if next_token:
            params["nextToken"] = next_token

        response = client.list_vectors(**params)

        vectors = response.get("vectors", [])
        num_vectors += len(vectors)

        next_token = response.get("nextToken")
        if not next_token:
            break

    return num_vectors

region = st.secrets["aws"]["region"]
bucket = st.secrets["aws"]["bucket_name"]
index = st.secrets["aws"]["index_name"]
total = count_vectors_in_index(region, bucket_name=bucket, index_name=index)
print(f"Total vectors in index: {total}")
