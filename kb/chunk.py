"""切分层：Markdown -> chunk 列表。

策略（按优先级）：
  1. 先按 Markdown 结构边界切（标题 / 段落），保证块语义完整
  2. 块太长 -> 按换行 -> 空格 -> 中文标点 依次找断点再切
  3. 相邻块之间保留少量重叠，避免答案正好被切断

这是企业制度类知识库最关键的一步：切得不对，检索出来就是半条制度。
"""
import re

HEADING = re.compile(r"^#{1,6}\s+", re.M)
CJK_PUNCT = "。！？；，、）】》”"  # 中文断点标点


def _split_long(text: str, size: int) -> list:
    """把超长文本按自然断点切���。"""
    out = []
    while len(text) > size:
        window = text[:size]
        cut = -1
        # 优先换行
        cut = window.rfind("\n")
        # 其次空格
        if cut < size // 3:
            cut = window.rfind(" ")
        # 再次中文标点
        if cut < size // 3:
            best = -1
            for i in range(len(window) - 1, size // 3, -1):
                if window[i] in CJK_PUNCT:
                    best = i + 1
                    break
            cut = best
        # 都找不到就硬切
        if cut <= 0:
            cut = size
        out.append(text[:cut].strip())
        text = text[cut:].lstrip()
    if text.strip():
        out.append(text.strip())
    return [c for c in out if c]


def _sections(text: str) -> list:
    """按 Markdown 标题切成小节，标题行会带进每节内容。"""
    parts = re.split(r"(?m)^(?=#{1,6}\s+)", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_markdown(text: str, size: int = 800, overlap: int = 100) -> list:
    chunks = []
    for sec in _sections(text):
        if len(sec) <= size:
            chunks.append(sec)
            continue
        # 小节内按段落聚合
        cur = ""
        for para in sec.split("\n\n"):
            if not para.strip():
                continue
            if len(cur) + len(para) + 2 <= size:
                cur = f"{cur}\n\n{para}" if cur else para
            else:
                if cur:
                    chunks.append(cur.strip())
                if len(para) <= size:
                    cur = para
                else:
                    pieces = _split_long(para, size)
                    chunks.extend(pieces[:-1])
                    cur = pieces[-1] if pieces else ""
        if cur.strip():
            chunks.append(cur.strip())
    # 加重叠：让跨块的上下文能命中
    if overlap > 0 and len(chunks) > 1:
        merged = [chunks[0]]
        for c in chunks[1:]:
            prev = merged[-1]
            tail = prev[-overlap:] if len(prev) > overlap else prev
            merged.append((tail + "\n" + c).strip())
        chunks = merged
    return chunks
