---
name: media-to-wav-batch
description: Batch process user-provided documents or manifests containing public audio/video/MV links and naming metadata; first semantically parse arbitrary user documents into a normalized CSV manifest, then detect direct media links or extract media from pages such as kg.qq.com or music.163.com outchain links, preserve original source audio/video with standard names, ensure portable ffmpeg when needed, and convert sources to WAV only after the user confirms sample rate, bit depth, and channels. Use when Codex needs to normalize messy media-link documents, download authorized public media links, keep source files, or convert batches to WAV.
---

# Media To WAV Batch

## Rules

Use only for media the user owns or is authorized to save. Do not bypass login, payment, DRM, private access, encryption, or platform restrictions. Do not infer gender from voice, avatar, nickname, or appearance.

Never silently choose WAV settings. Ask the user to confirm sample rate, bit depth, and channels before conversion.

## Workflow

1. If the input is not already a clean CSV/XLSX manifest, read the user document yourself and create `normalized_manifest.csv`. Follow `references/normalized_manifest.md`. Reuse `references/manifest_prompt_template.md` when you want a stable prompt/checklist for this semantic parsing step. The script is manifest-first and should not be used to understand complex free-form document layouts.

2. Run preparation on the normalized manifest:

```bash
python scripts/media_to_wav_batch.py --input normalized_manifest.csv --output media_batch --prepare-only
```

3. Inspect `media_batch/.meta/manifests/manifest_resolved.csv` and `media_batch/.meta/logs/summary.txt` or `extraction_debug.csv`.

4. Ask the user to choose WAV settings:

```text
sample rate: 16000 or 44100
bit depth: 16, 24, or 32
channels: mono or stereo
```

5. Convert existing source files only after confirmation:

```bash
python scripts/media_to_wav_batch.py --input normalized_manifest.csv --output media_batch --convert-existing --sample-rate 44100 --bit-depth 16 --channels mono --confirm-wav-settings
```

By default the user-facing output directory only needs `source/` and `wav/`. Internal manifests and logs are stored under `media_batch/.meta/`. Use `references/manifest_format.md` for fields, source retention, extractor order, and logs. Use `references/troubleshooting.md` for failure states and diagnostics.
