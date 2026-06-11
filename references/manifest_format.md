# Manifest Format

The script expects a normalized `.csv` or `.xlsx` manifest. Free-form `.txt`, `.md`, `.docx`, and `.pdf` inputs should be semantically parsed by Codex first and converted into `normalized_manifest.csv`.

## Standard Fields

```csv
row_id,url,platform,media_type,song_name,original_singer,genre,gender,base_filename,source_ext,source_path,wav_path,status,error
```

## Output Layout

```text
media_batch/
  source/
    audio/
    video/
  wav/
  .meta/
    manifests/
      manifest_extracted.csv
      manifest_resolved.csv
    logs/
      success.csv
      failures.csv
      environment.json
      extraction_debug.csv
      manifest_validation.csv
      summary.txt
    html/            only when --save-html is used
```

## Field Priority

Use user-provided document values first.

```text
song_name: document > page metadata > URL filename > Unknown song
original_singer: document > page metadata > Unknown singer
genre: document > page metadata > known song/genre map > user batch default > 未知类型
gender: document > Unknown
```

Gender must not be inferred from voice, avatar, nickname, or appearance.

Do not write `未知类型` merely because the document omitted genre. First infer from the song and original singer when possible. The bundled `references/default_genre_map.csv` is loaded automatically. A user-provided `--genre-map` CSV can add or override entries:

```csv
song_name,original_singer,genre
老男孩,筷子兄弟,流行
```

## Naming

Default filename pattern:

```text
{song_name}-{original_singer}-{genre}
```

Source files and WAV files share the same `base_filename`. Only the extension and directory differ.

## Media Extraction Order

```text
1. Direct media URL by extension or Content-Type.
2. Platform adapter, including kg.qq.com and music.163.com outchain links.
3. Generic HTML extractor for audio/video/source/meta/JSON-LD/script URLs.
4. Optional yt-dlp fallback for public authorized media only.
```

Windows filename cleanup must replace:

```text
\ / : * ? " < > |
```

When a duplicate appears, add suffixes to the base filename:

```text
Song-Singer-Genre
Song-Singer-Genre_2
Song-Singer-Genre_3
```
