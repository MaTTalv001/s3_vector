# python delete_vector_bucket_final.pyを実行することでベクトルバケットを削除できる

import boto3
from botocore.exceptions import ClientError
import streamlit as st

def delete_vector_bucket(bucket_name, region_name="us-west-2"):
    s3vectors = boto3.client("s3vectors", region_name=region_name)
    
    try:
        print(f"Starting deletion process for bucket '{bucket_name}'...")
        
        # 1. Get list of indexes
        print("Getting list of indexes...")
        response = s3vectors.list_indexes(vectorBucketName=bucket_name)
        indexes = response.get('indexes', [])
        
        if indexes:
            print(f"Found {len(indexes)} index(es) to delete")
            
            # 2. Delete each index (this also deletes all vectors within)
            for index in indexes:
                index_name = index['indexName']
                print(f"Deleting index '{index_name}'...")
                
                try:
                    s3vectors.delete_index(
                        vectorBucketName=bucket_name,
                        indexName=index_name
                    )
                    print(f"Successfully deleted index '{index_name}'")
                    
                except ClientError as e:
                    print(f"Error deleting index '{index_name}': {e}")
                    return False
        else:
            print("No indexes found to delete")
        
        # 3. Delete the vector bucket
        print(f"Deleting vector bucket '{bucket_name}'...")
        s3vectors.delete_vector_bucket(vectorBucketName=bucket_name)
        print(f"Successfully deleted vector bucket '{bucket_name}'!")
        
        return True
        
    except ClientError as e:
        print(f"AWS API Error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    bucket_name = st.secrets["aws"]["bucket_name"]
    success = delete_vector_bucket(bucket_name)
    
    if success:
        print(f"\nDeletion of '{bucket_name}' completed successfully!")
    else:
        print(f"\nError occurred during deletion of '{bucket_name}'")