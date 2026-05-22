"""
helpers.py - Shared utility functions used across all stages.
"""

import re
import hashlib
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Text Normalization ───────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """
    Normalize text for deduplication or comparison.
    Strips punctuation, extra whitespace, and lowercases.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def hash_text(text: str) -> str:
    """Return a stable MD5 hash of normalized text."""
    normalized = normalize_text(text)
    return hashlib.md5(normalized.encode()).hexdigest()


def truncate(text: str, max_len: int = 120) -> str:
    """Truncate text to max_len chars with ellipsis."""
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


# ─── Date Parsing ─────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
    r"\d{1,2}\s+\w+\s+\d{4}",
    r"\w+\s+\d{1,2},?\s+\d{4}",
]


def parse_date(text: str) -> Optional[str]:
    """
    Attempt to extract a date string from arbitrary text.
    Returns the raw match or None.
    """
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return None


# ─── Keyword Extraction ───────────────────────────────────────────────────────

def extract_by_keyword(text: str, keyword: str, length: int = 80) -> Optional[str]:
    """
    Find a line or snippet that starts near a keyword and return up to `length` chars.
    """
    pattern = rf"(?:{re.escape(keyword)}[\s:]*)(.*)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:length]
    return None


def detect_severity(text: str) -> str:
    """
    Classify severity from observation text.
    Returns: 'high' | 'medium' | 'low' | 'unspecified'
    """
    from src.utils.config import SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW
    lower = text.lower()
    if any(k in lower for k in SEVERITY_HIGH):
        return "high"
    if any(k in lower for k in SEVERITY_MEDIUM):
        return "medium"
    if any(k in lower for k in SEVERITY_LOW):
        return "low"
    return "unspecified"


# ─── Image Utilities ──────────────────────────────────────────────────────────

def image_to_base64(image_bytes: bytes) -> str:
    """Encode raw image bytes as a base64 string."""
    import base64
    return base64.b64encode(image_bytes).decode("utf-8")


def is_large_enough(width: int, height: int, min_dim: int = 100) -> bool:
    """Return True if image meets the minimum dimension requirement."""
    return width >= min_dim and height >= min_dim


# ─── Logging Setup ────────────────────────────────────────────────────────────

def setup_logger(name: str = "ddr", level: int = logging.INFO) -> logging.Logger:
    """Configure and return a logger with console output."""
    _logger = logging.getLogger(name)
    if not _logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                              datefmt="%H:%M:%S")
        )
        _logger.addHandler(handler)
    _logger.setLevel(level)
    return _logger


# ─── Progress Reporting ───────────────────────────────────────────────────────

def progress(stage: str, step: str, callback=None):
    """
    Emit a progress message.
    If callback is provided it must accept (stage: str, step: str).
    Otherwise prints to stdout.
    """
    msg = f"[{stage}] {step}"
    if callback:
        callback(stage, step)
    else:
        print(msg)


# ─── Timestamp ────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
