#!/usr/bin/env python3
"""Download and sort an IPTV M3U playlist by content genre."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

SOURCE_URL = os.getenv("SOURCE_URL", "https://raw.githubusercontent.com/slava-67/TV/IPTV/avto-full.m3u")
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", "dist/iptv-sorted.m3u"))
TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))
MAX_BYTES = 150 * 1024 * 1024

# Specific genres are checked before broad categories.
GENRES = [
    ("Бойовики", ("бойовик", "боевик", "action", "екшн", "приключенческий боевик")),
    ("Комедії", ("комеді", "комеди", "comedy", "юмор", "sitcom", "ситком")),
    ("Мелодрами та романтика", ("мелодрам", "melodrama", "романтик", "romance", "любов")),
    ("Драми", ("драма", "drama")),
    ("Трилери", ("трилер", "триллер", "thriller", "suspense")),
    ("Жахи", ("жах", "ужас", "horror", "страшилки")),
    ("Фантастика", ("фантаст", "sci-fi", "science fiction", "научная фантастика")),
    ("Фентезі", ("фентез", "фэнтези", "fantasy", "казк")),
    ("Детективи та кримінал", ("детектив", "кримінал", "криминал", "crime", "detective", "mystery", "нуар")),
    ("Пригоди", ("пригод", "adventure")),
    ("Мелодрами та романтика", ("романтик", "romance", "любов", "мелодрам")),
    ("Історичні та воєнні", ("історич", "историчес", "воєн", "военн", "war", "history")),
    ("Документальні", ("документ", "documentary", "науково-популяр")),
    ("Біографічні", ("біограф", "биограф", "biography", "biopic")),
    ("Музичні", ("музичн", "музыкальн", "music", "concert", "концерт")),
    ("Спортивні", ("спорт", "sport", "football", "футбол", "boxing", "бокс")),
    ("Анімація", ("анімац", "анимац", "animation", "cartoon", "мультф", "мультик")),
    ("Аніме", ("аніме", "аниме", "anime", "manga")),
    ("Дитячі", ("дитяч", "детск", "kids", "children", "baby")),
]

CATEGORY_RULES = [
    ("Аніме", ("аніме", "аниме", "anime", "manga")),
    ("Мультфільми", ("мультф", "мультик", "cartoon", "animation", "анімац", "анимац")),
    ("Дитячі", ("дитяч", "детск", "kids", "children", "baby", "junior")),
    ("Музика", ("музик", "музык", "music", "mtv", "concert", "концерт", "шлягер")),
    ("Спорт", ("спорт", "sport", "football", "футбол", "boxing", "бокс", "hockey", "хокей", "tennis", "теннис")),
    ("Новини", ("новин", "новост", "news", "інформац", "информац", "newsroom")),
    ("Пізнавальні", ("пізнав", "познав", "наук", "science", "discovery", "history", "істор", "истор", "nature", "природ", "animal", "тварин", "документ")),
    ("Розважальні", ("розваж", "развлек", "entertainment", "show", "шоу", "реаліті", "реалити", "reality", "гумор", "юмор", "комеді", "комеди")),
    ("Кіно", ("фільм", "фильм", "кіно", "кино", "movie", "movies", "film", "vod", "відеотека", "видеотека", "serial", "серіал", "сериал", "series")),
    ("Радіо", ("радіо", "радио", "radio")),
]

def parse_entries(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.lstrip("\ufeff").splitlines()
    header = lines[0].strip() if lines and lines[0].startswith("#EXTM3U") else "#EXTM3U"
    entries: list[tuple[str, str]] = []
    pending: list[str] = []
    source_lines = lines[1:] if lines and lines[0].startswith("#EXTM3U") else lines
    for raw in source_lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            if pending:
                pending = []
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


def has_any(value: str, words: tuple[str, ...]) -> bool:
    return any(word in value for word in words)


def genre_for(value: str) -> str:
    for genre, words in GENRES:
        if has_any(value, words):
            return genre
    return "Інші жанри"


def classify(group: str, name: str, url: str, extinf: str) -> str:
    # Do not use country names, country codes or tvg-country in classification.
    hay = f"{group} {name}".casefold()
    compact_group = group.strip().casefold()

    # Keep broad content types separate; use genre for movies/series where detectable.
    if has_any(hay, ("аніме", "аниме", "anime", "manga")):
        return "Аніме"
    if has_any(hay, ("мультф", "мультик", "cartoon", "animation", "анімац", "анимац")):
        return "Мультфільми"
    if has_any(hay, ("дитяч", "детск", "kids", "children", "baby", "junior")):
        return "Дитячі"
    if has_any(hay, ("радіо", "радио", "radio")):
        return "Радіо"

    movie_markers = ("фільм", "фильм", "кіно", "кино", "movie", "movies", "film", "vod", "відеотека", "видеотека")
    series_markers = ("серіал", "сериал", "series", "serial")
    url_markers = ("/films/", "/film/", "/movies/", "/series/", "/vod/", "/kino/")
    is_movie = has_any(hay, movie_markers) or any(marker in url.casefold() for marker in url_markers)
    is_series = has_any(hay, series_markers)

    if is_movie:
        return f"Фільми | {genre_for(hay)}"
    if is_series:
        return f"Серіали | {genre_for(hay)}"

    # A source group named only after a movie genre (e.g. "Боевики") is a movie genre.
    if genre_for(group.casefold()) != "Інші жанри":
        return f"Фільми | {genre_for(group.casefold())}"

    for category, words in CATEGORY_RULES:
        if category in ("Аніме", "Мультфільми", "Дитячі", "Кіно", "Радіо"):
            continue
        if has_any(hay, words):
            return category

    # Preserve meaningful source genre/group names rather than guessing a country.
    if compact_group and compact_group not in {"default", "undefined", "none", "other", "others", "разное", "різне"}:
        country_only = {
            "ua", "ukr", "ukraine", "украина", "україна", "us", "usa", "сша",
            "uk", "united kingdom", "великобритания", "велика британія",
            "de", "germany", "германия", "німеччина", "pl", "poland", "польша", "польща",
            "fr", "france", "франция", "франція", "it", "italy", "италия", "італія",
            "es", "spain", "испания", "іспанія", "tr", "turkey", "турция", "туреччина",
            "ca", "canada", "канада", "ro", "romania", "румыния", "румунія",
            "cz", "czech", "чехия", "чехія", "nl", "netherlands", "нидерланды", "нідерланди",
        }
        if compact_group not in country_only:
            return group.strip()
    return "Загальні телеканали"


def rewrite_extinf(extinf: str, category: str) -> str:
    if re.search(r'group-title="[^"]*"', extinf, re.I):
        return re.sub(r'group-title="[^"]*"', lambda _: f'group-title="{category}"', extinf, count=1, flags=re.I)
    comma = extinf.find(",")
    return extinf if comma < 0 else extinf[:comma] + f' group-title="{category}"' + extinf[comma:]


def organize(source: str) -> tuple[str, Counter[str]]:
    header, entries = parse_entries(source)
    if not entries:
        raise ValueError("У вихідному файлі не знайдено жодного M3U-запису")
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for extinf, url in entries:
        group, name = metadata(extinf)
        category = classify(group, name, url, extinf)
        grouped.setdefault(category, []).append((name.casefold(), rewrite_extinf(extinf, category), url))
    output = [header]
    counts: Counter[str] = Counter()
    for category in sorted(grouped, key=str.casefold):
        output.append(f"\n# ===== {category} ({len(grouped[category])}) =====")
        for _, extinf, url in sorted(grouped[category], key=lambda item: item[0]):
            output.extend((extinf, url))
            counts[category] += 1
    return "\n".join(output) + "\n", counts


def download() -> str:
    request = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; IPTV-Organizer/3.0)",
        "Accept": "application/vnd.apple.mpegurl, audio/x-mpegurl, text/plain, */*",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError(f"Плейлист завеликий: понад {MAX_BYTES // (1024 * 1024)} МБ")
    decoded = raw.decode("utf-8-sig", errors="replace")
    if not decoded.lstrip().startswith("#EXTM3U"):
        raise ValueError("Джерело не повернуло коректний M3U-файл (очікувався #EXTM3U)")
    return decoded


def main() -> int:
    temp_name: str | None = None
    try:
        source = download()
        result, counts = organize(source)
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=OUTPUT_FILE.parent, delete=False) as temp:
            temp.write(result)
            temp_name = temp.name
        os.replace(temp_name, OUTPUT_FILE)
        total = sum(counts.values())
        print(f"Успішно: {OUTPUT_FILE}; каналів/позицій: {total}; категорій: {len(counts)}")
        for category, count in sorted(counts.items(), key=lambda item: item[0].casefold()):
            print(f"{category}: {count}")
        return 0
    except Exception as exc:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
        print(f"Помилка формування плейлиста: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
