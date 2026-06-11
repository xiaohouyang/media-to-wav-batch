from __future__ import annotations

import csv
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from media_batch_types import FIELD_ALIASES, Record


INVALID_FILENAME_CHARS = r'\/:*?"<>|'
MANIFEST_FIELDS = [
    "row_id",
    "url",
    "platform",
    "media_type",
    "song_name",
    "original_singer",
    "genre",
    "gender",
    "base_filename",
    "source_ext",
    "source_path",
    "wav_path",
    "status",
    "error",
]


def normalize_key(key: str) -> str:
    key = str(key or "").strip().lower().replace(" ", "_")
    for canonical, aliases in FIELD_ALIASES.items():
        if key in {alias.lower() for alias in aliases}:
            return canonical
    return key


def sanitize_filename(value: str, fallback: str = "Unknown") -> str:
    value = str(value or fallback).strip()
    for ch in INVALID_FILENAME_CHARS:
        value = value.replace(ch, "_")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[-_ ]{2,}", "-", value)
    value = value.strip(" .-_")
    return value[:180] or fallback


def pattern_to_template(pattern: str) -> str:
    pattern = (pattern or "").strip()
    if not pattern:
        return "{song_name}-{original_singer}-{genre}"
    replacements = {
        "歌名": "{song_name}",
        "歌曲名": "{song_name}",
        "歌曲名称": "{song_name}",
        "歌手": "{original_singer}",
        "原唱": "{original_singer}",
        "原唱歌手": "{original_singer}",
        "歌曲类型": "{genre}",
        "类型": "{genre}",
        "曲风": "{genre}",
        "性别": "{gender}",
    }
    for src, dst in replacements.items():
        pattern = pattern.replace(src, dst)
    return pattern


def render_base_filename(record: Record, default_pattern: str) -> str:
    template = pattern_to_template(record.filename_pattern or default_pattern)
    values = {
        "song_name": sanitize_filename(record.song_name or "Unknown song"),
        "original_singer": sanitize_filename(record.original_singer or "Unknown singer"),
        "genre": sanitize_filename(record.genre or "未知类型"),
        "gender": sanitize_filename(record.gender or "Unknown"),
    }
    try:
        rendered = template.format(**values)
    except KeyError:
        rendered = "{song_name}-{original_singer}-{genre}".format(**values)
    return sanitize_filename(rendered, fallback=f"item_{record.row_id}")


def assign_unique_base_name(record: Record, default_pattern: str, used: Dict[str, int]) -> None:
    base = render_base_filename(record, default_pattern)
    count = used.get(base, 0) + 1
    used[base] = count
    record.base_filename = base if count == 1 else f"{base}_{count}"


def read_csv_manifest(path: Path) -> Tuple[List[Dict[str, str]], str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{normalize_key(k): (v or "").strip() for k, v in row.items()} for row in reader]
    pattern = ""
    for row in rows:
        pattern = row.get("filename_pattern") or pattern
    return rows, pattern


def read_xlsx_manifest(path: Path) -> Tuple[List[Dict[str, str]], str]:
    try:
        import openpyxl  # type: ignore
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to read .xlsx manifest inputs") from exc
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers = [normalize_key(x) for x in next(rows_iter)]
    rows = []
    pattern = ""
    for values in rows_iter:
        row = {headers[i]: str(values[i] or "").strip() for i in range(len(headers))}
        rows.append(row)
        pattern = row.get("filename_pattern") or pattern
    return rows, pattern


def read_input_manifest(path: Path) -> Tuple[List[Record], str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        rows, pattern = read_csv_manifest(path)
    elif suffix == ".xlsx":
        rows, pattern = read_xlsx_manifest(path)
    else:
        raise RuntimeError("Input must be a normalized .csv or .xlsx manifest")

    records: List[Record] = []
    for i, row in enumerate(rows, 1):
        url = (row.get("url") or "").strip()
        records.append(
            Record(
                row_id=i,
                url=url,
                song_name=row.get("song_name", ""),
                original_singer=row.get("original_singer", ""),
                genre=row.get("genre", ""),
                gender=row.get("gender", ""),
                filename_pattern=row.get("filename_pattern", "") or pattern,
            )
        )
    return records, pattern


def save_manifest(path: Path, records: List[Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({field: getattr(r, field) for field in MANIFEST_FIELDS})


def load_manifest(path: Path) -> List[Record]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        records = []
        for row in reader:
            records.append(
                Record(
                    row_id=int(row.get("row_id") or len(records) + 1),
                    url=row.get("url", ""),
                    platform=row.get("platform", ""),
                    media_type=row.get("media_type", ""),
                    song_name=row.get("song_name", ""),
                    original_singer=row.get("original_singer", ""),
                    genre=row.get("genre", ""),
                    gender=row.get("gender", ""),
                    base_filename=row.get("base_filename", ""),
                    source_ext=row.get("source_ext", ""),
                    source_path=row.get("source_path", ""),
                    wav_path=row.get("wav_path", ""),
                    status=row.get("status", "pending"),
                    error=row.get("error", ""),
                    detected_platform=row.get("detected_platform", ""),
                    candidate_count=int(row.get("candidate_count") or 0),
                    selected_candidate=row.get("selected_candidate", ""),
                    extraction_reason=row.get("extraction_reason", ""),
                    page_title=row.get("page_title", ""),
                )
            )
    return records


def save_extraction_debug(path: Path, records: List[Record]) -> None:
    fields = [
        "row_id",
        "url",
        "detected_platform",
        "candidate_count",
        "selected_candidate",
        "extraction_reason",
        "page_title",
        "status",
        "error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({field: getattr(r, field) for field in fields})


def save_manifest_validation(path: Path, records: List[Record]) -> None:
    fields = ["row_id", "url", "issue", "detail"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            if not r.url:
                writer.writerow({"row_id": r.row_id, "url": r.url, "issue": "missing_url", "detail": "url is required"})
                continue
            parsed = urllib.parse.urlparse(r.url)
            if parsed.scheme not in {"http", "https"}:
                writer.writerow({"row_id": r.row_id, "url": r.url, "issue": "invalid_url", "detail": "url must start with http or https"})
            if r.filename_pattern:
                fields_in_pattern = set(re.findall(r"{([^{}]+)}", pattern_to_template(r.filename_pattern)))
                allowed = {"song_name", "original_singer", "genre", "gender"}
                unknown = fields_in_pattern - allowed
                if unknown:
                    writer.writerow({"row_id": r.row_id, "url": r.url, "issue": "unknown_filename_field", "detail": ",".join(sorted(unknown))})


def write_summary(output: Path, meta_output: Path, records: List[Record], wav_confirmed: bool) -> None:
    logs = meta_output / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    source_ready = sum(1 for r in records if r.status in {"source_ready", "source_exists", "ok"} and r.source_path)
    wav_ok = sum(1 for r in records if r.status == "ok" and r.wav_path)
    failed = sum(1 for r in records if r.status not in {"source_ready", "source_exists", "ok", "dry_run"})
    lines = [
        f"records={len(records)}",
        f"source_ready={source_ready}",
        f"wav_ok={wav_ok}",
        f"failed={failed}",
        f"wav_confirmed={str(wav_confirmed).lower()}",
        f"manifest={meta_output / 'manifests' / 'manifest_resolved.csv'}",
        f"source_dir={output / 'source'}",
        f"wav_dir={output / 'wav'}",
        "next_step=confirm sample_rate, bit_depth, and channels, then run --convert-existing"
        if not wav_confirmed
        else "next_step=review wav output and failures.csv",
    ]
    (logs / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_result_logs(output: Path, records: List[Record]) -> None:
    logs = output / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    non_failure = {"ok", "source_exists", "source_ready"}
    save_manifest(logs / "success.csv", [r for r in records if r.status in non_failure])
    save_manifest(logs / "failures.csv", [r for r in records if r.status not in non_failure])
    save_extraction_debug(logs / "extraction_debug.csv", records)
    save_manifest_validation(logs / "manifest_validation.csv", records)


def load_genre_map(path: str = "") -> Dict[Tuple[str, str], str]:
    if not path:
        return {}
    genre_map: Dict[Tuple[str, str], str] = {}
    map_path = Path(path)
    if not map_path.exists():
        raise RuntimeError(f"Genre map file does not exist: {path}")
    with map_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = {normalize_key(k): (v or "").strip() for k, v in row.items()}
            song = normalized.get("song_name", "")
            singer = normalized.get("original_singer", "")
            genre = normalized.get("genre", "")
            if song and singer and genre:
                genre_map[(song, singer)] = genre
    return genre_map


def load_default_genre_map() -> Dict[Tuple[str, str], str]:
    default_path = Path(__file__).resolve().parents[1] / "references" / "default_genre_map.csv"
    return load_genre_map(str(default_path)) if default_path.exists() else {}


def infer_genre(record: Record, user_default: str, genre_map: Dict[Tuple[str, str], str]) -> str:
    if record.genre:
        return record.genre
    if user_default:
        return user_default
    candidates = [(record.song_name, record.original_singer), (record.song_name, "")]
    for song, singer in candidates:
        if (song, singer) in genre_map:
            return genre_map[(song, singer)]
    for (song, singer), genre in genre_map.items():
        if song and song == record.song_name and (not singer or not record.original_singer or singer == record.original_singer):
            return genre
    return "未知类型"


def apply_metadata_defaults(records: List[Record], default_genre: str, genre_map: Optional[Dict[Tuple[str, str], str]] = None) -> None:
    genre_map = genre_map or {}
    for r in records:
        r.song_name = r.song_name or sanitize_filename(Path(urllib.parse.urlparse(r.url).path).stem, "Unknown song")
        r.original_singer = r.original_singer or "Unknown singer"
        r.genre = infer_genre(r, default_genre, genre_map)
        r.gender = r.gender or "Unknown"
