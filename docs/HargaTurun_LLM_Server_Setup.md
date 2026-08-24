# HargaTurun — LLM Server Setup

> **Scope:** local model inference server only
> **Target machine:** NVIDIA GeForce RTX 4060 Laptop GPU (8 GB VRAM), 20 GB system RAM, Linux
> **Runtime:** CUDA-enabled `llama.cpp` in Docker Compose
> **Model:** evaluated Qwen3.5-4B GGUF `Q4_K_M` (base model is valid for the selected agentic-workflow route; use a fine-tuned artifact only if one is actually trained and evaluated)
> **Not covered:** conversational orchestrator, state validation, evaluation suite, FastAPI, frontend, or the pricing tool

This guide starts one OpenAI-compatible model server at `http://127.0.0.1:8080/v1`. In the full Compose stack, the server is private and FastAPI uses `http://llm-server:8080/v1` over the Compose network; only the API and frontend are loopback-published for local development.

## Serving identity and network boundary

The tested CUDA serving image is
`ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:45047ae940975851c3b195997c91f6bb4add4b941880d94287e5f21ff5a6369a`
(llama.cpp `b10588`, amd64, tested 2026-08-24). Both Compose files pin this
identity. `compose.yml` and `compose.llm.yml` deliberately have no host port
mapping for `llm-server`; do not add a public model port. The standalone
profile is reachable from other Compose services only, while native development
may still use loopback through `scripts/run-llama-server.sh`.


## 1. Resulting topology

```text
Host smoke test or FastAPI
          |
          | HTTP /v1/chat/completions
          v
llama.cpp CUDA server
          |
          +-- Qwen3.5-4B Q4_K_M GGUF
          +-- one inference slot
          +-- 4096-token context
          +-- all model layers on the RTX 4060
```

The server is configured for HargaTurun's short, synchronous, text-only turns. Agent actions and pricing-tool routing live in FastAPI, not inside llama.cpp. The server does not load the vision projector, use the model's 262K maximum context, expose tools directly, or provide a public web UI.

## 2. Profiles and selectable artifacts

Text-only remains the default. The multimodal path is explicitly opt-in because
Qwen3.5 vision requires a matching projector and additional VRAM. The model and
alias are configuration values, so 2B/4B candidates can be swapped without code
changes:

```bash
# Native launcher, text-only default
./scripts/run-llama-server.sh

# Native launcher with a matching projector
HARGATURUN_LLM_PROFILE=multimodal \
HARGATURUN_MODEL_FILE=hargaturun-qwen3.5-4b-q4_k_m.gguf \
HARGATURUN_MMPROJ_FILE=hargaturun-qwen3.5-mmproj-f16.gguf \
./scripts/run-llama-server.sh

# Standalone Compose text profile
HARGATURUN_MODEL_FILE=hargaturun-qwen3.5-2b-q5_k_m.gguf \
docker compose -f compose.llm.yml up llm-server

# Standalone Compose multimodal profile (same model directory, read-only)
docker compose -f compose.llm.yml --profile multimodal up llm-server-mm
```

The full application `compose.yml` remains text-only by design. It uses
`HARGATURUN_MODEL_FILE` and `HARGATURUN_MODEL_NAME`; use the standalone
`multimodal` profile when the image endpoint is being evaluated. Do not run both
standalone services on the same host port.

### Projector artifact provenance

The projector must be exported for the exact base model family and llama.cpp
format. Keep it in the Git-ignored `models/` directory; never commit the large
GGUF or projector. The operator must fill these release-record fields before a
real run (placeholders are deliberately not measurements):

| Field | Value to record |
|---|---|
| Model source URL | `MODEL_SOURCE_URL_TO_RECORD` |
| Model license | `MODEL_LICENSE_TO_RECORD` |
| Model filename | `hargaturun-qwen3.5-4b-q4_k_m.gguf` or selected candidate |
| Model SHA-256 | `MODEL_SHA256_TO_RECORD` |
| Projector source URL | `PROJECTOR_SOURCE_URL_TO_RECORD` |
| Projector license | `PROJECTOR_LICENSE_TO_RECORD` |
| Projector filename | `hargaturun-qwen3.5-mmproj-f16.gguf` or matching export |
| Projector SHA-256 | `PROJECTOR_SHA256_TO_RECORD` |

Set `HARGATURUN_MODEL_SHA256` and, for the multimodal profile,
`HARGATURUN_MMPROJ_SHA256`. The native launcher verifies any supplied 64-digit
hash before starting; unset hashes produce an explicit `not verified` warning.
The Compose full stack verifies the model during its download/init step. For a
projector downloaded or copied by an operator, verify it before startup:

```bash
sha256sum models/hargaturun-qwen3.5-mmproj-f16.gguf
HARGATURUN_MMPROJ_SHA256=<64-hex-digest> \
  docker compose -f compose.llm.yml --profile multimodal up llm-server-mm
```

Use the original provider URL and license for the chosen model/projector (for
example, the relevant Hugging Face Qwen3.5 GGUF repository); do not claim a
license or hash until the exact bytes are recorded.

## 3. Fixed runtime profile

| Setting | Value | Reason |
|---|---:|---|
| Quantization | `Q4_K_M` | Safest quality/memory balance on a laptop GPU that may also drive the display |
| Context | 4096 tokens total | Enough for system prompt, one item, JSON output, and headroom |
| Output ceiling | 350 tokens | SRS limit; normal outputs should target roughly 150–220 tokens |
| Parallel slots | 1 | The MVP is synchronous and single-user |
| GPU layers | All | Avoid slow CPU/GPU layer transfers |
| KV cache | FP16 | Small at 4K context and avoids unnecessary cache quantization |
| Thinking | Disabled | The task needs extraction and concise copy, not chain-of-thought |
| Sampling | Greedy, fixed seed | Static settings for reproducibility |
| Prompt cache | Disabled | Requests are short and independent; avoids cache-dependent variation |
| Vision projector | Disabled by default | Text-only profile does not load `--mmproj`; multimodal explicitly opts in |

A `Q4_K_M` file is currently about 3 GB. Total runtime VRAM will be higher because of CUDA, model metadata, recurrent/KV state, and compute buffers. Measure the final artifact rather than treating file size as VRAM usage.

The standalone Compose file mounts the model directory read-only in both
profiles. The text service has `--no-mmproj`; `llm-server-mm` has a configurable
`--mmproj /models/$HARGATURUN_MMPROJ_FILE` and never uses `--no-mmproj`.

## 4. Host prerequisites

Install these host components using their official instructions for the Linux distribution:

1. A current NVIDIA driver supporting the RTX 4060 Laptop GPU.
2. Docker Engine.
3. Docker Compose plugin (`docker compose`, not the legacy `docker-compose`).
4. NVIDIA Container Toolkit configured for Docker.
5. `curl` for health and API smoke tests.

The host does not need a separate CUDA toolkit for this containerized server. The NVIDIA driver and NVIDIA Container Toolkit are required.

Verify the host:

```bash
nvidia-smi
docker version
docker compose version
docker run --rm --gpus all ubuntu:24.04 nvidia-smi
```

The final command must list the RTX 4060 Laptop GPU from inside the container. Resolve Docker/NVIDIA runtime errors before downloading or loading the model.

For stable laptop performance during tests and demonstrations:

- connect AC power;
- select the laptop's Performance or Turbo profile;
- disable battery saver;
- close games, local AI applications, and other GPU-heavy software;
- provide adequate cooling to avoid sustained thermal throttling.

## 5. Prepare the GGUF artifact

The Compose service expects exactly:

```text
models/hargaturun-qwen3.5-4b-q4_k_m.gguf
```

The `models/` directory is intentionally ignored by Git because model files are too large for the repository.

### 4.1 Use an evaluated artifact

Place the evaluated base or genuinely fine-tuned `Q4_K_M` GGUF at the expected path:

```bash
cp /path/to/evaluated-model.Q4_K_M.gguf models/hargaturun-qwen3.5-4b-q4_k_m.gguf
```

A Transformers directory containing `.safetensors` is not directly loadable by `llama-server`; the server artifact must be GGUF. Record whether the file is base or fine-tuned, its source/license, evaluation report, and SHA-256. Never describe a base file as fine-tuned.

### 4.2 Optional baseline-only download

Before the fine-tuned artifact exists, the following base quant can validate Docker, CUDA, Qwen3.5 support, and the HTTP contract:

```bash
curl --fail --location --progress-bar \
  --output models/hargaturun-qwen3.5-4b-q4_k_m.gguf \
  https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf
```

This downloaded model is an honest base-model artifact. It can be the runtime model for the selected agentic-workflow adaptation route, but it does not by itself prove customization. The submission evidence must demonstrate the implemented orchestrator, state, pricing-tool calls, validators, traces, and baseline comparison.

### 4.3 Record artifact identity

Inspect and hash the chosen file:

```bash
ls -lh models/hargaturun-qwen3.5-4b-q4_k_m.gguf
sha256sum models/hargaturun-qwen3.5-4b-q4_k_m.gguf
```

Record the final SHA-256 value in the release notes or submission documentation. Anyone reproducing the demonstration should use the same bytes, not merely a file with the same name.

## 6. Review the server configuration

The repository provides [`compose.llm.yml`](../compose.llm.yml). Validate its syntax before startup:

```bash
docker compose -f compose.llm.yml config
```

The important effective server arguments are:

```text
--ctx-size 4096
--n-predict 350
--parallel 1
--n-gpu-layers all
--split-mode none
--flash-attn on
--batch-size 512
--ubatch-size 128
--cache-type-k f16
--cache-type-v f16
--temperature 0
--top-k 0
--top-p 1
--min-p 0
--seed 42
--reasoning off
--reasoning-budget 0
--no-cache-prompt
--no-cont-batching
--no-mmproj
--offline
```

`--offline` ensures the runtime does not fetch a model from the internet. The image and GGUF must already be present locally.

## 7. Start the server

Pull the CUDA server image while online:

```bash
docker compose -f compose.llm.yml pull
```

Start the service:

```bash
docker compose -f compose.llm.yml up -d
```

Inspect startup logs:

```bash
docker compose -f compose.llm.yml logs llm-server
```

The logs should confirm all of the following:

- one CUDA device was found;
- the device is the RTX 4060 Laptop GPU;
- the GGUF architecture is recognized as Qwen3.5;
- all model layers are offloaded to CUDA;
- Flash Attention is enabled;
- the configured context is 4096;
- one server slot is available;
- the HTTP server is listening on port 8080.

An unknown `--reasoning`, `--fit`, or Qwen3.5 architecture error indicates an outdated `llama.cpp` image. Pull a current image and retest rather than removing required controls without investigation.

## 8. Check readiness

Loading can take time. Poll the health endpoint until it returns HTTP 200:

```bash
curl --fail --silent --show-error http://127.0.0.1:8080/health
```

Expected body:

```json
{"status":"ok"}
```

Confirm the OpenAI-compatible alias:

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:8080/v1/models | python3 -m json.tool
```

The returned model ID should be:

```text
hargaturun-qwen3.5-4b
```

## 9. Run an inference smoke test

This request verifies CUDA inference, non-thinking mode, greedy sampling, and schema-constrained JSON. It does not verify that the model has been fine-tuned successfully; model quality belongs in the held-out evaluation.

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON' | python3 -m json.tool
{
  "model": "hargaturun-qwen3.5-4b",
  "messages": [
    {
      "role": "system",
      "content": "Anda adalah komponen bahasa HargaTurun. Ekstrak fakta yang tersedia dari input UMKM dan tulis penjelasan serta pratinjau promosi singkat dalam Bahasa Indonesia. Jangan menghitung diskon, harga rekomendasi, pendapatan, atau kerugian."
    },
    {
      "role": "user",
      "content": "roti tawar 10 biji exp 2 hari harga 15rb modal 10rb toko sari bakery"
    }
  ],
  "temperature": 0,
  "top_k": 0,
  "top_p": 1,
  "min_p": 0,
  "repeat_penalty": 1,
  "seed": 42,
  "max_tokens": 350,
  "stream": false,
  "reasoning_effort": "none",
  "chat_template_kwargs": {
    "enable_thinking": false
  },
  "response_format": {
    "type": "json_schema",
    "schema": {
      "type": "object",
      "properties": {
        "parsed_input": {
          "type": "object",
          "properties": {
            "item_name": { "type": "string" },
            "category": {
              "type": "string",
              "enum": [
                "Bakery",
                "Prepared Food",
                "Dairy",
                "Beverage",
                "Produce",
                "Snack",
                "Canned",
                "Other"
              ]
            },
            "original_price": { "type": "integer" },
            "cost": { "type": "integer" },
            "stock": { "type": "integer" },
            "days_remaining": { "type": "number" },
            "shop_name": { "type": ["string", "null"] }
          },
          "required": [
            "item_name",
            "category",
            "original_price",
            "cost",
            "stock",
            "days_remaining",
            "shop_name"
          ],
          "additionalProperties": false
        },
        "explanation": { "type": "string" },
        "promo_copy": { "type": "string" }
      },
      "required": ["parsed_input", "explanation", "promo_copy"],
      "additionalProperties": false
    }
  }
}
JSON
```

A successful response has HTTP 200 and places the generated JSON string in:

```text
choices[0].message.content
```

The response also includes timing information in `timings`. Record prompt and generation throughput during hardware validation.

## 10. Request contract for FastAPI

When the application is added to the same Compose project, FastAPI should use:

```text
LLM_BASE_URL=http://llm-server:8080/v1
LLM_MODEL=hargaturun-qwen3.5-4b
```

Keep the model server private to the Compose network in the full application. The loopback host mapping in `compose.llm.yml` exists for this standalone setup and local smoke tests; it must not be changed to a public `0.0.0.0:8080:8080` host binding.

FastAPI must send these values on every generation request because request parameters can override server defaults:

```json
{
  "temperature": 0,
  "top_k": 0,
  "top_p": 1,
  "min_p": 0,
  "repeat_penalty": 1,
  "seed": 42,
  "max_tokens": 350,
  "reasoning_effort": "none",
  "chat_template_kwargs": {
    "enable_thinking": false
  }
}
```

FastAPI must also send the production JSON Schema, validate the returned content with Pydantic, and retry once if parsing or validation fails. Schema-constrained generation guarantees syntax, not semantic correctness. The deterministic Python pricing engine remains the sole authority for all prices, discounts, projections, timing, and safety limits.

## 11. Monitor resource use

In another terminal, observe VRAM, GPU utilization, temperature, and power while running several requests:

```bash
watch -n 0.5 nvidia-smi
```

For the final `Q4_K_M` artifact, target a peak below approximately 6.5 GiB so the laptop display and temporary allocations retain 1–1.5 GiB of headroom. This is an operational target, not a guaranteed estimate.

Inspect server metrics:

```bash
curl --fail --silent --show-error http://127.0.0.1:8080/metrics
```

The most useful values are prompt tokens/second, predicted tokens/second, active requests, and the maximum observed context usage.

## 12. Acceptance checks

Do not lock the image, model, or settings until all checks pass with the exact submission GGUF:

- [ ] `/health` returns HTTP 200 after startup.
- [ ] Startup logs identify CUDA and Qwen3.5 correctly.
- [ ] All model layers are GPU-offloaded.
- [ ] Peak VRAM remains below the chosen safety threshold.
- [ ] The production prompt plus maximum output fits within 4096 tokens.
- [ ] Thinking content never appears in `message.content`.
- [ ] The model produces valid production-schema JSON on the held-out set.
- [ ] Repeated requests preserve parsed values under static settings.
- [ ] P95 end-to-end latency is below 10 seconds on AC power and the declared laptop profile.
- [ ] Fifty sequential requests complete without OOM or a container restart.
- [ ] The server starts and runs with network access unavailable after initial setup.
- [ ] The final model SHA-256 and server image digest are recorded.

Use `/v1/chat/completions/input_tokens` with the production request body to measure the actual prompt before increasing or reducing context size.

## 13. Readiness, smoke tests, and measurements

Static profile checks run without Docker:

```bash
cd backend
uv run pytest -q tests/test_model_server_profiles.py
```

The opt-in readiness test covers the text endpoint and, when
`HARGATURUN_TEST_MULTIMODAL=1`, a separate multimodal endpoint. One local image
request is sent only with both flags enabled; absent services skip cleanly unless
`HARGATURUN_STRICT_MODE=1`:

```bash
# Text readiness/parse/write smoke (server already running)
python scripts/run_dev_tests.py --real-model

# Add multimodal readiness plus one image request against the --mmproj server
HARGATURUN_MULTIMODAL_MODEL_URL=http://127.0.0.1:8080/v1 \
python scripts/run_dev_tests.py --real-model --multimodal

# Compose config, if Docker/Podman is installed
python scripts/run_dev_tests.py --compose
```

For warm measurements, run the script against a ready text or multimodal
endpoint. It prints P50/P95 request latency and samples peak VRAM with
`nvidia-smi` when available; it prints `unavailable` rather than fabricating a
value when the server/GPU cannot be observed:

```bash
python scripts/measure_llm_latency.py --url http://127.0.0.1:8080/v1 --count 20 --warmup 2
python scripts/measure_llm_latency.py --url http://127.0.0.1:8080/v1 --image --count 20 --warmup 2
```

Run these separately against text and multimodal services because both profiles
use port 8080. Preserve the command output with the declared hardware, model
and projector hashes only after a real run; no latency or VRAM result is stored
in this repository by default.

## 14. Pin the tested server image

The initial Compose file uses the floating `server-cuda` tag so current Qwen3.5 support can be validated. A floating image can change after testing, so pin its repository digest before proof-of-work recording and submission.

After pulling and testing, inspect the digest:

```bash
docker image inspect \
  --format '{{index .RepoDigests 0}}' \
  ghcr.io/ggml-org/llama.cpp:server-cuda
```

Replace the `image:` value in `compose.llm.yml` with the returned `ghcr.io/...@sha256:...` value, then rerun the complete acceptance checklist.

## 15. Stop, restart, and inspect

Stop the server without deleting the local model:

```bash
docker compose -f compose.llm.yml down
```

Restart it:

```bash
docker compose -f compose.llm.yml up -d
```

Show service status:

```bash
docker compose -f compose.llm.yml ps
```

Show recent logs:

```bash
docker compose -f compose.llm.yml logs --since 10m llm-server
```

Run without pulling anything after the image and model are cached:

```bash
docker compose -f compose.llm.yml up -d --pull never
```

## 16. Troubleshooting

### Docker cannot access the GPU

Symptoms include `could not select device driver`, `no compatible GPU`, or a CPU-only startup log.

1. Confirm `nvidia-smi` works on the host.
2. Rerun `docker run --rm --gpus all ubuntu:24.04 nvidia-smi`.
3. Reconfigure or reinstall NVIDIA Container Toolkit for Docker.
4. Restart the Docker daemon as required by the host distribution.

Do not continue with CPU inference and assume the latency target has been validated.

### Model file not found

Confirm the exact case-sensitive path:

```bash
ls -l models/hargaturun-qwen3.5-4b-q4_k_m.gguf
```

The Compose mount is read-only and maps the repository's `models/` directory to `/models` in the container.

### CUDA out of memory

1. Close other GPU applications and inspect display VRAM use.
2. Confirm the artifact is `Q4_K_M`, not Q8 or BF16.
3. Keep `--parallel 1` and `--ctx-size 4096`.
4. Reduce `--batch-size` from 512 to 256.
5. Reduce `--ubatch-size` from 128 to 64.
6. Only reduce context to 3072 after measuring the production prompt and proving it still fits.

Do not solve a normal Q4 memory problem by silently offloading layers to CPU; investigate the unexpected VRAM consumer first.

### Inference is slower than expected

1. Confirm AC power and the Performance/Turbo profile.
2. Check the startup log for full CUDA offload and Flash Attention.
3. Observe GPU power, utilization, and thermal throttling with `nvidia-smi`.
4. Keep thinking disabled and outputs concise.
5. Measure warmed requests; do not use the first cold request as the only benchmark.
6. Test `--ubatch-size 256` only after the stable baseline works, reverting if memory or reliability worsens.

Laptop RTX 4060 power limits vary significantly, so VRAM capacity alone cannot predict tokens/second.

### Thinking text appears

Confirm both startup controls are present:

```text
--reasoning off
--reasoning-budget 0
```

Also confirm each request sends:

```json
{
  "reasoning_effort": "none",
  "chat_template_kwargs": { "enable_thinking": false }
}
```

If the problem persists, inspect `/apply-template`, verify that the exported GGUF retained the correct Qwen3.5 chat template, and update to a tested `llama.cpp` image.

### JSON is malformed or semantically wrong

- Always send `response_format` with the production JSON Schema.
- Validate `choices[0].message.content` with Pydantic.
- Retry once on malformed output, as required by the SRS.
- Treat missing or ambiguous economic fields as `needs_confirmation`.
- Fix semantic quality through the prompt, training data, or fine-tuning—not through pricing post-processing.
- Never accept model-generated arithmetic as authoritative.

### The server starts downloading files

The provided configuration uses a local `--model` path and `--offline`. Confirm the active configuration with:

```bash
docker compose -f compose.llm.yml config
```

Do not pass `--hf-repo`, `--model-url`, or authentication tokens to the runtime service.

## 17. Optional quantization comparison

Only after the stable `Q4_K_M` path passes all acceptance checks, compare a `Q5_K_M` export using the same prompts and held-out evaluation. It is likely to fit in 8 GB at a 4K single-slot configuration, but the decision must be based on measured parsing accuracy, JSON compliance, latency, and peak VRAM.

Do not use Q8 or BF16 for the target laptop. Do not enable multiple slots, 128K context, multimodal projection, vLLM, or speculative decoding merely because the model supports them; none is necessary for the preliminary MVP.
