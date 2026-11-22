# IPTV Organizer

Automatically downloads the source M3U, classifies entries, sorts them and publishes `dist/iptv-sorted.m3u` in this repository.

## Categories

- TV grouped by country where country metadata is available.
- Movies grouped by country and genre, for example `Фільми | США | Бойовики`.
- Separate groups for cartoons, kids, music, news, sports, radio and regional channels.
- Unknown or incomplete metadata is retained in fallback groups; stream URLs and source EXTINF metadata are preserved.

Classification uses `tvg-country`, `country`, the source group title, display name and selected URL path patterns. It is heuristic: missing or ambiguous source metadata may result in an unknown-country or unknown-genre group.

## Output URL

`https://raw.githubusercontent.com/sarmatik32/iptv-organizer/main/dist/iptv-sorted.m3u`

## Automatic updates

GitHub Actions downloads and rebuilds the playlist every six hours (cron: `17 */6 * * *`, UTC). A manual run is also available under **Actions → Update sorted IPTV playlist → Run workflow**.

For the first run, confirm **Settings → Actions → General → Workflow permissions → Read and write permissions**. The workflow declares `contents: write` and needs permission to commit the generated file.

## Configuration

Default source:

`https://raw.githubusercontent.com/slava-67/TV/IPTV/avto-full.m3u`

To change it, add a repository Actions variable named `SOURCE_URL`. The download timeout defaults to 90 seconds and input is limited to 100 MiB. No third-party Python packages are required.

## Local run

Requires Python 3.10+:

```bash
python organize_playlist.py
```

Generated file: `dist/iptv-sorted.m3u`.
