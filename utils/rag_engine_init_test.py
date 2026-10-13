import os
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from docling.document_converter import DocumentConverter

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

CHROMA_PATH = "./saves/chroma_db"

class RagEngine:
    def __init__(self):
        self.converter = DocumentConverter()

        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("LLM_API_KEY"),
            base_url="https://api.siliconflow.cn/v1",
            model="BAAI/bge-m3"
        )

        self.vector_store = Chroma(
            collection_name="medical_docs",
            embedding_function=self.embeddings,
            persist_directory=CHROMA_PATH
        )

    def parse_pdf_to_markdown(self, file_path: str) -> str:
        """
        使用 Docling 将 PDF 解析为 Markdown
        先转为 Markdown，保留文档结构
        """
        print(f"Running Docling conversion for: {file_path}...")
        try:
            result = self.converter.convert(file_path)
            markdown_text = result.document.export_to_markdown()
            print("Docling conversion success!")
            return markdown_text
        except Exception as e:
            print(f"Docling conversion failed: {e}")
            raise e

    def split_markdown(self, markdown_text: str) -> List[Document]:
        """
        按标题切分 Markdown
        保留章节语义结构
        """
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        md_header_splits = markdown_splitter.split_text(markdown_text)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=100,
            separators=["\n\n", "\n", "。", "！", "？"]
        )
        final_splits = text_splitter.split_documents(md_header_splits)
        return final_splits

    def index_document(self, file_path: str, metadata: dict) -> int:
        """
        主流程：解析 -> 切分 -> 入库
        """
        md_text = self.parse_pdf_to_markdown(file_path)

        chunks = self.split_markdown(md_text)

        for chunk in chunks:
            chunk.metadata.update(metadata)
            chunk.metadata["source"] = os.path.basename(file_path)

        print(f"Embedding and indexing {len(chunks)} chunks...")

        # 【关键修复】手动分批，每批 50 个 (小于 SiliconFlow 的 64 限制)
        BATCH_SIZE = 50
        total_chunks = len(chunks)

        for i in range(0, total_chunks, BATCH_SIZE):
            batch = chunks[i: i + BATCH_SIZE]
            print(f"Processing batch {i} to {min(i + BATCH_SIZE, total_chunks)}...")
            try:
                self.vector_store.add_documents(batch)
                # 可选：稍微睡一下，防止触发 QPS 限制
                time.sleep(0.5)
                print("Indexing {i}...")
            except Exception as e:
                print(f"Batch {i} failed: {e}")
                raise e

        print("Indexing Finished!")

        print("Indexing Finished!")

        return len(chunks)

    def search(self, query: str, kb_id: int, top_k: int = 5):
        """
        检索核心：计算 query 向量 -> 在 Chroma 中找 TopK -> 过滤 kb_id
        """
        print(f"Searching for '{query}' in KB {kb_id}...")

        # Chroma/LangChain 支持 filter 参数，这对应了 SQL 里的 WHERE 子句
        results = self.vector_store.similarity_search_with_score(
            query,
            k=top_k,
            filter={"kb_id": kb_id}
        )

        # result 结构是 (Document, score)，score 越小越相似（欧式距离）
        data = []
        for doc, score in results:
            data.append({
                "content": doc.page_content,
                "score": score,
                "source": doc.metadata.get("source"),
                "file_id": doc.metadata.get("file_id")
            })

        print(f"Found {len(data)} relevant chunks.")
        return data

rag_engine = RagEngine()
