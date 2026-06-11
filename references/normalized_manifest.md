# Normalized Manifest

Use a normalized manifest whenever the user provides a free-form document, Word/PDF/text note, mixed natural language, or any format that is not already a clean CSV/XLSX table.

Codex should read and understand the user document first, then create a strict CSV manifest for the script. Do not make the script guess complex document layouts.

## Required Columns

```csv
url,song_name,original_singer,genre,gender,filename_pattern
```

## Rules

- `url` is required.
- Leave unknown metadata blank when the document does not provide it. The script can fill page metadata and genre maps later.
- Preserve user-provided metadata over page metadata.
- Write `filename_pattern` as a template using internal field names.
- Use one row per media link.
- Do not infer gender from voice, avatar, nickname, image, or video. Use only explicit user-provided gender.

## Parsing Steps

1. Read the whole document first and identify:
   - naming format
   - media links
   - explicit song metadata near each link
2. Convert the human naming format into a template.
3. Create one manifest row per link.
4. Keep missing values blank instead of guessing.
5. Save the result as `normalized_manifest.csv`.

## Filename Pattern Conversion

Convert human naming formats into templates:

```text
歌名-歌曲类型-歌手-性别 -> {song_name}-{genre}-{original_singer}-{gender}
歌名-歌手-歌曲类型 -> {song_name}-{original_singer}-{genre}
```

If the document does not specify a format, use:

```text
{song_name}-{original_singer}-{genre}
```

## Example

Input document:

```text
歌名-歌曲类型-歌手-性别
男https://static-play.kg.qq.com/node/...
https://music.163.com/#/outchain/2/1455767549/女
```

Normalized manifest:

```csv
url,song_name,original_singer,genre,gender,filename_pattern
https://static-play.kg.qq.com/node/...,老男孩,筷子兄弟,流行,男,{song_name}-{genre}-{original_singer}-{gender}
https://music.163.com/#/outchain/2/1455767549/,,, ,女,{song_name}-{genre}-{original_singer}-{gender}
```

The second row may leave `song_name`, `original_singer`, or `genre` blank if the document did not explicitly provide them; page metadata and genre maps can fill them later.
