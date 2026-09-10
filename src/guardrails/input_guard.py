import re
from typing import Tuple

BLOCKED_PATTERNS = [
    r"ignore previous instructions",
    r"bypass authorization",
    r"override spend limit",
    r"drop table",
    r"delete from",
    r"grant admin"
]

def check_input_safety(query: str) -> Tuple[bool, str]:
    """Validates user query against injection attacks or policy bypass attempts."""
    query_lower = query.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, query_lower):
            return False, f"Input Safety Guard Triggered: Query matches restricted pattern '{pattern}'."
    return True, "Input safety check passed."
