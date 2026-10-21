# 企业知识库·傻瓜式部署指导书（轻量级方案）

> 适用：无 GPU、内网隔离、4 核 CPU、7~8GB 内存的机器
> 选型：解析(pypdf/python-docx/openpyxl) + 切块(自定义) + 嵌入(现有本地嵌入模型) + 向量库(sqlite-vec) + 服务(FastAPI + MCP)
> 已在本机实测跑通：8 个测试 chunk 入库 → 语义检索命中 → HTTP/MCP 服务可用

## 0. 这套东西长什么样

```
原始文档(PDF/DOCX/XLSX/MD/TXT)
     │  放到 data/docs/
     ▼
kb.parse        解析成统一文本
     ▼
kb.chunk        切块（大小/重叠可配）
     ▼
kb.embed        调本地嵌入模型，算向量
     ▼
kb.store        写入 sqlite-vec（kb/data/kb.db）
     ▼
kb.search / kb.server   语义检索（命令行 或 HTTP/MCP 服务）
```

## 1. 一键初始化（首次）

```bash
# 1. 建虚拟环境（建议用项目专用 venv）
python3 -m venv ~/kb-venv
~/kb-venv/bin/python -m pip install -U pip

# 2. 装依赖（国内用阿里云镜像）
cd /home/hunter/kb
~/kb-venv/bin/python -m pip install -r requirements.txt \
  -i https://mirrors.aliyun.com/pypi/simple/
```

> ⚠️ 踩坑提醒：`pymupdf4llm` 2.0 在镜像上是坏包，**本方案已改用 `pypdf`（纯 Python，秒装、稳定）**。requirements 里别装 pymupdf4llm。

## 2. 配嵌入模型

打开 `config.json`，按你的实际情况改：

```json
{
  "embed_base_url": "http://127.0.0.1:39049/v1",
  "embed_api_key": "noop",
  "embed_model": "embeddinggemma-300m-qat-q8_0",
  "embed_dims": 768
}
```

`embed_base_url` 是你的本地嵌入模型服务地址（OpenClaw 自带的本地模型，或你自己起的）。
先确认它活着：

```bash
curl -s http://127.0.0.1:39049/health
```

> 想用更好的中文模型（BGE-M3）：把它也起成一个 OpenAI 兼容服务，改 `embed_model`/`embed_dims`（BGE-M3 是 1024 维）即可，代码不用动。

## 3. 放文档

把你自己的文档（PDF/DOCX/XLSX/MD/TXT）丢进 `data/docs/`。

## 4. 入库

```bash
cd /home/hunter/kb
~/kb-venv/bin/python -m kb.ingest data/docs
# 输出：解析→切块→嵌入→写入向量库，最后打印「入库完成：N 个 chunk」
```

## 5. 检索（命令行）

```bash
~/kb-venv/bin/python -m kb.search "出差住酒店最多能报多少钱" -k 3
```

用**换一种说法**的问法验证是真语义检索，不是关键词匹配。

## 6. 起检索服务（给系统 / Agent 用）

```bash
# HTTP API（系统调用、批处理、运维）
~/kb-venv/bin/python -m kb.server --port 8800

# 调 HTTP API
curl -X POST "http://127.0.0.1:8800/search?query=请假流程&k=2" \
  -H "x-api-key: ***"        # 默认 token，正式用要设 KB_API_TOKENS 环境变量
curl http://127.0.0.1:8800/health

# MCP（给 Agent 用：OpenClaw / Codex / Cursor / Claude Desktop）
~/kb-venv/bin/python -m kb.mcp
```

### 把 MCP 接进 OpenClaw（Agent 侧）

在 `~/.openclaw/openclaw.json` 的 `mcp.servers` 里加：

```json
{
  "corp-kb": {
    "command": "/home/hunter/kb-venv/bin/python",
    "args": ["-m", "kb.mcp"],
    "cwd": "/home/hunter/kb",
    "env": { "KB_API_TOKENS": "dev-token" }
  }
}
```

重启 OpenClaw 后，agent 就自动获得 `kb_search` / `kb_get_source` 两个工具。

## 7. 验证全链路（一次性验收脚本）

```bash
cd /home/hunter/kb
P=~/kb-venv/bin/python
$P -m kb.ingest data/docs >/dev/null 2>&1 && echo "1 入库 ✅"
$P -m kb.search "出差住酒店最多能报多少钱" -k 1 >/dev/null && echo "2 检索 ✅"
$P -m kb.server --port 8800 & sleep 8
curl -sf http://127.0.0.1:8800/health >/dev/null && echo "3 服务 ✅"
curl -sf -X POST "http://127.0.0.1:8800/search?query=hi&k=1" -H "x-api-key: ***" >/dev/null && echo "4 鉴权 ✅"
kill %1 2>/dev/null
echo "全链路 OK"
```

## 8. 常见坑（已在本机踩过并解决）

| 现象 | 原因 | 解决 |
|---|---|---|
| `pymupdf4llm` 导不进来 | 镜像上 2.0 是坏包 | 改用 `pypdf` |
| 中文 PDF 提取出 `\x00` | CJK 字体 2 字节编码 | parse.py 已加 `.replace("\x00","")` |
| 服务起后请求 401 | 旧进程没杀 / token 没传 | 确认新进程、`KB_API_TOKENS` 生效 |
| `SQLite objects created in a thread` | uvicorn 多线程 | store.py 已加 `check_same_thread=False` |
| URL 里裸中文 400 | 没做 URL 编码 | 用 curl 时中文要编码或放 JSON body |

## 9. 下一步升级（按需）

- **换 MinerU 解析**：复杂版式/扫描件，替换 `kb/parse.py` 的 `parse_pdf` 等
- **上量换 Qdrant**：把 `kb/store.py` 换成 Qdrant client，API 不变
- **加权限过滤**：入库时写 `extra` 权限标签，检索时 `where_sql` 过滤
- **结构化数据**：走 NL2-SQL / 语义层，别塞进向量库
