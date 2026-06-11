# Troubleshooting

## Failure States

```text
invalid_url
fetch_failed
parse_failed
unsupported_platform
no_media_url
download_failed
bad_media_file
ffmpeg_install_failed
transcode_failed
video_has_no_audio
drm_or_login_required
```

## Notes

- Direct media URLs should be tried before page extraction.
- Temporary signed media URLs should be downloaded immediately after extraction.
- `未知类型` should appear only after document metadata, page metadata, known song mappings, and optional user genre maps fail to identify a genre.
- WAV conversion must not run unless the user confirmed sample rate, bit depth, and channels. Use `source_ready` when source files are downloaded but WAV conversion is intentionally paused.
- If ffmpeg cannot be installed, keep any downloaded source files and mark WAV conversion as failed.
- If a video has no audio track, record `video_has_no_audio`.
- If generic page extraction finds multiple candidates, prefer audio over video and record the selected URL in the manifest/log.
- Use `yt-dlp` only as a fallback for public, authorized media. Do not use it to bypass access restrictions.
