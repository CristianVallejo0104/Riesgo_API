#!/bin/sh
set -eu

BACKEND_PORT="${BACKEND_PORT:-8000}"
STREAMLIT_PORT="${PORT:-8501}"

export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:${BACKEND_PORT}}"

python -m uvicorn app.main:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port "${BACKEND_PORT}" &

i=0
until python -c "import urllib.request; urllib.request.urlopen('${BACKEND_URL}/health', timeout=1)" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "FastAPI no respondio antes de iniciar Streamlit; continuando."
    break
  fi
  sleep 1
done

exec python -m streamlit run frontend/app.py \
  --server.address=0.0.0.0 \
  --server.port="${STREAMLIT_PORT}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
