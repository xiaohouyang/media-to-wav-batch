# Manifest Prompt Template

Use this template when Codex needs to convert an arbitrary user document into `normalized_manifest.csv`.

## Minimal Prompt

```text
Read the user document and convert it into a strict CSV manifest named normalized_manifest.csv.

Required columns:
url,song_name,original_singer,genre,gender,filename_pattern

Rules:
- Keep one row per media link.
- Preserve explicit user-provided metadata.
- Leave unknown values blank instead of guessing.
- Do not infer gender from voice, avatar, nickname, image, or video.
- Convert the human naming format into a template such as {song_name}-{genre}-{original_singer}-{gender}.
- If the document does not specify a naming format, use {song_name}-{original_singer}-{genre}.

Before saving, quickly sanity-check:
- every row has a url
- filename_pattern is present
- links and nearby metadata were attached to the correct row
```

## Stronger Prompt

```text
Parse the attached user document semantically and create normalized_manifest.csv for the media-to-wav-batch skill.

Output columns:
url,song_name,original_singer,genre,gender,filename_pattern

Process:
1. Identify the document's intended naming format.
2. Convert that naming format into an internal template.
3. Extract each media link.
4. Attach nearby explicit metadata to the correct link.
5. Leave uncertain fields blank rather than inventing values.
6. Save the final CSV as normalized_manifest.csv.

Constraints:
- Use only explicit gender from the document.
- Preserve the user's wording when it is clearly a song name, singer, or genre.
- Prefer blank cells over risky guesses.
- Produce machine-clean CSV output only.
```

## Review Checklist

After generating the manifest, inspect:

- Are all links present?
- Does each row map to one media item?
- Does `filename_pattern` match the user's intended order?
- Are missing fields blank rather than filled with guesses?
- Did any line glue text directly onto a URL, such as `男https://...` or `https://...女`?
