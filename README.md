# kb-lite · 轻量级企业知识库

无 GPU、内网隔离环境下的最小可用知识库：**解析 → 切块 → 嵌入 → 向量检索 → HTTP/MCP 服务**。

> 👉 **部署请直接看 [DEPLOY-GUIDE.md](DEPLOY-GUIDE.md)（傻瓜式操作指导书）**

## 特点

- **零外部服务**：向量库用 sqlite-vec（单文件），不需要 Milvus/Qdrant
- **数据不出内网**：嵌入调本地模型，无云端 API
- **解析零重依赖**：pypdf / python-docx / openpyxl（纯 Python，装包稳）
- **两种消费方式**：HTTP API（系统调用）+ MCP（Agent 直接挂载）

## 快速开始

```bash
python3 -m venv ~/kb-venv
~/kb-venv/bin/python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 改 config.json 里的 embed_base_url 指向你的本地嵌入模型
~/kb-venv/bin/python -m kb.ingest data/docs     # 入库
~/kb-venv/bin/python -m kb.search "出差住宿能报多少" -k 3   # 检索
./run.sh 8800                                    # 起服务
```

## 目录

| 文件 | 作用 |
|---|---|
| `kb/parse.py` | 文档解析（PDF/DOCX/XLSX/MD/TXT → 文本） |
| `kb/chunk.py` | 切块（按结构/长度，可配 size/overlap） |
| `kb/embed.py` | 嵌入（OpenAI 兼容接口） |
| `kb/store.py` | sqlite-vec 存储与检索 |
| `kb/ingest.py` | 入库流水线 |
| `kb/search.py` | 命令行检索 |
| `kb/server.py` | HTTP API（FastAPI）+ MCP 挂载 |
| `kb/mcp.py` | MCP stdio 入口（给 Agent） |

## 已验证

本机实测（4 核 / 7.6GB / 无 GPU）：3 份文档 → 8 个 chunk 入库；语义检索（换说法提问）命中正确条款；HTTP 鉴权 200/401 正确；MCP 端点可达。

## 升级路径

- 复杂版式/扫描件 → 解析层换 MinerU
- 数据上量 → 向量库换 Qdrant（改 `kb/store.py`）
- 权限控制 → 入库写 `extra` 标签，检索加 `where_sql`
