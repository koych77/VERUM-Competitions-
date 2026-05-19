import re


NICKNAME_PREFIX_RE = re.compile(r"^(?:b[\s-]*boy|b[\s-]*girl|bboy|bgirl)\s*[:\-–—.]?\s*", re.IGNORECASE)


def normalize_nickname(value: str | None) -> str:
    text = " ".join(str(value or "").strip().split())
    previous = None
    while text and text != previous:
        previous = text
        text = NICKNAME_PREFIX_RE.sub("", text).strip()
    return text.upper()


def normalize_directory_key(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())
