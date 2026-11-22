# IPTV Organizer

Automatically downloads the source M3U and publishes a sorted playlist at `dist/iptv-sorted.m3u`.

## Sorting

The playlist is grouped by content type and genre, **not by country**:

- Films: action, comedy, drama, thriller, horror, science fiction, fantasy, detective/crime, adventure, romance, historical/war, documentary, biography, western, family, music and other genres.
- Series: genre groups.
- Separate categories: cartoons, anime, kids, 18+, cinema channels, music, sports, news, educational, entertainment, cooking, radio and general TV.
- Country-only source groups are merged into general TV. Country metadata is never used as an output category.

The source sometimes provides only a film title and year, without a genre tag. Such entries are kept in `Фільми | Інші жанри`; the organizer does not invent genres.

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

## Local execution

Python 3.10+; no third-party dependencies:

```bash
python organize_playlist.py
```

Output: `dist/iptv-sorted.m3u`.
