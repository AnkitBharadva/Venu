# Local Model Weights & Offline Inference Configurations

## Air-Gap & Zero-Egress Architecture
This repository operates strictly in an **offline, air-gapped environment**.
At inference time:
- **No external API calls** (no OpenAI, Anthropic, Google or third-party endpoints).
- **No runtime telemetry** or external CDN lookups.
- All model weights are hosted locally or served via local inference engines (Ollama, vLLM, local Whisper runner) running within the secure enclave.

## Supported Models Specification (SIH26155)

| Role | Target Model | Local Runtime | Config File |
|---|---|---|---|
| **Reasoning & Synthesis** | Qwen3-8B / Qwen3-14B | Ollama / vLLM | `configs/qwen3_8b.yaml` |
| **Vision-Language** | Qwen3-VL-4B | vLLM / HuggingFace Transformers | `configs/qwen3_vl_4b.yaml` |
| **Audio/Video Speech-to-Text** | Whisper medium.en | Faster-Whisper / CTranslate2 | `configs/whisper_medium.yaml` |
| **Vector Grounding Embeddings** | BAAI/bge-small-en-v1.5 | FastEmbed / SentenceTransformers | `configs/bge_small_en.yaml` |

## Model Directory Structure
Model weights are mounted or downloaded to `models/weights/` during pre-deployment staging:

```
models/
├── README.md
├── configs/
│   ├── bge_small_en.yaml
│   ├── qwen3_8b.yaml
│   ├── qwen3_vl_4b.yaml
│   └── whisper_medium.yaml
└── weights/
    ├── bge-small-en-v1.5/
    ├── qwen3-8b-instruct-q4/
    ├── qwen3-vl-4b/
    └── whisper-medium.en/
```

## Weight Verification & Integrity Check
Before starting services in production, each model directory must be verified against sha256 checksums recorded in their respective config file to ensure uncorrupted and untampered weights.
