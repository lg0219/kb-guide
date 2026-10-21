"""入库流水线：文档目录 -> 解析 -> 切块 -> 嵌入 -> 入库。

用法：
    python -m kb.ingest data/docs            # 全量重建
    python -m kb.ingest data/docs --append   # 追加（不清空旧的）
"""
import argparse
import hashlib
import sys
from pathlib import Path

from . import chunk as chunker
from . import parse as parser
from . import store
from .config import CFG, BASE_DIR, path
from .embed import Embedder


def chunk_id(source: str, idx: int, text: str) -> str:
    h = hashlib.sha1(f"{source}#{idx}#{text}".encode("utf-8")).hexdigest()[:16]
    return f"{h}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="文档目录")
    ap.add_argument("--append", action="store_true", help="追加而不是重建")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_absolute():
        src = BASE_DIR / args.src
    md_dir = path(CFG["md_dir"])
    if not src.exists():
        print(f"[错误] 目录不存在: {src}")
        sys.exit(1)

    print(f"[1/4] 解析文档：{src}")
    files = parser.parse_dir(src, md_dir)
    if not files:
        print("[提示] 没有可解析的文件（支持 .pdf/.docx/.xlsx/.md/.txt）")
        sys.exit(1)

    print(f"[2/4] 切块（size={CFG['chunk_size']}, overlap={CFG['chunk_overlap']}）")
    db = store.connect()
    if not args.append:
        db.execute("DELETE FROM chunks")
        db.execute("DELETE FROM meta")
        db.commit()
        print("      已清空旧索引（--append 可保留）")

    all_chunks, meta_rows = [], []
    for src_file, md_file in files:
        rel = src_file.relative_to(src).as_posix()
        text = md_file.read_text(encoding="utf-8")
        pieces = chunker.chunk_markdown(text, CFG["chunk_size"], CFG["chunk_overlap"])
        for i, piece in enumerate(pieces):
            all_chunks.append((chunk_id(rel, i, piece), piece, rel, src_file.stem))
        print(f"      {rel}: {len(pieces)} 块")

    print(f"[3/4] 嵌入（{len(all_chunks)} 块，模型 {CFG['embed_model']}）")
    emb = Embedder()
    if not emb.health():
        print(f"[错误] 嵌入服务不可用: {CFG['embed_base_url']}")
        print("       先启动 OpenClaw 的本地模型服务，或改 config.json 的 embed_base_url")
        sys.exit(1)
    vectors = emb.embed([c[1] for c in all_chunks])
    print(f"      完成 {len(vectors)} 个向量")

    print("[4/4] 写入向量库")
    for (cid, piece, rel, title), vec in zip(all_chunks, vectors):
        store.upsert(db, cid, vec, rel, title, piece, extra={})
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"\n✅ 入库完成：{n} 个 chunk")
    print(f"   向量库: {path(CFG['db_path'])}")
    print(f"   检索示例: python -m kb.search \"你的问题\"")


if __name__ == "__main__":
    main()
