from __future__ import annotations

import html
import json
import mimetypes
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from media_batch_types import Record


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
MEDIA_EXTS = {
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, timeout: int = 30):
    req_headers = {"User-Agent": USER_AGENT, "Referer": "https://kg.qq.com/"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def read_text_response(url: str, timeout: int = 30) -> Tuple[str, str]:
    with request(url, timeout=timeout) as resp:
        data = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace"), resp.headers.get("Content-Type", "")


def fetch_head(url: str) -> Tuple[str, int]:
    try:
        with request(url, method="HEAD", timeout=15) as resp:
            return resp.headers.get("Content-Type", ""), int(resp.headers.get("Content-Length") or 0)
    except Exception:
        return "", 0


def is_probably_direct_media(url: str) -> bool:
    path = urllib.parse.urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in MEDIA_EXTS:
        return True
    ctype, _ = fetch_head(url)
    return ctype.lower().startswith(("audio/", "video/"))


def content_type_to_ext(ctype: str, fallback_url: str = "") -> str:
    ctype = (ctype or "").split(";")[0].strip().lower()
    mapping = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/aac": ".aac",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/flac": ".flac",
        "audio/ogg": ".ogg",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "video/x-matroska": ".mkv",
    }
    if ctype in mapping:
        return mapping[ctype]
    guessed = mimetypes.guess_extension(ctype) if ctype else None
    if guessed:
        return ".m4a" if guessed == ".mp4" and ctype.startswith("audio/") else guessed
    return Path(urllib.parse.urlparse(fallback_url).path).suffix.lower() or ".media"


def media_type_from_ext_or_ctype(ext: str, ctype: str) -> str:
    ctype = (ctype or "").lower()
    if ctype.startswith("audio/") or ext.lower() in AUDIO_EXTS:
        return "audio"
    if ctype.startswith("video/") or ext.lower() in VIDEO_EXTS:
        return "video"
    return "unknown"


def find_matching_brace(text: str, start: int) -> int:
    depth = 0
    in_string = False
    quote = ""
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            continue
        if ch in ("'", '"'):
            in_string = True
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def parse_kg_data(page: str) -> Optional[dict]:
    marker = "window.__DATA__"
    pos = page.find(marker)
    if pos == -1:
        return None
    start = page.find("{", pos)
    if start == -1:
        return None
    end = find_matching_brace(page, start)
    if end == -1:
        return None
    return json.loads(html.unescape(page[start : end + 1]))


def extract_kg(record: Record, html_dir: Optional[Path]) -> bool:
    page, _ = read_text_response(record.url)
    if html_dir is not None:
        html_dir.mkdir(parents=True, exist_ok=True)
        shareid = urllib.parse.parse_qs(urllib.parse.urlparse(record.url).query).get("s", [""])[0]
        (html_dir / f"{shareid or record.row_id}.html").write_text(page, encoding="utf-8")
    data = parse_kg_data(page)
    if not data:
        record.status = "parse_failed"
        record.error = "Could not parse window.__DATA__"
        return False
    detail = data.get("detail") or {}
    record.detected_platform = "kg.qq.com"
    record.page_title = detail.get("song_name", "")
    record.page_metadata = {
        "song_name": detail.get("song_name", ""),
        "original_singer": detail.get("singer_name", ""),
        "genre": detail.get("genre") or detail.get("song_type") or detail.get("style") or "",
    }
    record.song_name = record.song_name or record.page_metadata["song_name"]
    record.original_singer = record.original_singer or record.page_metadata["original_singer"]
    record.genre = record.genre or record.page_metadata["genre"]
    media_url = detail.get("playurl") or detail.get("playurl_video")
    if not media_url:
        share = data.get("share") or {}
        media_url = share.get("data_url") or ""
    if not media_url:
        record.status = "no_media_url"
        record.error = "No playurl or playurl_video found"
        record.extraction_reason = "kg data parsed but no media URL was present"
        return False
    record.platform = "kg.qq.com"
    record.media_url = media_url
    record.candidate_count = 1
    record.selected_candidate = media_url
    record.extraction_reason = "kg playurl"
    return True


def extract_netease(record: Record) -> bool:
    match = re.search(r"(?:outchain/2/|[?&]id=)(\d+)", record.url)
    if not match:
        record.status = "unsupported_platform"
        record.error = "Could not find NetEase song id"
        return False
    song_id = match.group(1)
    record.detected_platform = "music.163.com"
    detail_url = f"https://music.163.com/api/song/detail/?ids=%5B{song_id}%5D"
    try:
        detail_text, _ = read_text_response(detail_url)
        detail = json.loads(detail_text)
        song = (detail.get("songs") or [{}])[0]
    except Exception:
        song = {}
    if song:
        record.song_name = record.song_name or song.get("name", "")
        record.page_title = song.get("name", "")
        artists = song.get("artists") or []
        if artists and not record.original_singer:
            record.original_singer = "/".join(a.get("name", "") for a in artists if a.get("name"))
    record.platform = "music.163.com"
    record.media_url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"
    record.candidate_count = 1
    record.selected_candidate = record.media_url
    record.extraction_reason = "netease public outer URL"
    return True


def absolutize(base_url: str, found_url: str) -> str:
    found_url = html.unescape(found_url.strip().strip("'\""))
    if found_url.startswith("//"):
        return "https:" + found_url
    return urllib.parse.urljoin(base_url, found_url)


def extract_generic_page(record: Record, html_dir: Optional[Path]) -> bool:
    page, _ = read_text_response(record.url)
    if html_dir is not None:
        html_dir.mkdir(parents=True, exist_ok=True)
        (html_dir / f"row_{record.row_id}.html").write_text(page, encoding="utf-8")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    if title_match and not record.song_name:
        record.song_name = re.sub(r"\s+", " ", html.unescape(title_match.group(1))).strip()
    if title_match:
        record.page_title = re.sub(r"\s+", " ", html.unescape(title_match.group(1))).strip()
    if not record.genre:
        genre_match = re.search(r"<meta[^>]+(?:name|property)=[\"'](?:music:genre|article:tag|genre)[\"'][^>]+content=[\"']([^\"']+)[\"']", page, re.I)
        if genre_match:
            record.genre = html.unescape(genre_match.group(1)).strip()

    candidates: List[str] = []
    patterns = [
        r"<(?:audio|video|source)[^>]+src=[\"']([^\"']+)[\"']",
        r"<meta[^>]+property=[\"']og:(?:audio|video)[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:(?:audio|video)[\"']",
        r"https?://[^\"'\\<>\s]+?\.(?:mp3|m4a|aac|wav|flac|ogg|opus|mp4|mov|mkv|webm)(?:\?[^\"'\\<>\s]*)?",
    ]
    for pattern in patterns:
        candidates.extend(absolutize(record.url, m) for m in re.findall(pattern, page, re.I))

    seen = set()
    candidates = [c for c in candidates if not (c in seen or seen.add(c))]
    record.candidate_count = len(candidates)
    if not candidates:
        record.status = "no_media_url"
        record.error = "No media candidates found in page"
        record.extraction_reason = "generic page found no candidates"
        return False

    audio_candidates = [c for c in candidates if Path(urllib.parse.urlparse(c).path).suffix.lower() in AUDIO_EXTS]
    record.media_url = (audio_candidates or candidates)[0]
    record.platform = urllib.parse.urlparse(record.url).netloc
    record.detected_platform = record.platform
    record.selected_candidate = record.media_url
    record.extraction_reason = "generic page candidate"
    return True


def extract_with_ytdlp(record: Record) -> bool:
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        record.status = record.status if record.status != "pending" else "unsupported_platform"
        record.error = record.error or "yt-dlp is not installed"
        return False
    try:
        output = subprocess.check_output([ytdlp, "-g", "--no-playlist", record.url], text=True, stderr=subprocess.STDOUT, timeout=60)
    except subprocess.CalledProcessError as exc:
        record.status = "yt_dlp_failed"
        record.error = exc.output.strip()
        return False
    urls = [line.strip() for line in output.splitlines() if line.strip().startswith("http")]
    if not urls:
        record.status = "no_media_url"
        record.error = "yt-dlp returned no media URL"
        record.extraction_reason = "yt-dlp returned no media URL"
        return False
    record.media_url = urls[0]
    record.platform = urllib.parse.urlparse(record.url).netloc
    record.detected_platform = record.platform
    record.candidate_count = len(urls)
    record.selected_candidate = record.media_url
    record.extraction_reason = "yt-dlp fallback"
    return True


def extract_media_source(record: Record, html_dir: Optional[Path], use_ytdlp: bool) -> bool:
    parsed = urllib.parse.urlparse(record.url)
    if parsed.scheme not in {"http", "https"}:
        record.status = "invalid_url"
        record.error = "URL must start with http or https"
        return False
    if is_probably_direct_media(record.url):
        record.platform = parsed.netloc
        record.detected_platform = parsed.netloc
        record.media_url = record.url
        record.candidate_count = 1
        record.selected_candidate = record.url
        record.extraction_reason = "direct media URL"
        return True
    try:
        if parsed.netloc.endswith("kg.qq.com"):
            return extract_kg(record, html_dir)
        if parsed.netloc.endswith("music.163.com") and "outchain" in record.url:
            return extract_netease(record)
        if extract_generic_page(record, html_dir):
            return True
    except (urllib.error.URLError, TimeoutError) as exc:
        record.status = "fetch_failed"
        record.error = str(exc)
        return False
    except Exception as exc:
        record.status = "extractor_failed"
        record.error = str(exc)
        return False
    if use_ytdlp:
        return extract_with_ytdlp(record)
    return False


def download_file(record: Record, output: Path, overwrite: bool) -> bool:
    ctype, _ = fetch_head(record.media_url)
    ext = content_type_to_ext(ctype, record.media_url)
    media_type = media_type_from_ext_or_ctype(ext, ctype)
    if media_type == "unknown":
        media_type = "audio" if ext in AUDIO_EXTS else "video" if ext in VIDEO_EXTS else "audio"
    record.media_type = media_type
    record.source_ext = ext

    source_dir = output / "source" / media_type
    source_dir.mkdir(parents=True, exist_ok=True)
    target = source_dir / f"{record.base_filename}{ext}"
    record.source_path = str(target)
    if target.exists() and not overwrite:
        record.status = "source_exists"
        return True

    tmp = source_dir / f".{record.base_filename}.download"
    try:
        with request(record.media_url, timeout=60) as resp, tmp.open("wb") as f:
            ctype = resp.headers.get("Content-Type", ctype)
            ext = content_type_to_ext(ctype, record.media_url)
            record.media_type = media_type_from_ext_or_ctype(ext, ctype)
            record.source_ext = ext
            if target.suffix != ext:
                target = source_dir / f"{record.base_filename}{ext}"
                record.source_path = str(target)
            shutil.copyfileobj(resp, f)
    except Exception as exc:
        record.status = "download_failed"
        record.error = str(exc)
        tmp.unlink(missing_ok=True)
        return False

    if tmp.stat().st_size < 1024:
        record.status = "bad_media_file"
        record.error = "Downloaded file is too small"
        tmp.unlink(missing_ok=True)
        return False
    with tmp.open("rb") as f:
        first = f.read(256).lower()
    if first.lstrip().startswith((b"<!doctype", b"<html")):
        record.status = "bad_media_file"
        record.error = "Downloaded content looks like HTML"
        tmp.unlink(missing_ok=True)
        return False
    if target.exists() and overwrite:
        target.unlink()
    tmp.replace(target)
    return True
