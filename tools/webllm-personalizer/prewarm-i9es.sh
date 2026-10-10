#!/usr/bin/env bash
# Opportunistic isolated WebLLM warm-up on i9ES.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
RUN="$ROOT/.runtime"
PROFILE="${TF_WEBLLM_PROFILE:-/home/ned/.cache/torsionfield-webllm-brave}"
PORT="${TF_WEBLLM_PORT:-8989}"
CDP="${TF_WEBLLM_CDP:-9235}"
mkdir -p "$RUN" "$PROFILE"
cd "$HERE"
if [ ! -f dist/app.js ] || [ ! -f dist/worker.js ]; then
  [ -d node_modules ] || npm ci --no-audit --no-fund
  npm run build
fi
if ! curl -fsS --max-time 2 "http://127.0.0.1:$PORT/" >/dev/null; then
  nohup python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$HERE" \
    > "$RUN/local-webllm-http.log" 2>&1 </dev/null &
  echo $! > "$RUN/local-webllm-http.pid"
fi
if ! curl -fsS --max-time 2 "http://127.0.0.1:$CDP/json/version" >/dev/null; then
  nohup brave-browser --headless --no-sandbox --disable-dev-shm-usage \
    --enable-unsafe-webgpu --enable-features=Vulkan \
    --remote-debugging-address=127.0.0.1 --remote-debugging-port="$CDP" \
    --user-data-dir="$PROFILE" "http://127.0.0.1:$PORT/" \
    > "$RUN/local-webllm-browser.log" 2>&1 </dev/null &
  echo $! > "$RUN/local-webllm-browser.pid"
fi
sleep 1
curl -fsS --max-time 3 "http://127.0.0.1:$CDP/json/version" >/dev/null
printf "WEBLLM_PREWARM_STARTED port=%s cdp=%s\n" "$PORT" "$CDP"
