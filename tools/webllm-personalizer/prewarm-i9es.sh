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
  if ! DISPLAY=:0 XAUTHORITY=/home/ned/.Xauthority __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia glxinfo -B 2>/dev/null | grep -q 'OpenGL renderer string: NVIDIA'; then
    echo 'WEBLLM_PREWARM_SKIPPED: NVIDIA X11 unavailable'; exit 0
  fi
  DISPLAY=:0 XAUTHORITY=/home/ned/.Xauthority __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia __VK_LAYER_NV_optimus=NVIDIA_only nohup brave-browser --no-sandbox --disable-dev-shm-usage \
    --enable-unsafe-webgpu --ignore-gpu-blocklist --disable-extensions \
    --remote-debugging-address=127.0.0.1 --remote-debugging-port="$CDP" \
    --user-data-dir="$PROFILE" --window-position=-1800,-1600 --window-size=760,640 "http://127.0.0.1:$PORT/" \
    > "$RUN/local-webllm-browser.log" 2>&1 </dev/null &
  echo $! > "$RUN/local-webllm-browser.pid"
fi
sleep 1
curl -fsS --max-time 3 "http://127.0.0.1:$CDP/json/version" >/dev/null
node "$HERE/check-gpu.mjs" "$CDP" | tee "$RUN/webllm-prewarm-receipt.json"
