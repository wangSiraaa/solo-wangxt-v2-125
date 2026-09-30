#!/usr/bin/env bash
# 启动 FastAPI 后端（自动建表、PostGIS 扩展、播种虚构数据）。
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"

PREFIX="${PLUME_LOCAL:-/tmp/pglocal}"
export PLUME_DSN="${PLUME_DSN:-postgresql://plume@/plume_lab?host=/tmp&port=55432}"

if [ -d "$PREFIX/usr/lib/postgresql/15/bin" ]; then
  export PATH="$PREFIX/usr/lib/postgresql/15/bin:$PATH"
  export LD_LIBRARY_PATH="$(find "$PREFIX/usr/lib" -type d | tr '\n' ':')${LD_LIBRARY_PATH:-}"
fi

cd "$HERE/backend"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
