import asyncio
import os
import time
import zipfile
import io
import httpx


class MinerUProcessor:
    """MinerU (PDF-Extract) API 处理器"""
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}

    def __init__(self):
        self.api_key = os.getenv("MINERU_API")
        self.base_url = os.getenv("MINERU_BASE_URL")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def process_file(self,file_path: str) -> str:
        """
            调用 MinerU API 处理 PDF 文件并返回 Markdown
            完整处理流程：申请链接 -> 上传 -> 轮询 -> 获取结果
        """
        markdown_text, _ = await self.process_file_with_assets(file_path)
        return markdown_text

    async def process_file_with_assets(self, file_path: str) -> tuple[str, dict[str, bytes]]:
        """
            调用 MinerU API 处理 PDF 文件并返回 Markdown + 资源文件
            Returns:
                (markdown_text, assets) assets 为 {relative_path: bytes}
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)

        # 使用 httpx 进行异步 HTTP 请求，设置 trust_env=False 禁用系统代理
        async with httpx.AsyncClient(timeout=60., trust_env=False) as client:
            batch_id, upload_url = await self._get_upload_params(client, file_name)

            print(f"📤 正在上传文件到 MinerU 临时存储...")
            await self._update_to_s3(client, upload_url, file_path)

            print(f"⏳ 正在等待 MinerU 解析完成 (batch_id: {batch_id})...")
            file_result = await self._poll_result(client, batch_id)

            zip_url = file_result.get("full_zip_url")
            print(f"📥 正在下载并处理结果包...")
            markdown_text, assets = await self._download_and_extract_md_with_assets(client, zip_url)

            return markdown_text, assets

    async def _get_upload_params(self, client, file_name):
        """步骤 1: 申请上传链接"""
        data = {
            "files": [{"name": file_name, "is_ocr": True, "data_id": f"idx_{int(time.time())}"}],
            "model_version": "vlm",
            "enable_formula": True,
            "enable_table": True,
            "language": "ch"
        }
        resp = await client.post(f"{self.base_url}/file-urls/batch", headers=self.headers, json=data)
        resp.raise_for_status()
        res_json = resp.json()

        if res_json["code"] != 0:
            raise RuntimeError(f"申请上传失败: {res_json['msg']}")

        return res_json["data"]["batch_id"], res_json["data"]["file_urls"][0]

    async def _update_to_s3(self, client: httpx.AsyncClient, upload_url: str, file_path: str):
        """步骤 2: 上传文件到 S3"""
        with open(file_path, "rb") as f:
            # 修改超时时间，防止大文件上传失败
            resp = await client.put(upload_url, content=f.read(), timeout=300.0)
            resp.raise_for_status()

    async def _poll_result(self, client: httpx.AsyncClient, batch_id: str) -> dict:
        """步骤 3: 轮询结果 (参考 v4 接口文档)"""
        poll_url = f"{self.base_url}/extract-results/batch/{batch_id}"
        max_retries = 60

        for i in range(max_retries):
            resp = await client.get(poll_url, headers=self.headers)
            resp.raise_for_status()
            res_json = resp.json()

            if res_json["code"] != 0:
                raise RuntimeError(f"查询任务失败: {res_json['msg']}")

            # extract_result 是一个列表，因为是批量接口，取第一个文件
            file_result = res_json["data"]["extract_result"][0]
            state = file_result["state"]

            if state == "done":
                return file_result
            elif state == "failed":
                raise RuntimeError(f"MinerU 解析失败: {file_result.get('err_msg')}")

            if state == "running":
                progress = file_result.get("extract_progress", {})
                print(f"--- 解析进度: {progress.get('extracted_pages', 0)}/{progress.get('total_pages', 0)} 页 ---")

            await asyncio.sleep(10)

        raise TimeoutError("MinerU 解析超时")

    async def _download_and_extract_md(self, client: httpx.AsyncClient, zip_url: str) -> str:
        """步骤 4: 下载 ZIP 并从中读取 .md 文件"""
        markdown_text, _ = await self._download_and_extract_md_with_assets(client, zip_url)
        return markdown_text

    async def _download_and_extract_md_with_assets(
        self, client: httpx.AsyncClient, zip_url: str
    ) -> tuple[str, dict[str, bytes]]:
        """步骤 4: 下载 ZIP 并从中读取 .md 文件与资源"""
        resp = await client.get(zip_url, timeout=60.0)
        resp.raise_for_status()

        # 使用内存中的 ZipFile 处理，避免写磁盘
        markdown_text = None
        assets: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for name in z.namelist():
                if name.endswith(".md"):
                    with z.open(name) as f:
                        markdown_text = f.read().decode("utf-8")
                else:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in self.IMAGE_EXTS:
                        with z.open(name) as f:
                            assets[name] = f.read()

        if not markdown_text:
            raise RuntimeError("在结果包中未找到 Markdown 文件")

        return markdown_text, assets



_mineru_processor = None

def get_mineru_processor() -> MinerUProcessor:
    """获取 MinerU 处理器单例"""
    global _mineru_processor
    if _mineru_processor is None:
        _mineru_processor = MinerUProcessor()
    return _mineru_processor



