"""存储层：sqlite-vec 零服务向量库。

为什么用 sqlite-vec：单文件、零运维、Python 包只有几百 KB，
几万~几十万 chunk 完全够用；上量再换 Qdrant。
"""
import json
import sqlite3

import sqlite_vec

from .config import CFG


def connect(db_path=None):
    path = db_path or CFG["db_path"]
    import os as _os
    _os.makedirs(_os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    dims = CFG["embed_dims"]
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING vec0(chunk_id TEXT PRIMARY KEY, embedding float[%d])" % dims)
    db.execute("""CREATE TABLE IF NOT EXISTS meta (
        chunk_id TEXT PRIMARY KEY,
        source   TEXT,     -- 原始文件相对路径
        title    TEXT,     -- 来源标题
        text     TEXT,     -- 块正文
        extra    TEXT      -- JSON：权限标签等
    )""")
    db.commit()
    return db


def upsert(db, chunk_id, vector, source, title, text, extra=None):
    db.execute("DELETE FROM chunks WHERE chunk_id = ?", (chunk_id,))
    db.execute("INSERT INTO chunks(chunk_id, embedding) VALUES (?, ?)",
               (chunk_id, json.dumps(vector)))
    db.execute(
        "INSERT OR REPLACE INTO meta(chunk_id, source, title, text, extra) VALUES (?,?,?,?,?)",
        (chunk_id, source, title, text, json.dumps(extra or {}, ensure_ascii=False)),
    )


def search(db, vector, k=5, where_sql=None, params=None):
    """向量检索。where_sql 可加权限过滤（检索时过滤，不是生成后过滤）。"""
    sql = "SELECT chunk_id, distance FROM chunks WHERE embedding MATCH ? AND k = ?"
    args = [json.dumps(vector), k]
    if where_sql:
        sql += " AND " + where_sql
        args += list(params or [])
    sql += " ORDER BY distance"
    rows = db.execute(sql, args).fetchall()
    if not rows:
        return []
    ids = [r[0] for r in rows]
    dist = {r[0]: r[1] for r in rows}
    ph = ",".join("?" * len(ids))
    metas = db.execute(
        f"SELECT chunk_id, source, title, text, extra FROM meta WHERE chunk_id IN ({ph})", ids
    ).fetchall()
    out = []
    for m in metas:
        out.append({
            "chunk_id": m[0], "source": m[1], "title": m[2], "text": m[3],
            "extra": json.loads(m[4] or "{}"), "distance": dist.get(m[0]),
        })
    out.sort(key=lambda x: x["distance"])
    return out
