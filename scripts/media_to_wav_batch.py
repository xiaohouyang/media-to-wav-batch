#!/usr/bin/env python3
"""Batch download public media links from a normalized manifest and convert them to WAV."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

from ffmpeg_tools import convert_to_wav, ensure_ffmpeg, write_environment
from manifest_tools import (
    apply_metadata_defaults,
    assign_unique_base_name,
    load_default_genre_map,
    load_genre_map,
    load_manifest,
    read_input_manifest,
    save_manifest,
    write_result_logs,
    write_summary,
)
from media_batch_types import Record
from media_extractors import download_file, extract_media_source


def meta_output_dir(output: Path) -> Path:
    return output / ".meta"


def convert_records(records: List[Record], output: Path, args: argparse.Namespace) -> int:
    meta_output = meta_output_dir(output)
    try:
        ffmpeg = ensure_ffmpeg(output.parent)
    except Exception as exc:
        for record in records:
            if record.source_path and record.status in {"pending", "source_exists", "source_ready", "ffmpeg_install_failed", "transcode_failed"}:
                record.status = "ffmpeg_install_failed"
                record.error = str(exc)
        save_manifest(meta_output / "manifests" / "manifest_resolved.csv", records)
        write_result_logs(meta_output, records)
        write_summary(output, meta_output, records, wav_confirmed=False)
        print(f"ffmpeg unavailable: {exc}")
        return 3

    write_environment(meta_output, ffmpeg, args)
    for record in records:
        if record.source_path and record.status in {"pending", "source_exists", "source_ready", "ffmpeg_install_failed", "transcode_failed", "ok"}:
            convert_to_wav(record, ffmpeg, output, args.sample_rate, args.bit_depth, args.channels, args.overwrite)

    save_manifest(meta_output / "manifests" / "manifest_resolved.csv", records)
    write_result_logs(meta_output, records)
    write_summary(output, meta_output, records, wav_confirmed=True)
    ok = sum(1 for r in records if r.status == "ok")
    failed = sum(1 for r in records if r.status != "ok")
    print(f"Complete. WAV ok: {ok}; failed or skipped: {failed}; output: {output}")
    return 0 if failed == 0 else 1


def prepare_records(records: List[Record], output: Path, args: argparse.Namespace, default_pattern: str, genre_map: Dict[Tuple[str, str], str]) -> None:
    html_dir = meta_output_dir(output) / "html" if args.save_html else None
    used_names: Dict[str, int] = {}
    for record in records:
        if args.dry_run:
            apply_metadata_defaults([record], args.default_genre, genre_map)
            assign_unique_base_name(record, default_pattern, used_names)
            record.status = "dry_run"
            continue
        if not extract_media_source(record, html_dir, args.use_yt_dlp):
            continue
        apply_metadata_defaults([record], args.default_genre, genre_map)
        assign_unique_base_name(record, default_pattern, used_names)
        if not download_file(record, output, args.overwrite):
            continue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch download public media links and convert to WAV.")
    parser.add_argument("--input", required=True, help="Normalized .csv or .xlsx manifest path.")
    parser.add_argument("--output", default="media_batch", help="Output directory.")
    parser.add_argument("--filename-pattern", default="{song_name}-{original_singer}-{genre}")
    parser.add_argument("--default-genre", default="", help="User-specified batch genre. If omitted, infer from song metadata before using the unknown-genre fallback.")
    parser.add_argument("--genre-map", default="", help="Optional CSV with song_name, original_singer, genre columns for genre lookup.")
    parser.add_argument("--sample-rate", type=int, choices=[16000, 44100], help="Confirmed WAV sample rate, such as 16000 or 44100.")
    parser.add_argument("--bit-depth", type=int, choices=[16, 24, 32], help="Confirmed WAV bit depth.")
    parser.add_argument("--channels", choices=["mono", "stereo"], help="Confirmed WAV channel layout.")
    parser.add_argument("--confirm-wav-settings", action="store_true", help="Required to convert WAV files. Use only after the user confirmed sample rate, bit depth, and channels.")
    parser.add_argument("--prepare-only", action="store_true", help="Download and preserve source files, then stop before WAV conversion.")
    parser.add_argument("--convert-existing", action="store_true", help="Convert already downloaded sources from output/.meta/manifests/manifest_resolved.csv without re-downloading.")
    parser.add_argument("--dry-run", action="store_true", help="Only build manifests; do not download or convert.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing source/WAV files.")
    parser.add_argument("--save-html", action="store_true", help="Save fetched HTML pages under output/.meta/html for debugging.")
    parser.add_argument("--use-yt-dlp", action="store_true", help="Use installed yt-dlp as fallback extractor.")
    args = parser.parse_args()
    if args.confirm_wav_settings and (args.sample_rate is None or args.bit_depth is None or args.channels is None):
        parser.error("--confirm-wav-settings requires --sample-rate, --bit-depth, and --channels")
    if args.convert_existing and not args.confirm_wav_settings:
        parser.error("--convert-existing requires --confirm-wav-settings and confirmed WAV parameters")
    return args


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output = Path(args.output).resolve()
    meta_output = meta_output_dir(output)
    output.mkdir(parents=True, exist_ok=True)

    if args.convert_existing:
        manifest_path = meta_output / "manifests" / "manifest_resolved.csv"
        if not manifest_path.exists():
            print(f"Missing manifest for --convert-existing: {manifest_path}")
            return 2
        return convert_records(load_manifest(manifest_path), output, args)

    records, document_pattern = read_input_manifest(input_path)
    if not records:
        print("No manifest rows found in input.")
        return 2

    default_pattern = document_pattern or args.filename_pattern
    genre_map = {**load_default_genre_map(), **load_genre_map(args.genre_map)}
    save_manifest(meta_output / "manifests" / "manifest_extracted.csv", records)
    prepare_records(records, output, args, default_pattern, genre_map)

    if args.dry_run:
        save_manifest(meta_output / "manifests" / "manifest_resolved.csv", records)
        write_result_logs(meta_output, records)
        write_summary(output, meta_output, records, wav_confirmed=False)
        print(f"Dry run complete: {meta_output / 'manifests' / 'manifest_resolved.csv'}")
        return 0

    if args.prepare_only or not args.confirm_wav_settings:
        for record in records:
            if record.source_path and record.status in {"pending", "source_exists"}:
                record.status = "source_ready"
        save_manifest(meta_output / "manifests" / "manifest_resolved.csv", records)
        write_result_logs(meta_output, records)
        write_summary(output, meta_output, records, wav_confirmed=False)
        print(
            "Source download complete. WAV conversion is paused until the user confirms "
            "--sample-rate, --bit-depth, --channels, and --confirm-wav-settings."
        )
        return 0

    return convert_records(records, output, args)


if __name__ == "__main__":
    raise SystemExit(main())
