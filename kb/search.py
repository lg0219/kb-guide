"""命令行检索。

用法：
    python -m kb.search "迟到怎么扣钱" -k 5
"""
import argparse

from . import store
from .config import CFG
from .embed import Embedder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()

    db = store.connect()
    emb = Embedder()
    vec = emb.embed([args.query])[0]
    hits = store.search(db, vec, k=args.k)
    if not hits:
        print("没有命中")
        return
    for i, h in enumerate(hits, 1):
        print(f"\n--- [{i}] {h['source']}  (distance={h['distance']:.4f})")
        print(h["text"][:400])


if __name__ == "__main__":
    main()
