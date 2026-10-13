import io
import os

from minio import Minio, S3Error
from minio.deleteobjects import DeleteObject

class MinioHandler:
    def __init__(self):
        self.client = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9010"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "learningadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "learningadmin"),
            secure=False
        )
        self.bucket_name = "learning-local-knowledge-base"
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """确保指定的桶存在，如果不存在则创建它"""
        found = self.client.bucket_exists(self.bucket_name)
        if not found:
            self.client.make_bucket(self.bucket_name)
            print(f"Bucket '{self.bucket_name}' created.")
        else:
            print(f"Bucket '{self.bucket_name}' already exists.")


    def upload_file(self,file_data: bytes,file_name: str,content_type: str) -> str | S3Error:
        """上传文件到MinIO并返回文件URL"""
        try:
            data_stream = io.BytesIO(file_data)

            self.client.put_object(
                self.bucket_name,
                file_name,
                data_stream,
                length=len(file_data),
                content_type=content_type
            )
            url = f"https://localhost:9010/{file_name}"
            return url

        except S3Error as e:
            print(f"Minio Error occurred: {e}")
            return e

    def delete_kb_directory(self, kb_id: int):
        """删除指定知识库ID的目录下的所有文件"""
        prefix = f"kb_{kb_id}/"
        # 1. 列出该路径下的所有文件 recursive=True 很重要，否则只能删掉根目录下的文件，删不掉子目录
        objects_to_delete = self.client.list_objects(
            self.bucket_name, prefix=prefix, recursive=True
        )

        try:
            delete_list = [DeleteObject(obj.object_name) for obj in objects_to_delete]

            if not delete_list:
                print(f"知识库 {kb_id} 的目录下没有文件需要删除。")
                return

            # remove_objects 返回的是一个包含错误的迭代器
            errors = self.client.remove_objects(self.bucket_name, delete_list)

            # 必须遍历 errors，否则删除操作可能不会完全执行，
            error_list = list(errors)
            if error_list:
                for error in error_list:
                    print(f"❌ 删除对象时出错: {error}")
                # 如果有删除错误，抛出异常让上层回滚数据库
                raise Exception(f"MinIO 批量删除操作包含错误: {len(error_list)} 个文件删除失败")

            print(f"✅ 知识库 {kb_id} 的 MinIO 文件清理完成。")

        except Exception as e:
            print(f"Minio知识库文件删除系统级异常: {e}")
            raise e



minio_handler = MinioHandler()
