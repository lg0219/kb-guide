"""解析层：把 PDF / Word / Excel 转成 Markdown 文本。

轻量选型（全部纯 CPU，不需要下载模型）：
  PDF   -> pymupdf4llm（输出 Markdown，保留表格与标题结构）
  Word  -> python-docx
  Excel -> openpyxl（每个 sheet 转成 Markdown 表格 + "标题: 值" 列表）
"""
import os
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".xlsx", ".md", ".txt"}


def parse_pdf(path: Path) -> str:
    """PDF -> 文本。用 pypdf（纯 Python，无需 C 扩展，装包快且稳）。

    注意：pypdf 按 PDF 内嵌字体的编码提取文字。若 PDF 是扫描件（图片），
    这里提不出内容，需要 OCR 方案（见 README「进阶：换用 MinerU」）。
    """
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception as e:
            print(f"    [PDF 第{i+1}页提取失败] {type(e).__name__}")
            t = ""
        # CJK PDF 常出现每个字符间夹 \x00 的情况（2 字节 CID 被按 1 字节读），必须清洗
        t = t.replace("\x00", "")
        if t.strip():
            pages.append(t.strip())
    return "\n\n".join(pages)


def parse_docx(path: Path) -> str:
    import docx
    d = docx.Document(str(path))
    out = []
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        # 用 Word 的标题层级还原成 Markdown 标题，切分时才能按结构切
        style = (p.style.name or "") if p.style is not None else ""
        if style.startswith("Heading"):
            try:
                lvl = int(style.split()[-1])
            except ValueError:
                lvl = 1
            out.append("#" * min(lvl, 6) + " " + t)
        else:
            out.append(t)
    for ti, table in enumerate(d.tables):
        out.append(f"\n## 表格 {ti + 1}\n")
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            out.append("| " + " | ".join(cells) + " |")
    return "\n\n".join(out)


def parse_xlsx(path: Path) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"\n## {ws.title}\n")
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        # 前若干行做 Markdown 表格
        header = [str(c) if c is not None else "" for c in rows[0]]
        out.append("| " + " | ".join(header) + " |")
        out.append("| " + " | ".join(["---"] * len(header)) + " |")
        for r in rows[1:51]:
            out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
        if len(rows) > 51:
            out.append(f"（本表共 {len(rows)} 行，其余省略）")
        # 关键字段转成"标题: 值"，方便语义检索命中具体数字
        for r in rows[:60]:
            if r and len(r) >= 2 and r[0] is not None:
                key = str(r[0]).strip()
                val = "" if r[1] is None else str(r[1]).strip()
                if key and val and len(key) <= 20:
                    out.append(f"- {key}：{val}")
    wb.close()
    return "\n".join(out)


def parse_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".docx":
        return parse_docx(path)
    if ext == ".xlsx":
        return parse_xlsx(path)
    if ext in (".md", ".txt"):
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"不支持的文件类型: {ext}")


def parse_dir(src_dir: Path, md_dir: Path) -> list:
    """解析整个目录，返回 [(源文件, Markdown文件)] 列表。"""
    md_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for p in sorted(src_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SUPPORTED:
            continue
        try:
            text = parse_file(p)
        except Exception as e:
            print(f"  [跳过] {p.name}: {type(e).__name__}: {e}")
            continue
        rel = p.relative_to(src_dir).as_posix().replace("/", "__")
        out = md_dir / (rel + ".md")
        out.write_text(text, encoding="utf-8")
        print(f"  [解析] {p.name} -> {out.name}  ({len(text)} 字符)")
        results.append((p, out))
    return results
