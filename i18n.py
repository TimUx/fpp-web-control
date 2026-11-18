"""Translations shared by the server and the browser.

Every language is one flat JSON file in i18n/ (``de.json``, ``en.json``, ...):
``"key": "Text with {placeholder}"``. Keys starting with ``_`` describe the
language itself (``_language``: its own name, ``_locale``: for dates and
numbers in the browser). A key missing in one language falls back to English,
then to German, then to the key itself, so a new language can start small.

Adding a language: copy en.json to <code>.json (e.g. fr.json), translate the
values, restart. It is picked up automatically.
"""

import json
import os
import re
from datetime import time as dt_time
from typing import Dict, Iterable, List, Optional

I18N_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n")
FALLBACK_CHAIN = ("en", "de")
_CODE = re.compile(r"^[a-z]{2,3}$")


def _load() -> Dict[str, Dict[str, str]]:
    catalogs: Dict[str, Dict[str, str]] = {}
    try:
        names = sorted(os.listdir(I18N_DIR))
    except OSError:
        return catalogs
    for name in names:
        code, ext = os.path.splitext(name)
        if ext != ".json" or not _CODE.match(code):
            continue
        with open(os.path.join(I18N_DIR, name), encoding="utf-8") as f:
            data = json.load(f)
        catalogs[code] = {str(k): str(v) for k, v in data.items()}
    return catalogs


CATALOGS = _load()
SUPPORTED: List[str] = sorted(CATALOGS)


def normalize_language(value: Optional[str]) -> Optional[str]:
    """'en-US' -> 'en' if English is available, else None."""
    if not value:
        return None
    code = str(value).strip().lower().replace("_", "-").split("-", 1)[0]
    return code if code in CATALOGS else None


def from_accept_language(header: Optional[str]) -> Optional[str]:
    """Best supported language from an Accept-Language header."""
    if not header:
        return None
    ranked = []
    for index, part in enumerate(header.split(",")):
        pieces = part.strip().split(";")
        weight = 1.0
        for param in pieces[1:]:
            param = param.strip()
            if param.startswith("q="):
                try:
                    weight = float(param[2:])
                except ValueError:
                    weight = 0.0
        ranked.append((-weight, index, pieces[0]))
    for _, _, tag in sorted(ranked):
        code = normalize_language(tag)
        if code:
            return code
    return None


def catalog(lang: str) -> Dict[str, str]:
    """All strings for a language, gaps filled from the fallbacks."""
    merged: Dict[str, str] = {}
    for code in reversed((lang,) + FALLBACK_CHAIN):
        merged.update(CATALOGS.get(code, {}))
    return merged


def translate(lang: str, key: str, **params) -> str:
    for code in (lang,) + FALLBACK_CHAIN:
        text = CATALOGS.get(code, {}).get(key)
        if text is not None:
            break
    else:
        text = key
    if params:
        for name, value in params.items():
            text = text.replace("{" + name + "}", str(value))
    return text


def language_names(codes: Iterable[str]) -> Dict[str, str]:
    return {code: CATALOGS.get(code, {}).get("_language", code) for code in codes}


def format_time(value: dt_time, lang: str) -> str:
    """24 h for most languages, 12 h (5:30 PM) for English."""
    if lang == "en":
        return value.strftime("%I:%M %p").lstrip("0")
    return value.strftime("%H:%M")


def format_date(value, lang: str) -> str:
    if lang == "en":
        return f"{value.month}/{value.day}/{value.year}"
    return value.strftime("%d.%m.%Y")
