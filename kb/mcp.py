"""MCP stdio 入口：`python -m kb.mcp`

Agent 侧（OpenClaw / Codex / Cursor / Claude Desktop）配置示例：
    {"command": "/home/hunter/kb-venv/bin/python", "args": ["-m", "kb.mcp"]}
    （并设环境变量 PYTHONPATH=/home/hunter/kb）

只读两个工具：kb_search / kb_get_source。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from . import store
from .config import CFG
from .embed import Embedder
from .server import build_mcp

def main():
    store.connect()
    EMB = Embedder()
    # 让 build_mcp 内部的全局 DB/EMB 指向已连接的实例
    import kb.server as srv
    srv.DB = store.connect()
    srv.EMB = EMB
    mcp = build_mcp()
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
