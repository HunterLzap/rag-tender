"""长文本安全分块工具。"""

from math import ceil


def split_text_chunks(
    text: str,
    *,
    chunk_size: int,
    overlap: int,
    max_chunks: int = 500,
) -> list[str]:
    """将文本切成带重叠的有限分块。

    最后一块到达文本末尾后立即退出，避免 ``end - overlap`` 使游标
    永远停在尾部。分块数量异常时主动失败，防止耗尽系统内存。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size")
    if max_chunks <= 0:
        raise ValueError("max_chunks 必须大于 0")
    if not text:
        return []

    step = chunk_size - overlap
    expected_chunks = 1 if len(text) <= chunk_size else 1 + ceil((len(text) - chunk_size) / step)
    if expected_chunks > max_chunks:
        raise ValueError(
            f"文本过长，预计产生 {expected_chunks} 个分块，超过安全上限 {max_chunks}"
        )

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap

    return chunks
