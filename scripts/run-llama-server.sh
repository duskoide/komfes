#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
model=${HARGATURUN_MODEL_PATH:-"$project_root/models/hargaturun-qwen3.5-4b-q4_k_m.gguf"}
port=${HARGATURUN_MODEL_PORT:-8080}
alias=${HARGATURUN_MODEL_NAME:-hargaturun-qwen3.5-4b}

if [[ ! -f "$model" ]]; then
  echo "Model not found: $model" >&2
  echo "Set HARGATURUN_MODEL_PATH or place the GGUF under models/." >&2
  exit 1
fi

if [[ -n "${HARGATURUN_LLAMA_SERVER:-}" ]]; then
  server=$HARGATURUN_LLAMA_SERVER
else
  mapfile -t candidates < <(
    find "$HOME/.lmstudio/extensions/backends" -maxdepth 2 -type f \
      -path '*llama.cpp-linux-x86_64-nvidia-cuda*/llama-server' 2>/dev/null \
      | sort -V
  )
  if ((${#candidates[@]} == 0)); then
    server=$(command -v llama-server || true)
  else
    server=${candidates[-1]}
  fi
fi

if [[ -z "${server:-}" || ! -x "$server" ]]; then
  echo "No executable CUDA llama-server found." >&2
  echo "Set HARGATURUN_LLAMA_SERVER to a llama-server binary." >&2
  exit 1
fi

server_dir=$(dirname "$server")
vendor_dir=${HARGATURUN_CUDA_VENDOR_DIR:-"$HOME/.lmstudio/extensions/backends/vendor/linux-llama-cuda-vendor-v1"}
lib_path=$server_dir
if [[ -d "$vendor_dir" ]]; then
  lib_path="$lib_path:$vendor_dir"
fi
if [[ -n "${LD_LIBRARY_PATH:-}" ]]; then
  lib_path="$lib_path:$LD_LIBRARY_PATH"
fi

if ss -ltn 2>/dev/null | grep -qE ":${port}[[:space:]]"; then
  echo "Port $port is already in use." >&2
  exit 1
fi

printf 'Starting %s\nModel: %s\nEndpoint: http://127.0.0.1:%s/v1\n' \
  "$server" "$model" "$port"

exec env LD_LIBRARY_PATH="$lib_path" "$server" \
  --model "$model" \
  --alias "$alias" \
  --host 127.0.0.1 \
  --port "$port" \
  --ctx-size 4096 \
  --n-predict 350 \
  --parallel 1 \
  --n-gpu-layers 99 \
  --split-mode none \
  --flash-attn on \
  --fit off \
  --batch-size 512 \
  --ubatch-size 128 \
  --cache-type-k f16 \
  --cache-type-v f16 \
  --temperature 0 \
  --top-k 0 \
  --top-p 1 \
  --min-p 0 \
  --repeat-penalty 1 \
  --seed 42 \
  --reasoning off \
  --reasoning-budget 0 \
  --no-cache-prompt \
  --cache-ram 0 \
  --no-cont-batching \
  --no-mmproj \
  --no-ui \
  --offline \
  --metrics \
  --warmup
