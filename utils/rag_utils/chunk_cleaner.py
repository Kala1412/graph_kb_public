import hashlib
import re
import uuid
from collections import Counter
from typing import List

from langchain_core.documents import Document

# 合并块重新生成 chunk_id，source_chunk_ids 保留原始块来源。
class ChunkCleaner:
    def __init__(
        self,
        min_length: int = 30,
        near_dup_threshold: float = 0.9,
    ):
        self.min_length = min_length
        self.near_dup_threshold = near_dup_threshold

    def clean(self, chunks: List[Document]) -> List[Document]:
        if not chunks:
            return []

        chunks = self._strip_repeated_lines(chunks)
        chunks = self._filter_noise(chunks)
        chunks = self._deduplicate_exact(chunks)
        chunks = self._deduplicate_near(chunks)
        chunks = self._merge_fragments(chunks)
        return chunks
    
    # 页眉页脚剥离。识别“重复行”，批量移除高频的首行/末行文本
    def _strip_repeated_lines(self, chunks: List[Document]) -> List[Document]:
        if len(chunks) < 3:
            return chunks

        line_counter = Counter()
        for chunk in chunks:
            lines = [line.strip() for line in chunk.page_content.splitlines() if line.strip()]
            if not lines:
                continue
            line_counter[lines[0]] += 1
            if len(lines) > 1:
                line_counter[lines[-1]] += 1

        # 如果某行在超过30%的块中作为首/尾行出现，判定为页眉/页脚
        threshold = max(3, int(len(chunks) * 0.3))
        repeated = {line for line, count in line_counter.items() if count >= threshold}

        cleaned = []
        for chunk in chunks:
            lines = [line for line in chunk.page_content.splitlines() if line.strip()]
            lines = [line for line in lines if line.strip() not in repeated]
            chunk.page_content = "\n".join(lines).strip()
            cleaned.append(chunk)
        return cleaned

    # 噪声过滤。丢弃：目录、页码、纯符号、过短段落
    def _filter_noise(self, chunks: List[Document]) -> List[Document]:
        """
        用正则表达式清除诸如“目录”、“第 12 页”这种对回答医疗问题毫无帮助的系统级垃圾文本。
        此外，长度小于 30（min_length）的极短片段（如图片注释的残留）也没有语义价值，一并丢弃，
        节省大模型 Token 和数据库存储成本
        """
        noise_patterns = [
            r"^目录$",
            r"^目\s*录$",
            r"^contents$",
            r"^第\s*\d+\s*页$",
            r"^page\s*\d+$",
        ]
        filtered = []
        for chunk in chunks:
            text = chunk.page_content.strip()
            if len(text) < self.min_length:
                continue
            if all(re.fullmatch(r"[\W_]+", line.strip() or "_") for line in text.splitlines()):
                continue
            if any(re.match(pattern, text, re.IGNORECASE) for pattern in noise_patterns):
                continue
            filtered.append(chunk)
        return filtered

    # 精确去重。用MD5对文本hash去重
    def _deduplicate_exact(self, chunks: List[Document]) -> List[Document]:
        """
        相同的文本段落没必要存两遍。将文本压缩去除空格后，利用 MD5 算法生成信息摘要（Hash指纹）。
        MD5是一种经典算法，只要文本一模一样，算出来的哈希值绝对一致。使用set()集合利用了Hash表O(1)的查询时间复杂度，极其高效
        """
        seen = set()
        deduped = []
        for chunk in chunks:
            normalized = re.sub(r"\s+", "", chunk.page_content)
            digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            deduped.append(chunk)
        return deduped

    # 近似去重。用shingle+Jaccard去掉高度相似段落
    def _deduplicate_near(self, chunks: List[Document]) -> List[Document]:
        deduped: List[Document] = []
        signatures = []
        for chunk in chunks:
            sig = self._shingle_signature(chunk.page_content)
            """
            假设文本去空格后是："阿司匹林治头痛"。
            滑动窗口切出来的Shingle集合（Set）是：阿司匹 司匹林 匹林治 林治头 治头痛
            最终，这段话的特征指纹sig就是集合：{"阿司匹", "司匹林", "匹林治", "林治头", "治头痛"}
            """

            is_dup = False
            for other in signatures:
                if self._jaccard(sig, other) >= self.near_dup_threshold:
                    is_dup = True
                    break
                """
                交集（两边都有的）：{"阿司匹", "司匹林", "匹林治", "林治头"} -> 4 个
                并集（两边加起来去重后总共的）：{"阿司匹", "司匹林", "匹林治", "林治头", "治头痛", "治头疼"} -> 6 个
                Jaccard 相似度 = 4 ÷ 6 ≈ 0.67
                """
            if not is_dup:
                signatures.append(sig)
                deduped.append(chunk)
        return deduped

    # 语义合并。如果同一章节内出现连续碎片，合并成一块，并记录source_chunk_ids
    def _merge_fragments(self, chunks: List[Document]) -> List[Document]:
        if not chunks:
            return []
        merged: List[Document] = []
        buffer = chunks[0]
        buffer_ids = buffer.metadata.get("source_chunk_ids") or [buffer.metadata.get("chunk_id")]

        for current in chunks[1:]:
            buffer_text = buffer.page_content.strip()
            current_text = current.page_content.strip()
            same_header = self._same_header(buffer, current)

            # 条件A：必须在同一个标题下 (same_header)
            # 同一标题下任一块短于 120 字时合并，保留来源关联。
            if same_header and (len(buffer_text) < 120 or len(current_text) < 120):
                buffer.page_content = f"{buffer_text}\n{current_text}".strip()
                buffer_ids.append(current.metadata.get("chunk_id"))
                buffer.metadata["source_chunk_ids"] = buffer_ids
                continue
            merged.append(self._finalize_chunk(buffer, buffer_ids))
            buffer = current
            buffer_ids = current.metadata.get("source_chunk_ids") or [current.metadata.get("chunk_id")]
        merged.append(self._finalize_chunk(buffer, buffer_ids))
        return merged

    def _finalize_chunk(self, chunk: Document, source_ids: list) -> Document:
        if not chunk.metadata.get("source_chunk_ids"):
            chunk.metadata["source_chunk_ids"] = [cid for cid in source_ids if cid]
        chunk.metadata["chunk_id"] = str(uuid.uuid4())
        return chunk

    def _same_header(self, a: Document, b: Document) -> bool:
        """
        判断两个chunk是否同属一个章节
        作用： 提取两个文本块的 metadata 里所有以 "Header" 开头的键值对（比如 Header 1: 糖尿病, Header 2: 症状）。
        判断逻辑： 如果这两个字典完全相等，说明这两个碎片属于同一篇文档的同一个子标题下，可以安全合并。防止把“高血压的治疗”和“糖尿病的预防”错误地拼在了一起。
        """
        headers_a = {k: v for k, v in (a.metadata or {}).items() if k.startswith("Header")}
        headers_b = {k: v for k, v in (b.metadata or {}).items() if k.startswith("Header")}
        return headers_a == headers_b

    def _shingle_signature(self, text: str, size: int = 3) -> set[str]:
        """
        作用：把一段完整的长文本，切成一堆具有局部上下文的 词根集合（Set）
        怎么切：就像一个长度为 N（通常 N=3）的滑动窗口，每次往右挪一个字
        """
        normalized = re.sub(r"\s+", "", text)
        if len(normalized) <= size:
            return {normalized} if normalized else set()
        return {normalized[i : i + size] for i in range(len(normalized) - size + 1)}

    def _jaccard(self, a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)
