# HargaTurun — Fine-Tuning Plan & Runbook

> **Document type:** engineering runbook + proposal methodology source  
> **Competition:** COMPFEST 18 AIC — model must be genuinely fine-tuned  
> **Version:** 1.1  
> **Status:** design corrected; scripts and measured results still required

---

## 1. Decisions and constraints

### 1.1 Model responsibility

HargaTurun uses a hybrid architecture:

- **Qwen3.5-4B:** parse colloquial Indonesian and write Indonesian explanation/promo text.
- **Deterministic Python pricing engine:** validate confirmed inputs and compute every discount, price, timing, projection, warning, and `no_action` result.

The model must never invent or calculate discount percentages, recommended prices, revenue, loss, sell-through, timing, or safety outcomes.

### 1.2 Two explicit model tasks

Do not ask the model to parse input and justify an oracle result that it has not seen. Train two task modes instead:

1. **`parse`** — free text → `parsed_input`, `missing_fields`, and `needs_confirmation`.
2. **`write`** — confirmed normalized input plus the pricing-engine result → qualitative `explanation` and `promo_copy`.

One browser submission remains one synchronous product interaction. Internally:

```text
Free text:
  model(parse) -> validate/confirm -> pricing engine -> model(write) -> response

Structured input:
  validate -> pricing engine -> model(write) -> response
```

If required values are missing, the API returns confirmation immediately and does not call the pricing engine or writer.

### 1.3 Hardware and training-method decision

The target laptop has an RTX 4060 Laptop GPU with 8 GB VRAM. It is suitable for Qwen3.5-4B GGUF inference, but it is **not the declared training target**.

Current Unsloth guidance states:

- Qwen3.5-4B BF16 LoRA uses about 10 GB VRAM;
- QLoRA/4-bit training is not recommended for Qwen3.5 because quantization differences are higher than normal;
- Transformers v5 is required.

Therefore:

- **Training method:** BF16 LoRA, not QLoRA.
- **Training environment:** GPU with at least 12 GB usable VRAM; 16 GB is preferred. Use a suitable cloud/Colab GPU if needed.
- **Laptop role:** base-model baseline evaluation, final GGUF evaluation, local serving, and demo.
- **Fallback:** do not silently switch to QLoRA. If BF16 LoRA cannot be run, record the blocker and secure a larger training environment.

### 1.4 Existing local artifacts

The installed base Qwen3.5-4B `Q4_K_M` and `Q8_0` GGUF files are useful for baseline inference and quantization comparison. They are not trainable Unsloth checkpoints and are not evidence of fine-tuning.

Before evaluation, copy or symlink them to stable paths and record their identities:

```bash
mkdir -p models/baseline
cp /actual/path/Qwen3.5-4B-Q4_K_M.gguf models/baseline/qwen3.5-4b-q4_k_m.gguf
cp /actual/path/Qwen3.5-4B-Q8_0.gguf   models/baseline/qwen3.5-4b-q8_0.gguf
sha256sum models/baseline/*.gguf
```

Do not overwrite these files with fine-tuned exports. Final artifacts use `models/finetuned/`.

---

## 2. Model contracts

### 2.1 Parse task

**Input:** one Indonesian free-text item description.

**Output:** JSON only:

```json
{
  "task": "parse",
  "parsed_input": {
    "item_name": "roti tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 10,
    "days_remaining": 2,
    "daily_sales": null,
    "total_shelf_life": null,
    "shop_name": "toko sari bakery"
  },
  "missing_fields": ["daily_sales", "total_shelf_life"],
  "needs_confirmation": true
}
```

Allowed categories are `Bakery`, `Prepared Food`, `Dairy`, `Beverage`, `Produce`, `Snack`, `Canned`, and `Other`.

Rules:

- Preserve explicit values exactly after deterministic unit normalization (`15rb` → `15000`, `besok` → `1`).
- Use `null` when a value is missing or ambiguous; never infer economic facts.
- `daily_sales` is required and must be supplied or confirmed by the owner.
- `total_shelf_life` is required; a category default may be proposed by the backend but must be disclosed and confirmed.
- `needs_confirmation` is true when any required field is missing or ambiguous.
- The model does not emit an explanation, promo text, recommendation, or clarifying prose in this task.

Required parse fields are:

```text
item_name, category, original_price, cost, stock, days_remaining,
daily_sales, total_shelf_life
```

`shop_name` is optional.

### 2.2 Write task

**Input:** confirmed normalized input and the complete deterministic engine result. For example:

```json
{
  "task": "write",
  "normalized_input": {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 10,
    "days_remaining": 2,
    "daily_sales": 5,
    "total_shelf_life": 4,
    "shop_name": "Toko Sari Bakery"
  },
  "engine_result": {
    "status": "recommendation",
    "discount_percent": 30,
    "recommended_price": 10500,
    "timing": "Mulai diskon hari ini",
    "expected_sell_through": "8 dari 10 pcs",
    "expected_revenue": 84000,
    "expected_loss_no_action": 50000,
    "confidence": "Cukup yakin"
  }
}
```

**Output:** JSON only:

```json
{
  "task": "write",
  "explanation": "Roti tawar mendekati batas jual sementara stoknya belum tentu habis pada laju penjualan saat ini. Rekomendasi harga dari sistem membantu mempercepat penjualan tanpa melewati batas margin yang ditetapkan.",
  "promo_copy": "🍞 Roti Tawar hemat 30% hari ini, hanya Rp10.500! Stok terbatas di Toko Sari Bakery."
}
```

Rules:

- Treat `engine_result` as authoritative; do not recalculate or alter it.
- Copy numerical claims only from `engine_result` or `normalized_input`.
- Generate status-appropriate language for `recommendation`, `no_action`, or `warning`.
- The explanation is 2–4 concise Indonesian sentences.
- Promo copy is 1–2 Indonesian sentences and must not claim a promotion for `no_action` or `warning`.

### 2.3 Why these tasks are separate

The old single-pass target asked the model to decide whether a discount was needed before it received the engine result. That implicitly trained pricing logic into the model and could contradict the deterministic engine. The two-task contract makes the boundary testable and prevents conflicting recommendations.

---

## 3. Dataset design

### 3.1 Dataset units

Generate a canonical **scenario** first. Each scenario has a stable `scenario_id`, normalized values, and an engine result. Derive examples from that scenario only after assigning its split.

```json
{
  "scenario_id": "bakery-000123",
  "split": "train",
  "normalized_input": {},
  "engine_result": {}
}
```

A scenario can create:

- 2–3 parse examples with different free-text variants;
- missing/ambiguous parse variants where appropriate;
- one or more write examples for the engine result.

Report both **scenario count** and **example count**. Never call augmented variants independent scenarios.

### 3.2 Leakage-safe split

Split by `scenario_id` **before** paraphrasing or template expansion:

```text
80% train / 10% validation / 10% synthetic test
```

All variants of one scenario must remain in one split. Add an automated assertion that the three scenario-ID sets are disjoint.

Also maintain `data/gold_test.jsonl`: at least 200 manually authored or manually verified examples that are not produced by the training generator or its templates. It should cover all categories, common slang, missing fields, ambiguous units, status types, and difficult numeric forms.

The gold test set is the primary pre/post comparison. The synthetic validation set is for training diagnostics, not the final quality claim.

### 3.3 Exact value generation

Generate values that can be represented exactly in their rendered input. Never truncate a source value while keeping the untruncated label.

```python
original_price = random.randrange(2_000, 150_001, 500)
cost = random.randrange(1_000, original_price + 1, 500)
stock = random.randint(1, 100)
days_remaining = random.randint(0, max_days)
daily_sales = random.randint(1, 50)
total_shelf_life = CATEGORY_SHELF_LIFE[category]
```

Use deterministic reversible renderers:

```python
def render_rupiah(value: int, style: str) -> str:
    if style == "full":
        return str(value)
    if style == "rb" and value % 1_000 == 0:
        return f"{value // 1_000}rb"
    return str(value)  # never round or truncate


def render_days(value: int) -> str:
    return {0: "hari ini", 1: "besok"}.get(value, f"{value} hari")
```

Generator validation must parse each rendered variant with the deterministic normalization helpers and assert that every explicit value round-trips to its label.

### 3.4 Parse-data coverage

Include:

- `rb`, `ribu`, `k`, decimal `jt`, dots, and plain Rupiah where exactly representable;
- `pcs`, `biji`, `buah`, `porsi`, and omitted units;
- `hari ini`, `besok`, `lusa`, explicit dates where supported, and integer day counts;
- spelling variants such as `exp`, `expired`, `kadaluarsa`, and `kedaluwarsa`;
- reordered phrases, multiline form-like text, punctuation noise, and casing differences;
- explicitly missing `cost`, `daily_sales`, `total_shelf_life`, and other required fields;
- genuinely ambiguous values whose target is `null` plus `needs_confirmation: true`.

Do not train the model to guess a category, cost, sales rate, or shelf life from insufficient evidence.

### 3.5 Write-data coverage

Generate writing targets only after the production pricing function returns an engine result. Cover:

- normal recommendation;
- `no_action`;
- expired item warning;
- zero/negative-margin warning;
- invalid-input warning;
- low and high confidence;
- every product category and urgency band.

Template-generated prose is acceptable for an initial dataset, but manually review a stratified sample and avoid repeating a tiny set of sentence skeletons. Any LLM-assisted augmentation must be reviewed, provenance-tagged, and must not introduce unsupported numbers.

### 3.6 Dataset quality gates

The generator must fail before writing final files if any check fails:

1. JSON parses and validates against the task schema.
2. Scenario IDs do not overlap between splits.
3. Explicit rendered numbers round-trip exactly.
4. Parse targets contain no recommendation fields.
5. Write inputs contain a recorded engine result.
6. Write outputs contain no number absent from their input.
7. Required edge-case quotas and category quotas are met.
8. A fixed seed reproduces scenario IDs and labels.

---

## 4. Baseline and evaluation

### 4.1 Evaluation order

Run the same frozen test harness and prompts against:

1. base Q8_0 GGUF — highest-quality local baseline;
2. base Q4_K_M GGUF — deployment-quant baseline;
3. BF16 LoRA adapter or merged model — pre-quantization fine-tuned result;
4. fine-tuned Q8_0 GGUF — export check;
5. fine-tuned Q4_K_M GGUF — final deployment candidate.

This separates fine-tuning gain from quantization loss. Record artifact SHA-256, prompt version, chat template, llama.cpp build, seed, and decoding settings with every run.

### 4.2 Parse metrics

Measure on the frozen gold test set:

| Metric | Required gate |
|---|---:|
| Valid JSON and schema | ≥99% |
| Accuracy per required field | ≥95% |
| Complete-record exact match | ≥90% |
| Missing/ambiguous-field recall | ≥95% |
| False completion rate | ≤2% |

`False completion` means `needs_confirmation: false` when a required field is absent or ambiguous. It is a safety-critical failure and must not be hidden inside an average.

### 4.3 Write metrics

On at least 100 stratified gold cases, reviewers score:

- faithfulness to engine status and numbers;
- Indonesian clarity;
- promo appropriateness;
- unsupported numerical claims;
- whether `no_action`/warning cases incorrectly advertise a discount.

Required gates:

| Metric | Required gate |
|---|---:|
| Engine-status faithfulness | ≥98% |
| Unsupported numerical claims | 0 |
| Mean clarity score (1–5) | ≥4.0 |
| Inappropriate promo on no-action/warning | 0 |

Use at least two reviewers for a smaller adjudicated subset and document the rubric. Do not report “would click” as objective accuracy.

### 4.4 End-to-end engine metrics

`no_action`, margin floors, expired-item behavior, discount bounds, and deterministic pricing are pricing-engine/API tests—not model metrics. Test them separately against the SRS acceptance cases.

### 4.5 Acceptance decision

Fine-tuning is accepted only if all mandatory parse/write gates pass and:

- complete-record exact match improves by at least 5 percentage points over the matching base-model format, or the base already passes every gate and fine-tuning causes no material regression;
- final Q4_K_M stays within 2 percentage points of the fine-tuned Q8_0 result on complete-record accuracy;
- final Q4_K_M passes all safety and faithfulness gates;
- results are measured, saved, and reproducible.

Valid JSON alone is never sufficient.

---

## 5. BF16 LoRA training configuration

### 5.1 Initial configuration

Use a conservative first run and change one variable at a time:

| Parameter | Initial value |
|---|---:|
| Base checkpoint | `unsloth/Qwen3.5-4B` |
| Precision | BF16 LoRA (`load_in_4bit=False`, `load_in_16bit=True`) |
| LoRA rank / alpha | 16 / 16 |
| Target modules | `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj` |
| LoRA dropout | 0 |
| Batch size | 1 |
| Gradient accumulation | 8 |
| Effective batch | 8 |
| Max sequence length | 1024 initially |
| Learning rate | `2e-4` initial experiment |
| Epochs | 1 initial experiment; continue only from validation evidence |
| Optimizer | `adamw_8bit` |
| Gradient checkpointing | `unsloth` |
| Seed | 3407 |

Do not choose rank or dataset size solely from baseline accuracy. Increase rank, epochs, or examples only after diagnosing a specific error pattern and checking validation loss/quality.

### 5.2 Environment preflight

Use the environment in which Unsloth was installed; do not assume the system `python` points to it.

```bash
command -v unsloth
command -v python
python -c 'import unsloth, transformers, trl, torch; print(unsloth.__file__); print(transformers.__version__); print(trl.__version__); print(torch.__version__); print(torch.cuda.get_device_name())'
nvidia-smi
```

Record the output in the training report. Confirm Transformers major version 5 and a GPU with at least 12 GB usable VRAM before loading Qwen3.5-4B BF16.

The actual lock file or environment export must pin the versions that pass the smoke run. Do not retain the old CUDA-12.1/Torch-2.4 installation command as a universal recipe.

### 5.3 Required smoke run

Before a full run:

1. Build 20 train, 10 validation, and 20 gold-test examples covering both tasks.
2. Validate all dataset quality gates.
3. Run 10 training steps.
4. Save and reload the adapter.
5. Evaluate at least one parse and one write example.
6. Export Q8_0 and Q4_K_M GGUFs.
7. Run both through the same llama.cpp chat template used by evaluation.
8. Record peak VRAM and wall-clock time.

Only then approve the full run. Compilation of Qwen3.5 custom kernels may make first startup slower than later runs.

### 5.4 Training-data formatting

Convert each chat example to the tokenizer's exact chat template before SFT and ensure the trainer receives a `text` field. Do not assume raw `messages` will be formatted automatically across TRL versions.

Mask or otherwise exclude user/system tokens from loss if the verified trainer configuration supports it; document the choice. Preserve the same chat template and EOS behavior during adapter, merged, and GGUF evaluation.

### 5.5 Full-run procedure

The scripts below are deliverables and must exist before these commands are advertised as runnable:

```bash
python scripts/generate_training_data.py --seed 3407 --output-dir data
python scripts/validate_training_data.py --data-dir data
python scripts/eval_model.py --backend llama-cpp --model models/baseline/qwen3.5-4b-q8_0.gguf --suite data/gold_test.jsonl --report reports/base-q8.json
python scripts/eval_model.py --backend llama-cpp --model models/baseline/qwen3.5-4b-q4_k_m.gguf --suite data/gold_test.jsonl --report reports/base-q4.json
python scripts/train.py --config configs/train-qwen35-4b-lora.yaml
python scripts/eval_model.py --backend unsloth --model models/finetuned/hargaturun-lora --suite data/gold_test.jsonl --report reports/adapter.json
```

Until those files exist and pass `--help` plus the smoke run, this section is a required interface—not a claim that the repository is training-ready.

---

## 6. Export and local serving

### 6.1 Export both comparison artifacts

Export directly from the loaded fine-tuned model using Unsloth's supported API:

```python
model.save_pretrained_gguf(
    "models/finetuned/hargaturun-qwen3.5-4b-q8_0",
    tokenizer,
    quantization_method="q8_0",
)
model.save_pretrained_gguf(
    "models/finetuned/hargaturun-qwen3.5-4b-q4_k_m",
    tokenizer,
    quantization_method="q4_k_m",
)
```

Do not use the old export snippet that accepted `--output` but ignored it. Keep adapters, merged/pre-quantization output, GGUFs, training config, logs, hashes, and reports as fine-tuning evidence.

### 6.2 Serving profile

The final local server uses the fine-tuned Q4_K_M artifact and the exact chat template used in evaluation. Follow `HargaTurun_LLM_Server_Setup.md` for Docker and llama.cpp details.

For deterministic competition inference, use fixed decoding settings and disable thinking. Treat deterministic settings as a product constraint even if the model vendor's general-chat recommendation uses sampling.

### 6.3 Artifact promotion

Promote a model to the serving path only after evaluation:

```bash
cp models/finetuned/hargaturun-qwen3.5-4b-q4_k_m/*.gguf \
   models/hargaturun-qwen3.5-4b-q4_k_m.gguf
sha256sum models/hargaturun-qwen3.5-4b-q4_k_m.gguf
```

Adjust the source glob to the actual Unsloth export filename. Never present a base GGUF copied to this path as the fine-tuned competition artifact.

---

## 7. Failure handling and iteration

| Failure | First diagnosis | Corrective action |
|---|---|---|
| JSON/schema failures | Prompt/chat-template mismatch | Verify template and EOS first; then add targeted examples |
| Incorrect explicit numbers | Generator or normalization bug | Fix labels/renderer; do not compensate with more training |
| Missing-field false completion | Inadequate ambiguity examples | Add targeted missing/ambiguous parse cases |
| Writer contradicts engine | Task contamination or weak write prompt | Verify task separation; add status-faithful write cases |
| Adapter good, GGUF bad | Quantization/template mismatch | Compare Q8_0, Q4_K_M, template, and EOS |
| Overfitting | Validation worsens while train loss falls | Stop earlier or diversify data |
| BF16 OOM | Training GPU below requirement | Use a larger GPU; reduce sequence/batch only after confirming model load fits |

Do not use rank increases as the default fix for every error. Correct data and contract errors before tuning hyperparameters.

---

## 8. Proposal methodology mapping

### 8.1 Dataset acquisition

> Dataset utama dibuat secara sintetik dari skenario UMKM yang memiliki ID stabil. Skenario dibagi ke train, validation, dan test sebelum parafrase dibuat sehingga variasi dari satu skenario tidak bocor antar-split. Input kolokial dan target parsing divalidasi dengan round-trip numerik. Evaluasi akhir menggunakan sedikitnya 200 contoh gold yang ditulis atau diverifikasi manual dan tidak dihasilkan oleh template training.

### 8.2 Model development

> Qwen3.5-4B di-fine-tune menggunakan BF16 LoRA melalui Unsloth pada GPU dengan memori yang memadai. QLoRA tidak digunakan karena panduan Unsloth saat ini tidak merekomendasikan training 4-bit untuk Qwen3.5. Model mempelajari dua task eksplisit: parsing input ke field terstruktur dan penulisan teks berdasarkan hasil pricing engine. Seluruh perhitungan harga tetap dilakukan oleh Python secara deterministik.

### 8.3 Integration

> Untuk input bebas, backend memanggil task parse, meminta konfirmasi jika field wajib belum tersedia, menjalankan pricing engine setelah data lengkap, lalu memanggil task write dengan hasil engine. Model hasil fine-tuning diekspor ke Q8_0 untuk pemeriksaan kualitas dan Q4_K_M untuk serving lokal melalui llama.cpp. Satu interaksi pengguna tetap sinkron meskipun backend dapat melakukan dua inferensi model.

### 8.4 Data-driven decisions

> Base Q8_0 dan Q4_K_M dievaluasi pada gold test yang sama sebelum training. Adapter BF16, hasil export Q8_0, dan hasil export Q4_K_M kemudian dibandingkan dengan prompt, chat template, dan decoding yang dibekukan. Model hanya dipromosikan jika lolos seluruh gate parsing, missing-field safety, faithfulness, dan quantization regression; JSON valid saja tidak dianggap cukup.

Do not copy target percentages into the proposal as achieved results until the reports exist.

---

## 9. Deliverables and execution order

| Order | Deliverable | Exit condition |
|---:|---|---|
| 1 | Production `pricing.py` + tests | All SRS arithmetic/safety cases pass |
| 2 | Frozen parse/write schemas and prompts | API/SRS contract review passes |
| 3 | Gold test set | ≥200 reviewed examples, no generator provenance |
| 4 | Dataset generator + validator | All §3.6 gates pass |
| 5 | Base Q8_0 and Q4_K_M reports | Same harness/config, hashes recorded |
| 6 | 10-step BF16 LoRA smoke run | Save/reload/export/inference succeeds |
| 7 | Full training run | Config, logs, adapters, and environment recorded |
| 8 | Adapter/Q8_0/Q4_K_M reports | All §4 gates pass |
| 9 | Final local server smoke test | Fine-tuned artifact hash and API result recorded |

The next implementation priority is the frozen schemas, gold-test format, dataset generator validation, and baseline evaluator—not a full training run.

---

## References

- Unsloth Qwen3.5 fine-tuning guide: <https://unsloth.ai/docs/models/qwen3.5/fine-tune>
- Unsloth Qwen3.5 inference guide: <https://unsloth.ai/docs/models/qwen3.5>
- Local llama.cpp setup: `docs/HargaTurun_LLM_Server_Setup.md`
- Preliminary product contract: `docs/HargaTurun_Penyisihan_SRS.md`

*This is a living runbook. Update version pins, measured VRAM, artifact hashes, and evaluation results from actual runs; do not replace evidence with estimates.*
