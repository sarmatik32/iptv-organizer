#!/usr/bin/env python3
"""Download and organize an M3U playlist into stable, human-readable groups."""
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
TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "90"))
MAX_BYTES = 100 * 1024 * 1024

COUNTRIES = {
    "Україна": [r"україн", r"ukraine", r"\bua\b", r"\bukr\b"],
    "США": [r"сша", r"united states", r"\busa\b", r"\bus\b"],
    "Велика Британія": [r"велика британія", r"united kingdom", r"\buk\b", r"britain", r"англія"],
    "Німеччина": [r"німеччин", r"germany", r"\bde\b"],
    "Франція": [r"франці", r"france", r"\bfr\b"],
    "Польща": [r"польщ", r"poland", r"\bpl\b"],
    "Італія": [r"італі", r"italy", r"\bit\b"],
    "Іспанія": [r"іспані", r"spain", r"\bes\b"],
    "Туреччина": [r"туреччин", r"turkey", r"\btr\b"],
    "Канада": [r"канада", r"canada", r"\bca\b"],
    "Австралія": [r"австралі", r"australia", r"\bau\b"],
    "Японія": [r"япон", r"japan", r"\bjp\b"],
    "Південна Корея": [r"південна корея", r"south korea", r"\bkr\b"],
    "Китай": [r"китай", r"china", r"\bcn\b"],
    "Індія": [r"інді", r"india", r"\bin\b"],
    "Румунія": [r"румун", r"romania", r"\bro\b"],
    "Чехія": [r"чех", r"czech", r"\bcz\b"],
    "Нідерланди": [r"нідерланд", r"netherlands", r"holland", r"\bnl\b"],
    "Бельгія": [r"бельгі", r"belgium", r"\bbe\b"],
    "Швеція": [r"швеці", r"sweden", r"\bse\b"],
    "Норвегія": [r"норвегі", r"norway", r"\bno\b"],
    "Інші країни": [],
}
COUNTRY_PATTERNS = {name: [re.compile(p, re.I) for p in patterns] for name, patterns in COUNTRIES.items() if patterns}
GENRES = [
    ("Бойовики", ["бойовик", "екшн", "action"]),
    ("Комедії", ["комеді", "comedy"]),
    ("Драми", ["драма", "drama"]),
    ("Трилери", ["трилер", "thriller"]),
    ("Фантастика та фентезі", ["фантаст", "фентезі", "sci-fi", "science fiction", "fantasy"]),
    ("Жахи", ["жах", "horror"]),
    ("Детективи та кримінал", ["детектив", "кримінал", "crime", "mystery"]),
    ("Пригоди", ["пригод", "adventure"]),
    ("Мелодрами", ["мелодрам", "романтич", "romance"]),
    ("Документальні", ["документал", "documentary"]),
    ("Історичні та воєнні", ["історич", "воєн", "військов", "history", "war"]),
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


def country_for(value: str) -> str | None:
    for country, patterns in COUNTRY_PATTERNS.items():
        if any(pattern.search(value) for pattern in patterns):
            return country
    return None


def classify(group: str, name: str, url: str, extinf: str) -> str:
    hay = f"{group} {name}".casefold()
    country_hint = ""
    for attribute in ("tvg-country", "country"):
        match = re.search(rf'{attribute}="([^"]+)"', extinf, re.I)
        if match:
            country_hint = match.group(1)
            break
    country = country_for(f"{country_hint} {hay}") or "Інші країни"

    if any(word in hay for word in ("мультф", "анімац", "cartoon", "animation", "anime", "аніме")):
        return "Мультфільми"
    if any(word in hay for word in ("дитяч", "kids", "children", "baby")):
        return "Дитячі"
    if any(word in hay for word in ("муз", "music", "mtv", "музич")):
        return "Музика"
    if any(word in hay for word in ("радіо", "radio")):
        return "Радіо"
    if any(word in hay for word in ("новин", "news", "інформац", "інфо")):
        return "Новини"
    if any(word in hay for word in ("спорт", "sport", "football", "футбол")):
        return "Спорт"
    if any(word in hay for word in ("регіон", "облас", "міст", "local")):
        return "Регіональні"

    movie_markers = ("фільм", "фильм", "кіно", "kino", "movie", "film", "серіал", "series", "vod", "kino zal")
    movie_url_markers = ("/films/", "/film/", "/movies/", "/series/", "/vod/")
    if any(word in hay for word in movie_markers) or any(word in url.casefold() for word in movie_url_markers):
        genre = next((label for label, words in GENRES if any(word in hay for word in words)), "Інші фільми")
        return f"Фільми | {country} | {genre}"

    detected_country = country_for(hay)
    if detected_country:
        return f"ТБ | {detected_country}"
    if group and group.casefold() not in {"default", "undefined", "none"}:
        return f"ТБ | {group}"
    return "ТБ | Інші"


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
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "IPTV-Playlist-Organizer/2.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Плейлист перевищує ліміт 100 МБ")
    decoded = raw.decode("utf-8-sig", errors="replace")
    if "#EXTM3U" not in decoded[:200]:
        raise ValueError("Джерело не схоже на M3U-плейлист")
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
        print(f"Збережено: {OUTPUT_FILE}; позицій: {sum(counts.values())}")
        for category, count in sorted(counts.items(), key=lambda item: item[0].casefold()):
            print(f"{category}: {count}")
        return 0
    except Exception as exc:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
        print(f"Помилка формування плейлиста: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
