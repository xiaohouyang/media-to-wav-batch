from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


FIELD_ALIASES = {
    "url": {"url", "link", "media_url", "链接", "地址", "媒体链接", "歌曲链接"},
    "song_name": {"song_name", "song", "title", "name", "歌名", "歌曲", "歌曲名", "歌曲名称", "标题"},
    "original_singer": {
        "original_singer",
        "singer",
        "artist",
        "歌手",
        "原唱",
        "原唱歌手",
        "歌手姓名",
    },
    "genre": {"genre", "type", "song_type", "曲风", "类型", "歌曲类型", "音乐类型"},
    "gender": {"gender", "sex", "性别", "演唱者性别"},
    "filename_pattern": {"filename_pattern", "pattern", "命名格式", "文件名格式"},
}


@dataclass
class Record:
    row_id: int
    url: str
    song_name: str = ""
    original_singer: str = ""
    genre: str = ""
    gender: str = ""
    filename_pattern: str = ""
    platform: str = ""
    media_type: str = ""
    media_url: str = ""
    source_ext: str = ""
    base_filename: str = ""
    source_path: str = ""
    wav_path: str = ""
    status: str = "pending"
    error: str = ""
    page_metadata: Dict[str, str] = field(default_factory=dict)
    detected_platform: str = ""
    candidate_count: int = 0
    selected_candidate: str = ""
    extraction_reason: str = ""
    page_title: str = ""
