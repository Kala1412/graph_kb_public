"""
Markdown 处理服务
负责将文件转换为 Markdown 并存储到 MinIO
"""
import os
import io
import time
import re
import mimetypes
from pathlib import Path
from urllib.parse import unquote
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc.base import ImageRefMode
import fitz

from utils.mineru_client import get_mineru_processor
from utils.minio_client import minio_handler
from utils.ocr_tool import get_deepseek_ocr_processor

# Docling 转换器单例
_docling_converter: DocumentConverter | None = None

def get_docling_converter() -> DocumentConverter:
    """获取 Docling 转换器单例"""
    global _docling_converter
    if _docling_converter is None:
        pdf_options = PdfPipelineOptions(generate_picture_images=True)
        format_options = {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
        }
        _docling_converter = DocumentConverter(format_options=format_options)
    return _docling_converter


def _collect_assets_from_dir(assets_dir: Path, base_dir: Path) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    if not assets_dir.exists():
        return assets
    for asset_path in sorted(assets_dir.rglob("*")):
        if asset_path.is_file():
            rel_path = asset_path.relative_to(base_dir).as_posix()
            assets[rel_path] = asset_path.read_bytes()
    return assets


def _convert_docling_with_assets(file_path: str) -> tuple[str, dict[str, bytes]]:
    import tempfile

    converter = get_docling_converter()
    result = converter.convert(file_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        md_path = tmp_dir_path / "docling.md"
        artifacts_rel = Path("docling_artifacts")

        result.document.save_as_markdown(
            filename=md_path,
            artifacts_dir=artifacts_rel,
            image_mode=ImageRefMode.REFERENCED,
        )

        markdown_text = md_path.read_text(encoding="utf-8")
        assets_dir = tmp_dir_path / artifacts_rel
        assets = _collect_assets_from_dir(assets_dir, tmp_dir_path)

    return markdown_text, assets


def _extract_pdf_images(pdf_path: str, max_images: int = 200) -> dict[str, bytes]:
    """
    Docling解析图片方法：从 PDF 中直接提取嵌入图片（不渲染整页）
    返回 {relative_path: bytes}
    """
    assets: dict[str, bytes] = {}
    seen_xref: set[int] = set()
    doc = fitz.open(pdf_path)
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            images = page.get_images(full=True)
            for img_index, img in enumerate(images):
                xref = img[0]
                if xref in seen_xref:
                    continue
                seen_xref.add(xref)
                info = doc.extract_image(xref)
                image_bytes = info.get("image")
                ext = info.get("ext") or "png"
                if not image_bytes:
                    continue
                name = f"docling_images/page_{page_index + 1:03d}_img_{img_index + 1:03d}.{ext}"
                assets[name] = image_bytes
                if len(assets) >= max_images:
                    return assets
    finally:
        doc.close()
    return assets

async def process_file_to_markdown(
        minio_bucket: str,
        minio_object: str,
        file_extension: str,
        enable_ocr: str = "disable"
) -> tuple[str, dict[str, bytes]]:
    """
    从 MinIO 下载文件 → 解析为 Markdown

    Args:
        minio_bucket: MinIO 桶名
        minio_object: MinIO 对象名（文件路径）
        file_extension: 文件扩展名（.pdf, .docx, .jpg 等）
        enable_ocr: OCR 模式（disable / deepseek_ocr / MinerU）

    Returns:
        (Markdown 文本, 资源文件字典)
    """
    import tempfile

    temp_file_path = None
    try:
        print(f"📥 Downloading {minio_object} from MinIO...")
        file_content = minio_handler.client.get_object(
            minio_bucket,
            minio_object
        ).read()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_extension
        ) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        print(f"📄 Saved to temp: {temp_file_path}")

        assets: dict[str, bytes] = {}

        if file_extension == ".pdf":
            if enable_ocr == "deepseek_ocr":
                print("🔄 Using DeepSeek OCR for PDF...")
                processor = get_deepseek_ocr_processor()
                markdown_text = await processor.process_file(temp_file_path)
            elif enable_ocr == "mineru":
                print("🔄 Using MinerU for PDF...")
                processor = get_mineru_processor()
                markdown_text, assets = await processor.process_file_with_assets(temp_file_path)
            else:
                print("🔄 Using Docling for PDF...")
                markdown_text, assets = _convert_docling_with_assets(temp_file_path)
                try:
                    extracted_assets = _extract_pdf_images(temp_file_path)
                    for rel_path, data in extracted_assets.items():
                        assets.setdefault(rel_path, data)
                except Exception as img_err:
                    print(f"? Docling 图片提取失败: {img_err}")
        elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
            # 图片必须使用 OCR
            if enable_ocr == "disable":
                raise ValueError("图片文件必须启用 OCR")

            print("🔄 Using DeepSeek OCR for Image...")
            processor = get_deepseek_ocr_processor()
            markdown_text = await processor.process_file(temp_file_path)
        elif file_extension in ['.docx', '.pptx', '.xlsx']:
            print("🔄 Using Docling for Office file...")
            markdown_text, assets = _convert_docling_with_assets(temp_file_path)
        elif file_extension in ['.txt', '.md']:
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                markdown_text = f.read()
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")
        print(f"✅ Markdown generated ({len(markdown_text)} chars)")

        return markdown_text, assets
    except Exception as e:
        print(f"❌ Markdown conversion failed: {e}")
        raise
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            print(f"🗑️ Cleaned temp file: {temp_file_path}")


def _normalize_asset_path(path: str) -> str:
    cleaned = unquote(path.replace("\\", "/").strip())
    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0]
    parts = [p for p in cleaned.split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def _asset_lookup_keys(path: str) -> list[str]:
    normalized = _normalize_asset_path(path)
    if not normalized:
        return []

    keys: list[str] = [normalized]
    base = os.path.basename(normalized)
    if base and base not in keys:
        keys.append(base)

    first_sep = normalized.find("/")
    if first_sep != -1:
        without_root = normalized[first_sep + 1:]
        if without_root and without_root not in keys:
            keys.append(without_root)
    return keys


def _rewrite_markdown_images(markdown_text: str, asset_url_map: dict[str, str]) -> str:
    if not asset_url_map:
        return markdown_text

    def resolve_url(raw_url: str) -> str:
        url = raw_url.strip().strip("<>")
        if url.startswith("http://") or url.startswith("https://") or url.startswith("data:"):
            return url
        for key in _asset_lookup_keys(url):
            if key in asset_url_map:
                return asset_url_map[key]
        return url

    def repl_md(match: re.Match) -> str:
        alt = match.group(1)
        url = match.group(2)
        tail = match.group(3) or ""
        return f"![{alt}]({resolve_url(url)}{tail})"

    markdown_text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)([^)]*)\)", repl_md, markdown_text)

    def repl_html(match: re.Match) -> str:
        attrs = match.group(1) or ""
        src = match.group(2) or ""
        alt_match = re.search(r'alt=[\"\\\']([^\"\\\']*)[\"\\\']', attrs)
        alt = alt_match.group(1) if alt_match else ""
        return f"![{alt}]({resolve_url(src)})"

    markdown_text = re.sub(
        r"<img([^>]*?)src=[\"\\\']([^\"\\\']+)[\"\\\']([^>]*)>",
        repl_html,
        markdown_text,
        flags=re.IGNORECASE,
    )

    return markdown_text


def _has_image_reference(markdown_text: str) -> bool:
    if re.search(r"!\[[^\]]*\]\(", markdown_text):
        return True
    if re.search(r"<img[^>]*>", markdown_text, flags=re.IGNORECASE):
        return True
    return False


async def save_markdown_to_minio(
        markdown_content: str,
        kb_id: int,
        file_id: int,
        original_filename: str,
        assets: dict[str, bytes] | None = None
) -> tuple[str, str]:
    """
    将 Markdown 内容保存到 MinIO

    Returns:
        (markdown_url, markdown_path) 元组
    """
    timestamp = int(time.time() * 1000)
    base_name = Path(original_filename).stem
    markdown_filename = f"{base_name}_{timestamp}.md"

    # MinIO 路径：kb_{kb_id}/markdown/file_{file_id}/xxx.md
    markdown_object = f"kb_{kb_id}/markdown/file_{file_id}/{markdown_filename}"

    asset_url_map: dict[str, str] = {}
    asset_urls: list[str] = []
    if assets:
        backend_base = (
            os.getenv("BACKEND_BASE_URL")
            or "http://127.0.0.1:8000/api"
        )
        backend_base = backend_base.rstrip("/")
        for rel_path, data in assets.items():
            safe_path = _normalize_asset_path(rel_path)
            if not safe_path:
                continue
            asset_object = f"kb_{kb_id}/markdown/file_{file_id}/assets/{safe_path}"
            content_type = mimetypes.guess_type(safe_path)[0] or "application/octet-stream"
            data_stream = io.BytesIO(data)
            minio_handler.client.put_object(
                minio_handler.bucket_name,
                asset_object,
                data_stream,
                length=len(data),
                content_type=content_type
            )
            asset_url = f"{backend_base}/knowledge/files/{file_id}/assets/{safe_path}"
            for key in _asset_lookup_keys(safe_path):
                if key not in asset_url_map:
                    asset_url_map[key] = asset_url
            asset_urls.append(asset_url)

    if asset_url_map:
        markdown_content = _rewrite_markdown_images(markdown_content, asset_url_map)
        if asset_urls and not _has_image_reference(markdown_content):
            unique_urls = list(dict.fromkeys(asset_urls))
            image_lines = "\n".join(
                f"![{os.path.basename(url)}]({url})" for url in unique_urls
            )
            markdown_content = (
                f"{markdown_content}\n\n## 图片资源\n\n{image_lines}"
            )

    markdown_bytes = markdown_content.encode("utf-8")
    data_stream = io.BytesIO(markdown_bytes)
    minio_handler.client.put_object(
        minio_handler.bucket_name,
        markdown_object,
        data_stream,
        length=len(markdown_bytes),
        content_type="text/markdown"
    )

    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9010")
    markdown_url = f"http://{endpoint}/{minio_handler.bucket_name}/{markdown_object}"
    print(f"✅ Markdown saved to MinIO: {markdown_url}")
    return markdown_url, markdown_object



















































