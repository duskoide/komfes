#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
profile=${HARGATURUN_LLM_PROFILE:-text}
model=${HARGATURUN_MODEL_PATH:-"$project_root/models/${HARGATURUN_MODEL_FILE:-hargaturun-qwen3.5-4b-q4_k_m.gguf}"}
projector=${HARGATURUN_MMPROJ_PATH:-"$project_root/models/${HARGATURUN_MMPROJ_FILE:-hargaturun-qwen3.5-mmproj-f16.gguf}"}
port=${HARGATURUN_MODEL_PORT:-8080}
alias=${HARGATURUN_MODEL_NAME:-hargaturun-qwen3.5-4b}

case "$profile" in
  text|multimodal) ;;
  *)
    echo "Unsupported HARGATURUN_LLM_PROFILE: $profile (expected text or multimodal)." >&2
    exit 2
    ;;
esac

if [[ ! -f "$model" ]]; then
  echo "Model not found: $model" >&2
  echo "Set HARGATURUN_MODEL_PATH/HARGATURUN_MODEL_FILE or place the GGUF under models/." >&2
  exit 1
fi

if [[ "$profile" == multimodal && ! -f "$projector" ]]; then
  echo "Multimodal projector not found: $projector" >&2
  echo "Set HARGATURUN_MMPROJ_PATH/HARGATURUN_MMPROJ_FILE or use the text profile." >&2
  exit 1
fi

verify_sha256() {
  local label=$1 path=$2 expected=$3 actual
  if [[ -z "$expected" ]]; then
    printf '%s SHA-256: not verified (set the corresponding *_SHA256 variable)\n' "$label" >&2
    return 0
  fi
  if [[ ! "$expected" =~ ^[[:xdigit:]]{64}$ ]]; then
    echo "$label SHA-256 must be exactly 64 hexadecimal characters." >&2
    exit 2
  fi
  actual=$(sha256sum "$path" | awk '{print $1}')
  if [[ "$actual" != "${expected,,}" ]]; then
    echo "$label SHA-256 mismatch: expected $expected, got $actual" >&2
    exit 1
  fi
  echo "$label SHA-256 verified: $actual"
}

verify_sha256 "Model" "$model" "${HARGATURUN_MODEL_SHA256:-}"
if [[ "$profile" == multimodal ]]; then
  verify_sha256 "Projector" "$projector" "${HARGATURUN_MMPROJ_SHA256:-}"
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

printf 'Starting %s profile=%s\nModel: %s\n' "$server" "$profile" "$model"
if [[ "$profile" == multimodal ]]; then
  printf 'Projector: %s\n' "$projector"
fi
printf 'Endpoint: http://127.0.0.1:%s/v1\n' "$port"

common_args=(
  --model "$model"
  --alias "$alias"
  --host 127.0.0.1
  --port "$port"
  --ctx-size 4096
  --n-predict 350
  --parallel 1
  --n-gpu-layers 99
  --split-mode none
  --flash-attn on
  --fit off
  --batch-size 512
  --ubatch-size 128
  --cache-type-k f16
  --cache-type-v f16
  --temperature 0
  --top-k 0
  --top-p 1
  --min-p 0
  --repeat-penalty 1
  --seed 42
  --reasoning off
  --reasoning-budget 0
  --no-cache-prompt
  --cache-ram 0
  --no-cont-batching
  --no-ui
  --offline
  --metrics
  --warmup
)
if [[ "$profile" == multimodal ]]; then
  common_args+=(--mmproj "$projector")
else
  common_args+=(--no-mmproj)
fi

exec env LD_LIBRARY_PATH="$lib_path" "$server" "${common_args[@]}"
