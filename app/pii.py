from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.IGNORECASE),
    "phone_vn": re.compile(r"(?:\+84|0)[ \.-]?\d{3}[ \.-]?\d{3}[ \.-]?\d{3,4}"),
    "cccd": re.compile(r"\b\d{12}\b"),
    "credit_card": re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    "passport": re.compile(r"\b(?:passport|h\u1ed9\s*chi\u1ebfu|ho\s*chieu)\b(?:\s*[:#-]?\s*[A-Z0-9]{6,12})?", re.IGNORECASE),
    "vn_address": re.compile(
        r"\b(?:s\u1ed1|so|\u0111\u01b0\u1eddng|duong|ph\u01b0\u1eddng|phuong|qu\u1eadn|quan|x\u00e3|xa|huy\u1ec7n|huyen|t\u1ec9nh|tinh|th\u00e0nh\s+ph\u1ed1|thanh\s+pho|tp\.?|khu\s+ph\u1ed1|khu\s+pho|ng\u00f5|ngo|h\u1ebfm|hem)\b(?:\s+[^\n,;:.]{1,60})?",
        re.IGNORECASE,
    ),
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = pattern.sub(f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
