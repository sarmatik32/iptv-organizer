#!/usr/bin/env python3
"""Build a genre-sorted M3U playlist from the configured IPTV source."""
from __future__ import annotations

import os
import re
import concurrent.futures
import sys
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

SOURCE_URL = os.getenv("SOURCE_URL", "https://raw.githubusercontent.com/slava-67/TV/IPTV/avto-full.m3u")
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", "dist/iptv-sorted.m3u"))
TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))
PROBE_TIMEOUT = float(os.getenv("PROBE_TIMEOUT", "5"))
PROBE_WORKERS = max(1, min(16, int(os.getenv("PROBE_WORKERS", "8"))))
PROBE_LIMIT = max(0, int(os.getenv("PROBE_LIMIT", "300")))
MAX_BYTES = 150 * 1024 * 1024

GENRES = [
    ("Бойовики", ("бойовик", "боевик", "екшн", "экшн", "action")),
    ("Комедії", ("комеді", "комеди", "comedy", "юмор", "sitcom", "ситком")),
    ("Мелодрами та романтика", ("мелодрам", "melodrama", "романтик", "romance")),
    ("Драми", ("драма", "drama")),
    ("Трилери", ("трилер", "триллер", "thriller", "suspense")),
    ("Жахи", ("жах", "ужас", "horror")),
    ("Фантастика", ("фантаст", "sci-fi", "science fiction")),
    ("Фентезі", ("фентез", "фэнтези", "fantasy")),
    ("Детективи та кримінал", ("детектив", "кримінал", "криминал", "crime", "detective", "mystery", "нуар")),
    ("Пригоди", ("пригод", "adventure")),
    ("Історичні та воєнні", ("історич", "историчес", "воєн", "военн", "war", "history")),
    ("Документальні", ("документ", "documentary")),
    ("Біографічні", ("біограф", "биограф", "biography", "biopic")),
    ("Вестерни", ("вестерн", "western")),
    ("Сімейні", ("сімейн", "семейн", "family")),
    ("Музичні", ("музичн", "музыкальн", "music", "concert", "концерт")),
]

MOVIE_GROUP = re.compile(r"(фильм|фільм|кино\s*зал|kino\s*zal|кинозал|4k\s*kino)", re.I)
COUNTRY_GROUP = {
    "ua", "ukr", "ukraine", "украина", "україна", "us", "usa", "сша",
    "uk", "united kingdom", "великобритания", "велика британія",
    "de", "germany", "германия", "німеччина", "pl", "poland", "польша", "польща",
    "fr", "france", "франция", "франція", "it", "italy", "италия", "італія",
    "es", "spain", "испания", "іспанія", "tr", "turkey", "турция", "туреччина",
    "ca", "canada", "канада", "ro", "romania", "румыния", "румунія",
    "cz", "czech", "чехия", "чехія", "nl", "netherlands", "нидерланды", "нідерланди",
}

def contains(value: str, words: tuple[str, ...]) -> bool:
    return any(word in value for word in words)

def genre_for(value: str) -> str:
    value = value.casefold()
    segments = [part.strip() for part in re.split(r"[|/,;]", value) if part.strip()]
    for segment in segments:
        matches = [
            (segment.find(word), genre)
            for genre, words in GENRES
            for word in words
            if segment.find(word) >= 0
        ]
        if matches:
            return min(matches, key=lambda item: item[0])[1]
    matches = [
        (value.find(word), genre)
        for genre, words in GENRES
        for word in words
        if value.find(word) >= 0
    ]
    return min(matches, key=lambda item: item[0])[1] if matches else "Інші жанри"

def parse_entries(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.lstrip("\ufeff").splitlines()
    header = lines[0].strip() if lines and lines[0].startswith("#EXTM3U") else "#EXTM3U"
    entries: list[tuple[str, str]] = []
    pending: list[str] = []
    for raw in lines[1:] if lines and lines[0].startswith("#EXTM3U") else lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            pending = [line]
        elif line.startswith("#"):
            if pending:
                pending.append(line)
        elif pending:
            entries.append(("\n".join(pending), line))
            pending = []
    return header, entries

def metadata(extinf: str) -> tuple[str, str]:
    match = re.search(r'group-title="([^"]*)"', extinf, re.I)
    group = re.sub(r"\s+", " ", match.group(1).strip()) if match else ""
    name = extinf.split(",", 1)[1].strip() if "," in extinf else "Без назви"
    return group, name

def classify(group: str, name: str, url: str) -> str:
    value = f"{group} {name}".casefold()
    group_value = group.strip().casefold()

    if contains(value, ("18+", "xxx", "для дорос", "для взрос", "adult")):
        return "18+"
    if contains(value, ("аніме", "аниме", "anime", "manga")):
        return "Аніме"
    if contains(value, ("мультф", "мультик", "cartoon", "animation", "анімац", "анимац")):
        return "Мультфільми"
    if contains(value, ("дитяч", "детск", "kids", "children", "baby", "junior")):
        return "Дитячі"

    is_movie = bool(MOVIE_GROUP.search(group)) or bool(re.search(r"/(films?|movies?|vod)/|/content/stream/(new|films)/", url, re.I))
    if is_movie:
        return f"Фільми | {genre_for(name)}"

    if contains(value, ("серіал", "сериал", "series", "serial")):
        return f"Серіали | {genre_for(name)}"

    if contains(value, ("радіо", "радио", "radio")):
        return "Радіо"
    if contains(value, ("музик", "музык", "music", "mtv", "concert", "концерт")):
        return "Музика"
    if contains(value, ("спорт", "sport", "football", "футбол", "boxing", "бокс", "hockey", "хокей", "tennis", "теніс")):
        return "Спорт"
    if contains(value, ("новин", "новост", "news", "інформац", "информац")):
        return "Новини"
    if contains(value, ("пізнав", "познав", "наук", "science", "discovery", "history", "істор", "истор", "nature", "природ", "animal", "тварин", "документ")):
        return "Пізнавальні"
    if contains(value, ("relax", "релакс", "nature", "природа", "travel", "подорож")):
        return "Пізнавальні"
    if contains(value, ("кухня", "кулинар", "culinary", "food", "їжа")):
        return "Кулінарія"
    if contains(value, ("розваж", "развлек", "entertainment", "show", "шоу", "реаліті", "реалити", "reality", "гумор", "юмор")):
        return "Розважальні"
    if contains(value, ("кино", "кіно", "movie", "film", "cinema", "kino+", "кіно+", "киноканал", "кіно канал")):
        return "Кіно та серіали"

    if group_value in COUNTRY_GROUP or group_value == "общие" or re.match(r"^[tт]ест", group_value, re.I) or re.search(r"[🇺🇦🇺🇸🇬🇧🇩🇪🇫🇷🇵🇱🇮🇹🇪🇸🇹🇷🇨🇦🇨🇿🇳🇱🇷🇴🇦🇲🇺🇿🇦🇿]", group):
        return "ТБ | Загальні"
    if group_value in {"default", "undefined", "none", "other", "others", "разное", "різне", ""}:
        return "ТБ | Загальні"
    if re.search(r"(test|тест|vpn|uplink|internet|telecom|нет|оргтех|datacamp|turon|инет|велком)", group, re.I):
        return "ТБ | Загальні"
    return group.strip()

def rewrite_extinf(extinf: str, category: str) -> str:
    if re.search(r'group-title="[^"]*"', extinf, re.I):
        return re.sub(r'group-title="[^"]*"', lambda _: f'group-title="{category}"', extinf, count=1, flags=re.I)
    comma = extinf.find(",")
    return extinf if comma < 0 else extinf[:comma] + f' group-title="{category}"' + extinf[comma:]

def quality_for(extinf: str, group: str, name: str, url: str) -> str:
    """Use explicit source markers; unknown quality is conservatively labeled SD."""
    value = f"{extinf} {group} {name} {url}".casefold()
    hd_patterns = (
        r"\b(?:4k|8k|uhd|ultra[ ._-]?hd|fhd|full[ ._-]?hd)\b",
        r"\b(?:2160|1440|1080|720)[pi]?\b",
        r"(?:^|[\s._/?=&-])hd(?:$|[\s._/?&#=-])",
        r"high[ ._-]?definition",
    )
    return "HD" if any(re.search(pattern, value, re.I) for pattern in hd_patterns) else "SD"


def probe_stream(url: str) -> tuple[str, str]:
    """Return stream type and seekability using HLS markers or HTTP byte ranges."""
    lower = url.casefold()
    if ".m3u8" in lower:
        request = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; IPTV-Organizer/3.2)",
            "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
            "Range": "bytes=0-1048575",
        })
        try:
            with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT) as response:
                body = response.read(1024 * 1024 + 1).decode("utf-8-sig", errors="replace")
            if not body.lstrip().startswith("#EXTM3U"):
                return "UNKNOWN", "unknown"
            if "#EXT-X-ENDLIST" in body or "#EXT-X-PLAYLIST-TYPE:VOD" in body:
                return "VOD", "yes"
            if "#EXT-X-STREAM-INF" in body or "#EXT-X-MEDIA:" in body:
                return "UNKNOWN", "unknown"
            if len(body.encode("utf-8")) <= 1024 * 1024:
                return "LIVE", "no"
            return "UNKNOWN", "unknown"
        except Exception:
            return "UNKNOWN", "unknown"

    if re.search(r"\.(?:mp4|m4v|mkv|avi|mov|webm)(?:$|[?#])", lower):
        request = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; IPTV-Organizer/3.2)",
            "Range": "bytes=0-0",
        })
        try:
            with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT) as response:
                seekable = response.status == 206 or response.headers.get("Accept-Ranges", "").casefold() == "bytes"
                return ("VOD", "yes") if seekable else ("UNKNOWN", "no")
        except Exception:
            return "UNKNOWN", "unknown"
    return "UNKNOWN", "unknown"


def initial_stream_type(group: str, name: str, category: str, url: str) -> str:
    value = f"{group} {name} {url}".casefold()
    if re.search(r"/(?:live|livetv|channel|channels)(?:/|$)|[?&](?:type|mode)=live\b", value):
        return "LIVE"
    if re.search(r"/(?:movie|movies|film|films|vod|series|episode|episodes)(?:/|$)", value):
        return "VOD"
    if category.startswith(("Фільми |", "Серіали |")):
        return "VOD"
    if category in {
        "ТБ | Загальні", "Спорт", "Новини", "Музика", "Радіо",
        "Розважальні", "Пізнавальні", "Кулінарія", "Кіно та серіали",
    }:
        return "LIVE"
    return "UNKNOWN"


def organize(source: str) -> tuple[str, Counter[str]]:
    header, entries = parse_entries(source)
    if not entries:
        raise ValueError("У вихідному M3U не знайдено жодного запису")

    prepared = []
    probe_candidates = []
    seen_probe_urls = set()
    for extinf, url in entries:
        group, name = metadata(extinf)
        base_category = classify(group, name, url)
        stream_type = initial_stream_type(group, name, base_category, url)
        if ".m3u8" in url.casefold() or re.search(r"\.(?:mp4|m4v|mkv|avi|mov|webm)(?:$|[?#])", url, re.I):
            probe_urls.add(url)
        prepared.append((extinf, url, group, name, base_category, stream_type))

    probe_urls = probe_candidates[:PROBE_LIMIT]
    probe_results = {}
    if probe_urls:
        with concurrent.futures.ThreadPoolExecutor(max_workers=PROBE_WORKERS) as executor:
            futures = {executor.submit(probe_stream, url): url for url in probe_urls}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    probe_results[url] = future.result()
                except Exception:
                    probe_results[url] = ("UNKNOWN", "unknown")

    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for extinf, url, group, name, base_category, stream_type in prepared:
        probed_type, seekability = probe_results.get(url, ("UNKNOWN", "unknown"))
        if probed_type in {"LIVE", "VOD"}:
            stream_type = probed_type
        elif url in probe_results and re.search(r"\.(?:mp4|m4v|mkv|avi|mov|webm)(?:$|[?#])", url, re.I):
            stream_type = "UNKNOWN"
        quality = quality_for(extinf, group, name, url)
        seek_label = "так" if seekability == "yes" else "не підтверджено"
        vod_seek_group = f" | Перемотування: {seek_label}" if stream_type == "VOD" else ""
        category = f"{quality} | {stream_type}{vod_seek_group} | {base_category}"
        rewritten = rewrite_extinf(extinf, category)
        grouped.setdefault(category, []).append((name.casefold(), rewritten, url))

    output = [header]
    counts: Counter[str] = Counter()
    quality_order = {"HD": 0, "SD": 1}
    type_order = {"LIVE": 0, "VOD": 1, "UNKNOWN": 2}

    def sort_category(category: str) -> tuple[int, int, str]:
        quality, stream_type, subcategory = category.split(" | ", 2)
        return quality_order.get(quality, 2), type_order.get(stream_type, 3), subcategory.casefold()

    for category in sorted(grouped, key=sort_category):
        output.append(f"\n# ===== {category} ({len(grouped[category])}) =====")
        for _, extinf, url in sorted(grouped[category], key=lambda item: item[0]):
            output.extend((extinf, url))
            counts[category] += 1
    return "\n".join(output) + "\n", counts

def download() -> str:
    request = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; IPTV-Organizer/3.1)",
        "Accept": "application/vnd.apple.mpegurl, audio/x-mpegurl, text/plain, */*",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Вихідний плейлист перевищує 150 МБ")
    decoded = raw.decode("utf-8-sig", errors="replace")
    if not decoded.lstrip().startswith("#EXTM3U"):
        raise ValueError("Джерело не повернуло коректний M3U-файл")
    return decoded

def main() -> int:
    temp_name: str | None = None
    try:
        result, counts = organize(download())
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=OUTPUT_FILE.parent, delete=False) as temp:
            temp.write(result)
            temp_name = temp.name
        os.replace(temp_name, OUTPUT_FILE)
        print(f"Готово: {OUTPUT_FILE}; позицій: {sum(counts.values())}; категорій: {len(counts)}")
        for category, count in sorted(counts.items(), key=lambda item: item[0].casefold()):
            print(f"{category}: {count}")
        return 0
    except Exception as exc:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
        print(f"Помилка: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
