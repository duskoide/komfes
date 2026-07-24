# HargaTurun — Fine-Tuning Plan & Runbook

> **Document type:** Engineering runbook + Proposal methodology source
> **Competition:** COMPFEST 18 AIC — "model wajib di-fine tune"
> **Version:** 1.0

---

## 1. Objective & Scope

### 1.1 What Fine-Tuning Achieves

Given the **hybrid architecture** (Project Spec §9.2), the model's job is narrow:
- **NLU:** Parse colloquial Indonesian input → structured `parsed_input` JSON
- **NLG:** Generate `explanation` (business-facing reasoning) + `promo_copy` (consumer-facing marketing text)

The model does **NOT** compute pricing, revenue projections, or discount percentages. That is the Python pricing engine's job (oracle formula, Project Spec §9.5).

### 1.2 Why Fine-Tune (vs. Zero-Shot Prompting)

| Benefit | Impact |
|---|---|
| **Output consistency** | Near-100% valid JSON schema compliance vs. ~85-90% with prompting |
| **Colloquial robustness** | Handles "exp", "rb", "biji", "besok", slang variants reliably |
| **Shorter prompts** | No need for 5-shot examples in every request → lower latency |
| **Competition compliance** | Satisfies "model wajib di-fine tune" rule |

### 1.3 Fine-Tuning Intensity (Scaled to Baseline Gap)

Run `scripts/baseline_eval.py` first. Adjust fine-tuning effort based on results:

| Baseline Accuracy | Strategy | Data Size | LoRA Rank | Epochs |
|---|---|---|---|---|
| ≥85% | Light (consistency lock) | 2,000–3,000 | 16 | 1–2 |
| 60–85% | Standard | 4,000–5,000 | 32 | 2 |
| <60% | Full | 5,000–8,000 | 64 | 2–3 |

---

## 2. Base Model & Tooling

### 2.1 Model Selection

**Base model:** `unsloth/Qwen3.5-4B` (Unsloth's optimized loader for fast QLoRA)

| Attribute | Value |
|---|---|
| Parameters | 4B |
| Languages | 201 (incl. Bahasa Indonesia) |
| Context window | 262K tokens (we use ~1K max) |
| Architecture | Transformer decoder-only, multimodal (vision unused in MVP) |
| Quantization (training) | 4-bit NF4 (QLoRA) |
| Quantization (inference) | Q4_K_M GGUF for llama.cpp |

**Why Qwen3.5-4B?** See Project Spec §9.1 — Indonesian fluency, right-sized, mature tooling, built-in vision for future OCR.

### 2.2 Tooling

| Tool | Purpose |
|---|---|
| **Unsloth** | Fast QLoRA training (1.5× faster, 50% less VRAM than FA2) |
| **TRL (SFTTrainer)** | Supervised fine-tuning on chat-format data |
| **bitsandbytes** | 4-bit quantization for QLoRA |
| **llama.cpp** | GGUF export + inference serving |

**Installation:**
```bash
pip install "unsloth[cu121-torch240] @ git+https://github.com/unslothai/unsloth.git"
pip install trl bitsandbytes accelerate datasets
```

---

## 3. What the Model Learns (and Doesn't)

### 3.1 Training Targets

The model learns to produce **three outputs** from one input:

```json
{
  "parsed_input": {
    "item_name": "roti tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 10,
    "days_remaining": 2,
    "shop_name": "toko sari bakery"
  },
  "explanation": "Roti tawar termasuk cepat basi. Dengan sisa 2 hari dan stok 10 pcs, perlu diskon agar tidak terbuang. Kategori bakery sangat sensitif harga, pembeli cenderung membeli jika ada potongan.",
  "promo_copy": "🍞 Roti tawar fresh dari Toko Sari Bakery! Stok terbatas, buruan sebelum habis. Diskon spesial untuk Anda!"
}
```

### 3.2 What the Model Does NOT Learn

- ❌ Discount percentage calculation (Python oracle)
- ❌ Recommended price computation (Python oracle)
- ❌ Revenue/loss projections (Python oracle)
- ❌ Timing recommendation logic (Python oracle)
- ❌ Sell-through estimation (Python oracle)

These are **injected by Python** at inference time. The model's `explanation` and `promo_copy` are **qualitative** (reference days, stock, category perishability) but do not contain specific figures like "30% OFF" or "Rp10.500" — those are added by the API layer after oracle computation.

### 3.3 Training Data Schema

Each training example is a chat message:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "Anda adalah asisten HargaTurun untuk UMKM makanan Indonesia.\n\nTugas: baca input pemilik usaha (form terstruktur atau teks bebas sehari-hari), hasilkan JSON dengan tiga bagian:\n\n1. \"parsed_input\": objek dengan field:\n   - item_name (string)\n   - category (salah satu: Bakery, Prepared Food, Dairy, Beverage, Produce, Snack, Canned, Other)\n   - original_price (integer, Rupiah. \"15rb\"=15000, \"1.5jt\"=1500000)\n   - cost (integer, Rupiah, modal per unit)\n   - stock (integer, jumlah unit)\n   - days_remaining (number, hari menuju kadaluarsa. \"besok\"=1, \"hari ini\"=0)\n   - shop_name (string)\n   Jika field tidak ada/tidak jelas, isi null.\n\n2. \"explanation\": 2-4 kalimat Bahasa Indonesia sederhana mengapa item perlu/tidak perlu diskon.\n\n3. \"promo_copy\": 1-2 kalimat promosi catchy dan mendesak untuk konsumen.\n\nHanya keluarkan JSON valid, tanpa teks lain, tanpa markdown code fence."
    },
    {
      "role": "user",
      "content": "roti tawar 10 biji exp 2 hari harga 15rb modal 10rb toko sari bakery"
    },
    {
      "role": "assistant",
      "content": "{\"parsed_input\": {\"item_name\": \"roti tawar\", \"category\": \"Bakery\", \"original_price\": 15000, \"cost\": 10000, \"stock\": 10, \"days_remaining\": 2, \"shop_name\": \"toko sari bakery\"}, \"explanation\": \"Roti tawar termasuk cepat basi. Dengan sisa 2 hari dan stok 10 pcs, perlu diskon agar tidak terbuang. Kategori bakery sangat sensitif harga, pembeli cenderung membeli jika ada potongan.\", \"promo_copy\": \"🍞 Roti tawar fresh dari Toko Sari Bakery! Stok terbatas, buruan sebelum habis. Diskon spesial untuk Anda!\"}"
    }
  ]
}
```

---

## 4. Training Data Specification

### 4.1 Data Generation Pipeline

**Script:** `scripts/generate_training_data.py` (to be written)

**Steps:**

1. **Generate random scenarios** (5,000–8,000 based on baseline gap)
   ```python
   categories = ["Bakery", "Prepared Food", "Dairy", "Beverage", "Produce", "Snack", "Canned", "Other"]
   
   for i in range(N):
       category = random.choice(categories)
       item_name = generate_item_name(category)  # e.g., "roti tawar", "susu uht", "sarden kaleng"
       shop_name = generate_shop_name()  # e.g., "Toko Sari Bakery", "Warung Bu Rina"
       
       original_price = random.randint(2000, 150000)  # Rp2.000 – Rp150.000
       cost = int(original_price * random.uniform(0.5, 0.9))  # 10-50% margin
       stock = random.randint(1, 100)
       
       shelf_life = CATEGORY_SHELF_LIFE[category]  # from Project Spec §9.5
       days_remaining = random.uniform(0, shelf_life * 1.5)  # some expired, some far
       
       daily_sales = random.uniform(1, 50)  # vendor estimate
   ```

2. **Run oracle** → get numbers (for context, to generate realistic explanations)
   ```python
   from pricing import compute_recommendation
   
   parsed_input = {
       "item_name": item_name,
       "category": category,
       "original_price": original_price,
       "cost": cost,
       "stock": stock,
       "days_remaining": days_remaining,
       "shop_name": shop_name
   }
   
   recommendation = compute_recommendation(parsed_input)
   # recommendation has: discount_percent, recommended_price, timing, etc.
   ```

3. **Generate model targets** (qualitative, no computed figures)
   
   **Explanation templates** (category + urgency-specific):
   ```python
   def generate_explanation(parsed_input, recommendation):
       category = parsed_input["category"]
       days = parsed_input["days_remaining"]
       stock = parsed_input["stock"]
       
       # Perishability statement
       if category == "Bakery":
           perish = "termasuk cepat basi"
       elif category == "Canned":
           perish = "tahan lama"
       elif category == "Dairy":
           perish = "perlu disimpan dingin dan cepat kadaluarsa"
       # ... etc
       
       # Urgency statement
       if days < 1:
           urgency = "Waktu sangat terbatas, harus habis hari ini"
       elif days < 3:
           urgency = f"Dengan sisa {int(days)} hari"
       else:
           urgency = f"Dengan sisa {int(days)} hari"
       
       # Stock statement
       if stock > 20:
           stock_stmt = f"stok masih banyak ({stock} pcs)"
       elif stock < 5:
           stock_stmt = f"stok tinggal sedikit ({stock} pcs)"
       else:
           stock_stmt = f"stok {stock} pcs"
       
       # Recommendation direction
       if recommendation["no_action"]:
           rec = "Belum perlu diskon, item ini kemungkinan terjual normal"
       elif recommendation["discount_percent"] > 40:
           rec = "perlu diskon agresif agar tidak terbuang"
       else:
           rec = "perlu diskon agar terjual sebelum kadaluarsa"
       
       # Category elasticity
       if category in ["Bakery", "Prepared Food"]:
           elast = "Kategori ini sangat sensitif harga, pembeli cenderung membeli jika ada potongan"
       elif category == "Canned":
           elast = "Kategori ini kurang sensitif harga, diskon kecil sudah cukup membantu"
       else:
           elast = ""
       
       explanation = f"{item_name.capitalize()} {perish}. {urgency} dan {stock_stmt}, {rec}. {elast}"
       return explanation.strip()
   ```
   
   **Promo templates** (urgency-specific, no figures):
   ```python
   def generate_promo(parsed_input, recommendation):
       item = parsed_input["item_name"]
       shop = parsed_input["shop_name"]
       days = parsed_input["days_remaining"]
       stock = parsed_input["stock"]
       
       if days < 1:
           urgency = "HARI INI SAJA!"
       elif days < 3:
           urgency = f"Sisa {int(days)} hari!"
       else:
           urgency = f"Promo spesial!"
       
       if stock < 5:
           stock_stmt = "Stok sangat terbatas"
       elif stock < 20:
           stock_stmt = "Stok terbatas"
       else:
           stock_stmt = "Selama persediaan masih ada"
       
       emojis = {"Bakery": "🍞", "Beverage": "☕", "Dairy": "🥛", "Prepared Food": "🍱", "Snack": "🍪"}
       emoji = emojis.get(parsed_input["category"], "🏷️")
       
       promo = f"{emoji} {item.capitalize()} dari {shop.capitalize()}! {urgency} {stock_stmt}, buruan sebelum habis. Diskon spesial untuk Anda!"
       return promo
   ```

4. **Generate colloquial free-text variants** (2–3 per scenario)
   ```python
   def to_colloquial(parsed_input):
       item = parsed_input["item_name"]
       price = parsed_input["original_price"]
       cost = parsed_input["cost"]
       stock = parsed_input["stock"]
       days = parsed_input["days_remaining"]
       shop = parsed_input["shop_name"]
       
       # Price abbreviation
       if price >= 1000000:
           price_str = f"{price/1000000:.1f}jt"
       elif price >= 1000:
           price_str = f"{price//1000}rb"
       else:
           price_str = str(price)
       
       # Cost abbreviation
       if cost >= 1000000:
           cost_str = f"{cost/1000000:.1f}jt"
       elif cost >= 1000:
           cost_str = f"{cost//1000}rb"
       else:
           cost_str = str(cost)
       
       # Days colloquial
       if days == 0:
           days_str = "hari ini"
       elif days == 1:
           days_str = "besok"
       else:
           days_str = f"{int(days)} hari"
       
       # Random unit word
       unit = random.choice(["pcs", "biji", "buah", ""])
       
       # Variant 1: standard colloquial
       v1 = f"{item} {stock} {unit} exp {days_str} harga {price_str} modal {cost_str} {shop}".strip()
       
       # Variant 2: shorter
       v2 = f"{item} {stock}{unit} exp {days_str} {price_str} modal {cost_str} {shop}".strip()
       
       # Variant 3: structured-ish
       v3 = f"Item: {item}\nStok: {stock}\nKadaluarsa: {days_str}\nHarga: {price}\nModal: {cost}\nToko: {shop}"
       
       return [v1, v2, v3]
   ```

5. **Format as chat JSONL**
   ```python
   for scenario in scenarios:
       for input_text in [structured_input] + colloquial_variants:
           example = {
               "messages": [
                   {"role": "system", "content": SYSTEM_PROMPT},
                   {"role": "user", "content": input_text},
                   {"role": "assistant", "content": json.dumps({
                       "parsed_input": scenario["parsed_input"],
                       "explanation": scenario["explanation"],
                       "promo_copy": scenario["promo_copy"]
                   }, ensure_ascii=False)}
               ]
           }
           write_jsonl(example)
   ```

### 4.2 Data Size & Split

| Baseline Accuracy | Training Examples | Train/Eval Split |
|---|---|---|
| ≥85% | 2,000–3,000 scenarios × 3 variants = 6,000–9,000 | 90/10 |
| 60–85% | 4,000–5,000 scenarios × 3 variants = 12,000–15,000 | 90/10 |
| <60% | 5,000–8,000 scenarios × 3 variants = 15,000–24,000 | 90/10 |

**Output:** `data/train.jsonl`, `data/eval.jsonl`

### 4.3 Edge Cases (10–15% of dataset)

Inject special scenarios:
- `days_remaining > shelf_life * 0.8` → "no action needed" response
- `days_remaining < 1` → fire sale explanation
- `days_remaining <= 0` → already expired warning
- `stock <= 2` → very low stock
- `cost >= original_price` → zero/negative margin warning
- Missing field (e.g., no `cost`) → `parsed_input` has `null`

---

## 5. QLoRA Configuration

### 5.1 Hyperparameters

| Parameter | Value | Rationale |
|---|---|---|
| **LoRA rank (r)** | 16 / 32 / 64 | Scaled to baseline gap (see §1.3) |
| **LoRA alpha** | 32 / 64 / 128 | Typically 2× rank |
| **Target modules** | `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj` | All linear layers (standard for Qwen) |
| **LoRA dropout** | 0.0 | Narrow task, no regularization needed |
| **Bias** | `none` | Standard for LoRA |
| **Learning rate** | `2e-4` | Standard for QLoRA |
| **LR scheduler** | `cosine` | Smooth decay |
| **Warmup ratio** | `0.05` | 5% warmup steps |
| **Epochs** | 1–3 | Scaled to baseline gap |
| **Per-device batch size** | `2` | Fits 8GB VRAM |
| **Gradient accumulation** | `8` | Effective batch = 16 |
| **Max seq length** | `1024` | Our prompts are <1K tokens |
| **Optimizer** | `adamw_8bit` | bitsandbytes, saves VRAM |
| **Weight decay** | `0.01` | Light regularization |
| **bf16** | `True` | Mixed precision |
| **Gradient checkpointing** | `True` | Saves VRAM |
| **4-bit quant type** | `nf4` | NormalFloat4 (QLoRA standard) |
| **Double quantization** | `True` | Quantize the quantization constants |
| **Seed** | `3407` | Reproducibility |

**VRAM estimate:** ~5–6 GB (Qwen3.5-4B QLoRA with these settings). Fits 8GB GPU.

### 5.2 Unsloth Setup

```python
from unsloth import FastLanguageModel
import torch

# Load base model in 4-bit
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen3.5-4B",
    max_seq_length=1024,
    dtype=None,  # auto-detect (bf16)
    load_in_4bit=True,  # QLoRA
)

# Apply LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16,  # or 32/64 based on baseline
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=32,  # or 64/128
    lora_dropout=0.0,
    bias="none",
    use_gradient_checkpointing="unsloth",  # Unsloth's optimized version
    random_state=3407,
    use_rslora=False,
    loftq_config=None,
)
```

---

## 6. Training Procedure

### 6.1 Step-by-Step Runbook

**Step 1: Prepare environment**
```bash
# Create venv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install "unsloth[cu121-torch240] @ git+https://github.com/unslothai/unsloth.git"
pip install trl bitsandbytes accelerate datasets
```

**Step 2: Generate training data**
```bash
python scripts/generate_training_data.py \
    --num-scenarios 4000 \
    --output-dir data/
```
Output: `data/train.jsonl`, `data/eval.jsonl`

**Step 3: Run training**
```bash
python scripts/train.py \
    --train-data data/train.jsonl \
    --eval-data data/eval.jsonl \
    --model-name unsloth/Qwen3.5-4B \
    --output-dir models/hargaturun-qwen3.5-4b-lora \
    --lora-r 16 \
    --lora-alpha 32 \
    --epochs 2 \
    --batch-size 2 \
    --grad-accum 8 \
    --lr 2e-4
```

**Step 4: Evaluate**
```bash
python scripts/eval_model.py \
    --model-path models/hargaturun-qwen3.5-4b-lora \
    --eval-data data/eval.jsonl
```

**Step 5: Export to GGUF**
```bash
python scripts/export_gguf.py \
    --model-path models/hargaturun-qwen3.5-4b-lora \
    --output models/hargaturun-qwen3.5-4b-q4_k_m.gguf \
    --quant q4_k_m
```

**Step 6: Test in llama.cpp**
```bash
llama-cli \
    -m models/hargaturun-qwen3.5-4b-q4_k_m.gguf \
    -ngl 99 \
    -c 1024 \
    --temp 0.0 \
    -p "Anda adalah asisten HargaTurun..." \
    --interactive
```

### 6.2 Training Script (`scripts/train.py`)

```python
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset
import torch
import argparse

def main(args):
    # Load model
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=1024,
        dtype=None,
        load_in_4bit=True,
    )
    
    # Apply LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"
        ],
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )
    
    # Load dataset
    train_dataset = load_dataset("json", data_files=args.train_data, split="train")
    eval_dataset = load_dataset("json", data_files=args.eval_data, split="train")
    
    # Training config
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=SFTConfig(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            warmup_ratio=0.05,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            logging_steps=10,
            lr_scheduler_type="cosine",
            optim="adamw_8bit",
            weight_decay=0.01,
            bf16=True,
            max_seq_length=1024,
            output_dir=args.output_dir,
            save_steps=100,
            save_total_limit=3,
            evaluation_strategy="steps",
            eval_steps=100,
            seed=3407,
            report_to="none",  # no wandb
        ),
    )
    
    # Train
    trainer.train()
    
    # Save LoRA adapters
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    
    print(f"Training complete. LoRA adapters saved to {args.output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-data", required=True)
    parser.add_argument("--eval-data", required=True)
    parser.add_argument("--model-name", default="unsloth/Qwen3.5-4B")
    parser.add_argument("--output-dir", default="models/hargaturun-lora")
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    args = parser.parse_args()
    main(args)
```

---

## 7. Evaluation

### 7.1 Metrics & Targets

| Metric | Target | How Measured |
|---|---|---|
| **JSON schema compliance** | >95% | Automated: response parses as valid JSON with required keys |
| **Parse accuracy (field-level)** | >90% | Automated: compare `parsed_input` fields to ground truth |
| **Explanation coherence** | >90% "clear" | Manual eval on 50 samples (Bahasa Indonesia native speaker) |
| **Promo copy quality** | >85% "would click" | Manual eval on 50 samples |
| **"No action" correctness** | >90% | Automated: low-pressure inputs → `no_action: true` |

See Project Spec §13.1 for full eval spec.

### 7.2 Eval Procedure

**Automated eval script:** `scripts/eval_model.py`

```python
# Loads eval.jsonl, runs model on each input, compares parsed_input to ground truth
# Reports:
# - JSON validity %
# - Field-level accuracy (category, original_price, cost, stock, days_remaining)
# - Overall accuracy (all fields correct)
# - Sample outputs for manual review
```

**Manual eval:** Print 50 random examples from eval set, rate explanation + promo quality (1-5 scale). Target: avg >4.0 ("clear" / "would click").

### 7.3 Baseline Comparison

After fine-tuning, re-run `scripts/baseline_eval.py` against the fine-tuned model (served via llama.cpp). Compare:

| Metric | Base Model (zero-shot) | Fine-Tuned |
|---|---|---|
| JSON validity | ?% | ?% |
| Parse accuracy | ?% | ?% |
| Overall accuracy | ?% | ?% |

**Success criterion:** Fine-tuned model shows ≥10% improvement in overall accuracy, or ≥95% JSON validity.

---

## 8. Export to GGUF (Serving)

### 8.1 Export Script

```python
from unsloth import FastLanguageModel
import argparse

def main(args):
    # Load base + LoRA
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_path,
        max_seq_length=1024,
        dtype=None,
        load_in_4bit=True,
    )
    
    # Merge LoRA into base (16-bit)
    model = FastLanguageModel.merge_and_unload(model)
    
    # Export to GGUF with quantization
    model.save_pretrained_gguf(
        "merged_model",
        tokenizer,
        quantization_method=args.quant  # "q4_k_m"
    )
    
    print(f"GGUF exported to merged_model/{args.quant}.gguf")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", default="models/hargaturun-qwen3.5-4b-q4_k_m.gguf")
    parser.add_argument("--quant", default="q4_k_m")
    args = parser.parse_args()
    main(args)
```

### 8.2 Serving with llama.cpp

```bash
llama-server \
    -m models/hargaturun-qwen3.5-4b-q4_k_m.gguf \
    -c 1024 \
    -ngl 99 \
    --host 0.0.0.0 \
    --port 8080 \
    --temp 0.0 \
    --top-p 1.0 \
    --top-k 40
```

**API endpoint:** `http://localhost:8080/v1/chat/completions` (OpenAI-compatible)

---

## 9. Iteration & Troubleshooting

### 9.1 If Eval Fails Targets

| Problem | Diagnosis | Fix |
|---|---|---|
| JSON validity <95% | Model drifts from schema | Add more training examples, increase LoRA rank (16→32→64) |
| Parse accuracy <90% | Colloquial variants not covered | Generate more diverse free-text variants (slang, abbreviations) |
| Explanation incoherent | Templates too rigid | Add LLM-augmented explanation diversity (use base Qwen to generate 5 variants per scenario) |
| Overfitting (train loss →0, eval loss ↑) | Too many epochs or too small dataset | Reduce epochs (3→2→1), increase dataset size |
| VRAM OOM | Batch size too large | Reduce `per_device_train_batch_size` to 1, increase `gradient_accumulation_steps` to 16 |

### 9.2 Hyperparameter Tuning (if needed)

Start with defaults (§5.1). If eval fails after 2 iterations:
- Try LoRA rank 32 or 64
- Try learning rate 1e-4 or 3e-4
- Try epochs 1 or 3

Do **not** grid search. Adjust one parameter at a time, re-eval.

---

## 10. Proposal Mapping (Methodology Section)

This fine-tuning plan feeds directly into the **Proposal PDF §4 Metodologi** (max 20 pages):

### 10.1 Alur Memperoleh Dataset (Data Acquisition Flow)

> "Dataset diperoleh melalui generasi sintetik berbasis oracle formula (Project Spec §9.5).
> Skenario pricing di-generate secara acak (5.000–8.000 contoh) mencakup 8 kategori produk,
> rentang harga Rp2.000–Rp150.000, dan variasi input kolokial Bahasa Indonesia.
> Setiap skenario diproses melalui oracle untuk memperoleh ground-truth numerik,
> lalu explanation dan promo copy di-generate menggunakan template berbasis kategori dan urgensi.
> Data dibagi 90% training / 10% evaluasi."

### 10.2 Alur Pengembangan Model (Model Development Flow)

> "Model dasar Qwen3.5-4B di-fine tune menggunakan QLoRA (4-bit NF4 + LoRA adapters)
> dengan library Unsloth. Arsitektur hybrid memisahkan tugas: model hanya belajar NLU
> (parsing input kolokial → JSON terstruktur) dan NLG (explanation + promo copy),
> sementara perhitungan pricing dilakukan oleh Python pricing engine (oracle formula).
> Hyperparameter: LoRA rank 16/32/64 (disesuaikan dengan baseline gap), learning rate 2e-4,
> batch size efektif 16, 1–3 epoch. Training dilakukan pada GPU 8GB VRAM, ~5-6 GB terpakai."

### 10.3 Alur Integrasi Model ke Environment Kode (Model Integration Flow)

> "Model hasil fine-tuning di-export ke format GGUF (Q4_K_M, ~2.5 GB) dan di-serve
> menggunakan llama.cpp dengan API OpenAI-compatible. Backend FastAPI memanggil model
> via HTTP POST ke /v1/chat/completions, mengirim system prompt + user input,
> menerima JSON berisi parsed_input + explanation + promo_copy.
> Python pricing engine kemudian menghitung discount, recommended price, dan proyeksi
> berdasarkan parsed_input, lalu meng-assemble respons akhir ke frontend.
> Seluruh sistem di-deploy via Docker Compose (3 service: model-server, api, frontend)."

### 10.4 Decision Making Berbasis Data (Data-Driven Decisions)

> "Sebelum fine-tuning, dilakukan baseline evaluation terhadap Qwen3.5-4B zero-shot
> pada 16 test case kolokial Bahasa Indonesia. Hasil baseline menentukan intensitas
> fine-tuning: jika akurasi ≥85%, cukup light fine-tuning (2-3K data, rank 16, 1-2 epoch);
> jika 60-85%, standard fine-tuning (4-5K data, rank 32, 2 epoch);
> jika <60%, full fine-tuning (5-8K data, rank 64, 2-3 epoch).
> Pendekatan ini memastikan effort fine-tuning proporsional dengan kebutuhan,
> tidak over-engineering."

---

## 11. Timeline & Deliverables

| Task | Duration | Output |
|---|---|---|
| Write `pricing.py` (oracle) | 1 day | `pricing.py` (deterministic, testable) |
| Write `generate_training_data.py` | 1 day | Script + `data/train.jsonl`, `data/eval.jsonl` |
| Run baseline eval | 0.5 day | Baseline accuracy report |
| Fine-tune (QLoRA) | 2–4 hours | `models/hargaturun-lora/` (LoRA adapters) |
| Eval fine-tuned model | 0.5 day | Eval report, manual review |
| Export to GGUF | 0.5 hour | `models/hargaturun-qwen3.5-4b-q4_k_m.gguf` |
| Test in llama.cpp | 0.5 hour | Verify inference works, temp=0 deterministic |
| Iterate if needed | 1–2 days | Adjust hyperparameters, re-train, re-eval |

**Total:** ~4–6 days (excluding iteration).

---

*This plan is a living document. Adjust hyperparameters and data size based on baseline eval results.*
