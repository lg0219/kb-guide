#!/usr/bin/env bash
# 启动检索服务。用法: ./run.sh [端口]
set -e
cd "$(dirname "$0")"

# ---- 配置 ----
export KB_API_TOKENS="${KB_API_TOKENS:-dev-token}"   # 正式环境改成随机长串
PORT="${1:-8800}"
# -------------

echo "启动知识库检索服务 :$PORT （token 数: $(echo "$KB_API_TOKENS" | tr ',' '\n' | wc -l)）"
exec /home/hunter/kb-venv/bin/python -m kb.server --port "$PORT"
