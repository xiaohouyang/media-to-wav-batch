from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import List

from media_batch_types import Record


FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def ensure_ffmpeg(workspace: Path) -> str:
    existing = shutil.which("ffmpeg")
    if existing:
        return existing
    portable_root = workspace / ".tools" / "ffmpeg"
    existing_portable = list(portable_root.glob("**/bin/ffmpeg.exe")) if portable_root.exists() else []
    if existing_portable:
        return str(existing_portable[0])
    if os.name != "nt":
        raise RuntimeError("ffmpeg is missing; automatic portable installation is currently Windows-only")
    portable_root.mkdir(parents=True, exist_ok=True)
    zip_path = portable_root / "ffmpeg-release-essentials.zip"
    print(f"Downloading portable ffmpeg to {zip_path} ...")
    urllib.request.urlretrieve(FFMPEG_ZIP_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(portable_root)
    matches = list(portable_root.glob("**/bin/ffmpeg.exe"))
    if not matches:
        raise RuntimeError("Portable ffmpeg install failed: ffmpeg.exe not found")
    subprocess.check_call([str(matches[0]), "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return str(matches[0])


def bit_depth_args(bit_depth: int) -> List[str]:
    if bit_depth == 16:
        return ["-sample_fmt", "s16", "-c:a", "pcm_s16le"]
    if bit_depth == 24:
        return ["-sample_fmt", "s32", "-c:a", "pcm_s24le"]
    if bit_depth == 32:
        return ["-sample_fmt", "s32", "-c:a", "pcm_s32le"]
    raise ValueError("bit depth must be 16, 24, or 32")


def convert_to_wav(record: Record, ffmpeg: str, output: Path, sample_rate: int, bit_depth: int, channels: str, overwrite: bool) -> bool:
    wav_dir = output / "wav"
    wav_dir.mkdir(parents=True, exist_ok=True)
    wav_path = wav_dir / f"{record.base_filename}.wav"
    record.wav_path = str(wav_path)
    if wav_path.exists() and not overwrite:
        record.status = "ok"
        return True
    ac = "1" if channels == "mono" else "2"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        record.source_path,
        "-vn",
        "-ac",
        ac,
        "-ar",
        str(sample_rate),
        *bit_depth_args(bit_depth),
        str(wav_path),
    ]
    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    except subprocess.CalledProcessError as exc:
        record.status = "transcode_failed"
        record.error = exc.output[-1000:]
        if "Output file #0 does not contain any stream" in exc.output or "does not contain any stream" in exc.output:
            record.status = "video_has_no_audio"
        return False
    record.status = "ok"
    record.error = ""
    return True


def write_environment(meta_output: Path, ffmpeg: str, args) -> None:
    env = {
        "ffmpeg_path": ffmpeg,
        "sample_rate": args.sample_rate,
        "bit_depth": args.bit_depth,
        "channels": args.channels,
    }
    logs = meta_output / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "environment.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
