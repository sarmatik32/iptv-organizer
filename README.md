# IPTV Organizer

Automatically downloads the source M3U and publishes a sorted playlist at `dist/iptv-sorted.m3u`.

## Sorting

The playlist is grouped in this order: **HD / SD → LIVE / VOD / UNKNOWN → content category and genre**.

- **HD** — source explicitly marks HD, Full HD, 720p/1080p/1440p/2160p, 4K, 8K or UHD.
- **SD** — no explicit HD quality marker was found; quality is not guessed.
- **LIVE** — live TV/radio/channel streams, based on source group metadata, URL hints or a live HLS playlist.
- **VOD** — films and series, VOD URL paths, completed HLS playlists, or direct media files with HTTP byte-range support.
- **UNKNOWN** — stream type cannot be confirmed. The script does not force uncertain entries into LIVE or VOD.
- VOD groups additionally show **Перемотування: так** when HLS VOD markers or HTTP byte-range support confirm seeking; otherwise they show **Перемотування: не підтверджено**.

HLS playlists are inspected for `#EXT-X-ENDLIST` and `#EXT-X-PLAYLIST-TYPE:VOD`. Direct MP4/MKV/AVI/MOV/WebM links are tested with an HTTP Range request. Probes run concurrently with a bounded worker pool and short timeout. Servers that block probes or hide their capabilities can cause UNKNOWN or an unconfirmed seeking label; this is not proof that playback or seeking is impossible.

Films are grouped by genre where metadata contains one. Genres include action, comedy, drama, thriller, horror, science fiction, fantasy, detective/crime, adventure, romance, historical/war, documentary, biography, western, family, music and other genres. Series are grouped by genre. Other categories include cartoons, anime, kids, 18+, cinema channels, music, sports, news, educational, entertainment, cooking, radio and general TV. Countries are not used as output categories.

## Permanent M3U URL

`https://raw.githubusercontent.com/sarmatik32/iptv-organizer/main/dist/iptv-sorted.m3u`

## Automatic updates

GitHub Actions runs every six hours (UTC) and can be started manually:

**Actions → Update sorted IPTV playlist → Run workflow**

The workflow validates that the generated file is a valid, non-empty M3U with at least 1,000 entries before publishing.

Required repository setting:

**Settings → Actions → General → Workflow permissions → Read and write permissions**

## Source

`https://raw.githubusercontent.com/slava-67/TV/IPTV/avto-full.m3u`

The branch name is `IPTV`, and the file path is `avto-full.m3u`.

Optional Actions variable: `SOURCE_URL`.

Optional probe settings:
- `PROBE_TIMEOUT` — per-stream probe timeout in seconds (default: `5`).
- `PROBE_WORKERS` — concurrent probes, clamped to 1–16 (default: `8`).
- `PROBE_LIMIT` — maximum number of unique streams actively checked per refresh (default: `300`).

## Local execution

Python 3.10+; no third-party dependencies:

```bash
python organize_playlist.py
```

Output: `dist/iptv-sorted.m3u`.
