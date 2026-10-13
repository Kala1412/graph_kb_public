import uuid
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


def split_markdown_to_chunks(
    markdown_text: str,
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> List[Document]:
    """
    分块最好按意义进行chunks分块，而不是机械地按长度切分。尤其是markdown文档，章节结构很重要

    方式:
    1) 按几级标题分块，保证每个chunk内的文本在同一章节或子章节，避免混杂多个主题
    2) 分块避免过大，超过embedding模型的推荐范围（通常512-1000字）。过小则会丢失上下文信息。chunk_size=600比较合适，可以根据实际情况调整
    """
    if not markdown_text:
        return []

    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    # 按标题切分。保留语义结构，避免一个chunk混杂多个章节
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    header_splits = header_splitter.split_text(markdown_text)

    """首先尝试按 \n\n（段落）切分。
    如果切出来的段落还是大于 600 字，就尝试按 \n（换行）切分。
    如果还是太大，就按中文句号 。、感叹号 ！、问号 ？ 切分。
    这样可以保证切分的最小粒度是一个完整的句子，绝对不会把‘二甲双胍’这个词从中间劈成两半，最大限度保护了医学语义的完整性”
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？"],
    )
    chunks = text_splitter.split_documents(header_splits)

    # 为每个chunk生成唯一chunk_id（UUID）。为了后续在Milvus与Neo4j里对齐同一块文本
    for chunk in chunks:
        chunk.metadata = chunk.metadata or {}
        if not chunk.metadata.get("chunk_id"):
            chunk.metadata["chunk_id"] = str(uuid.uuid4())

    return chunks
