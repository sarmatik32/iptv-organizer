# IPTV Organizer

Automatic M3U playlist downloader and genre sorter.

## Categories

The playlist is grouped by content, **not by country**:

- Films: action, comedy, drama, thriller, horror, science fiction, fantasy, detective/crime, adventure, romance, historical/war, documentary, biography and other genres.
- Series: the same genre groups.
- Cartoons, anime and kids.
- Music, sport, news, educational, entertainment and radio.
- Original meaningful source group names are retained as a fallback; unknown entries go to "Інше".

The sorter intentionally ignores `tvg-country`, country names and country codes.

## Permanent M3U URL

`https://raw.githubusercontent.com/sarmatik32/iptv-organizer/main/dist/iptv-sorted.m3u`

The link becomes available after the first successful GitHub Actions run.

## Automatic updates

GitHub Actions runs every six hours (UTC) and can also be started manually:

**Actions → Update sorted IPTV playlist → Run workflow**

Workflow permissions required:

**Settings → Actions → General → Workflow permissions → Read and write permissions**

The workflow verifies the generated M3U before committing it. A failed download or invalid source fails the job and does not replace the last valid playlist.

## Source

Default source:

`https://raw.githubusercontent.com/slava-67/TV/IPTV/avto-full.m3u`

Optional repository Actions variable: `SOURCE_URL`.

## Local execution

Python 3.10+; no external dependencies:

```bash
python organize_playlist.py
```

Output: `dist/iptv-sorted.m3u`.
