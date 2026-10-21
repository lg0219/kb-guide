"""检索服务：同时暴露 HTTP API 和 MCP。

HTTP API  -> 给系统用（批处理、其他服务、运维排查）
MCP       -> 给 Agent 用（工具自动发现，Codex / OpenClaw / Cursor 都能接）

启动：
    python -m kb.server --port 8800
"""
import argparse
import json
import os

from . import store
from .config import CFG
from .embed import Embedder

DB = None
EMB = None

# 每个调用方带自己的 token；这里做最简校验（换成你的真实鉴权逻辑）
API_TOKENS = {t.strip() for t in os.environ.get("KB_API_TOKENS", "dev-token").split(",") if t.strip()}


def _check_token(token):
    return token in API_TOKENS


def do_search(query, k=5, extra_filter=None):
    vec = EMB.embed([query])[0]
    hits = store.search(DB, vec, k=k, where_sql=extra_filter)
    return hits


# ---------------- HTTP API ----------------
def build_http_app():
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse

    app = FastAPI(title="企业知识库检索服务", version="1.0")

    @app.get("/health")
    def health():
        n = DB.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"status": "ok", "chunks": n, "embed_model": CFG["embed_model"]}


    @app.post("/search")
    def search(request: Request, query: str, k: int = 5):
        # 兼容 x-api-key 与 Authorization: Bearer 两种传法
        token = request.headers.get("x-api-key", "") or request.headers.get("authorization", "").replace("Bearer ", "").strip()
        if not _check_token(token):
            raise HTTPException(status_code=401, detail="invalid api key")
        hits = do_search(query, k)
        return {"query": query, "results": hits}

    return app


# ---------------- MCP ----------------
def build_mcp():
    # mcp 1.x 用 FastMCP；mcp 2.x 改名为 MCPServer（API 基本一致）。按版本分支导入。
    try:
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("corp-kb")
    except ModuleNotFoundError:
        from mcp.server.mcpserver import MCPServer
        mcp = MCPServer("corp-kb")

    @mcp.tool()
    def kb_search(query: str, k: int = 5) -> str:
        """在企业知识库中检索与问题最相关的制度/文档片段。
        问制度、规定、流程、报销、采购、请假等问题时使用。"""
        hits = do_search(query, k)
        if not hits:
            return "未检索到相关内容。"
        parts = []
        for i, h in enumerate(hits, 1):
            parts.append(
                f"[{i}] 来源：{h['source']}（相似度距离 {h['distance']:.4f}）\n{h['text']}"
            )
        return "\n\n".join(parts)

    @mcp.tool()
    def kb_get_source(source: str) -> str:
        """按文件名取回该文档的全部已入库片段（用于看上下文全貌）。"""
        rows = DB.execute("SELECT text FROM meta WHERE source = ? ORDER BY chunk_id", (source,)).fetchall()
        if not rows:
            return f"没有找到来源为 {source} 的内容。"
        return "\n\n---\n\n".join(r[0] for r in rows)

    return mcp


def main():
    global DB, EMB
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--transport", default="http", choices=["http", "stdio"])
    args = ap.parse_args()

    DB = store.connect()
    EMB = Embedder()

    if args.transport == "stdio":
        # MCP stdio 模式：由独立入口 kb/mcp.py 处理
        raise SystemExit("请用 `python -m kb.mcp` 启动 MCP（stdio）")

    import uvicorn
    http_app = build_http_app()
    # 挂载 MCP（HTTP 流式）到 /mcp；mcp 版本不支持时自动跳过
    try:
        mcp = build_mcp()
        http_app.mount("/mcp", mcp.streamable_http_app())
    except Exception as e:
        print(f"[warn] MCP 端点不可用（{type(e).__name__}: {e}）；HTTP API 仍可用")
    uvicorn.run(http_app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
