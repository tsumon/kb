import json

import minio_client
from minio import Minio

from atguigu.config.config import MinIOConfig
from atguigu.tool.logger import logger

minio_client = None

def get_minio_client():
    global minio_client
    if not minio_client:
        try:
            minio_client = Minio(
                endpoint=MinIOConfig.minio_endpoint,
                access_key=MinIOConfig.minio_access_key,
                secret_key=MinIOConfig.minio_secret_key,
                # MinIO 部署为纯 HTTP，需显式关闭默认的 HTTPS
                secure=False,
            )

            #创建桶

            bucket_name = MinIOConfig.minio_bucket_name
            if not minio_client.bucket_exists(bucket_name):
                minio_client.make_bucket(bucket_name)

            #设置权限
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                        "Resource": f"arn:aws:s3:::{bucket_name}",
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*",
                    },
                ],
            }
            minio_client.set_bucket_policy(bucket_name=bucket_name, policy=json.dumps(policy))
        except Exception as e:
            logger.error(e)
    return minio_client



if __name__ == '__main__':
    get_minio_client()
