"""
DeepSeek OCR 处理器（通过 SiliconFlow API）
"""
import base64
import os
from pathlib import Path
import re
from openai import OpenAI
import fitz
import requests

class DeepSeekOCRProcessor:
    """DeepSeek OCR 处理器（使用 SiliconFlow API）"""

    MIME_TYPE_MAP = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OCR_API_KEY"),
            base_url=os.getenv("OCR_BASE_URL")
        )
        self.model = os.getenv("OCR_MODEL")

    async def process_file(self,file_path: str,params: dict | None = None) -> str:
        """
        处理文件（PDF或图片）并返回 Markdown 文本

        Args:
            file_path: 文件路径
            params: 处理参数

        Returns:
            str: Markdown 格式的文本
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        file_extension = Path(file_path).suffix.lower()

        if file_extension == ".pdf":
            return await self._process_pdf(file_path)
        elif file_extension in['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
            return await self._process_image(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")

    async def _process_image(self, image_path: str) -> str:
        """处理单张图片"""
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        return self._call_api(image_bytes)

    def _call_api(self, image_bytes: bytes) -> str:
        """
             调用 SiliconFlow DeepSeek-OCR API
            【关键】使用 OpenAI SDK + 特殊的 DeepSeek-OCR prompt 格式
        """
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        # 【关键】DeepSeek-OCR 特殊的 message 格式
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "<image>\n<|grounding|>\n请对上面的图片进行 OCR 识别，并将结果以 Markdown 格式返回。"
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1,
                timeout=120.0
            )
            content = response.choices[0].message.content

            # 清理特殊标签（DeepSeek-OCR 的输出格式）
            import re
            content = re.sub(r"<\|ref\|>.*?<\|/ref\|>", "", content)
            content = re.sub(r"<\|det\|>.*?<\|/det\|>", "", content)

            return content.strip()

        except Exception as e:
            print(f"❌ API 调用失败: {e}")
            raise RuntimeError(f"DeepSeek-OCR API 调用失败: {str(e)}")


    async def _process_pdf(self, pdf_path: str) -> str:
        """
        处理 PDF 文件
        策略：
            1. 使用 pdf2image 将 PDF 转为图片
            2. 逐页调用 OCR
            3. 合并结果
        """

        doc = fitz.open(pdf_path)

        try:
            full_text = []
            total_pages = len(doc)

            print(f"📄 Processing PDF with {total_pages} pages...")

            for i, page in enumerate(doc):
                print(f"   Processing page {i + 1}/{total_pages}...")

                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")

                page_text = self._call_api(img_bytes)
                full_text.append(f"## 第 {i + 1} 页\n\n{page_text}")

            return "\n\n---\n\n".join(full_text)
        finally:
            doc.close()

_deepseek_ocr_processor = None

def get_deepseek_ocr_processor() -> DeepSeekOCRProcessor:
    """获取 DeepSeek OCR 处理器单例"""
    global _deepseek_ocr_processor
    if _deepseek_ocr_processor is None:
        _deepseek_ocr_processor = DeepSeekOCRProcessor()
    return _deepseek_ocr_processor
