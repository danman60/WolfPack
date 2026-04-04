"""Resilient JSON extraction from LLM responses.

LLMs often wrap JSON in markdown fences, reasoning tags, or chain-of-thought
text. This module extracts the JSON through multiple fallback strategies,
recovering responses that would otherwise be wasted API calls.

Pure utility — no state, no DB, no side effects.
"""

import json
import re
import logging
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)


def extract_json(raw_response: str) -> Tuple[Optional[Any], str]:
    """Extract JSON and reasoning from an LLM response.

    Returns (parsed_json, reasoning_text).
    Falls back through multiple strategies.
    """
    if not raw_response or not raw_response.strip():
        return None, ""

    reasoning = ""
    cleaned = raw_response.strip()

    # Strategy 1: Extract <reasoning> tag content, then JSON after it
    reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', cleaned, re.DOTALL)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
        # Remove reasoning tag, try to parse remainder
        remainder = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned, flags=re.DOTALL).strip()
        parsed = _try_parse_json(remainder)
        if parsed is not None:
            return parsed, reasoning

    # Strategy 2: Markdown code fence ```json ... ```
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', cleaned, re.DOTALL)
    if fence_match:
        parsed = _try_parse_json(fence_match.group(1))
        if parsed is not None:
            # Reasoning is everything before the code fence
            pre_fence = cleaned[:fence_match.start()].strip()
            return parsed, reasoning or pre_fence

    # Strategy 3: First { to last } or first [ to last ]
    parsed, json_start = _extract_braces(cleaned)
    if parsed is not None:
        pre_json = cleaned[:json_start].strip() if json_start > 0 else ""
        return parsed, reasoning or pre_json

    # Strategy 4: Fix common issues and retry
    fixed = _fix_common_issues(cleaned)
    if fixed != cleaned:
        parsed, json_start = _extract_braces(fixed)
        if parsed is not None:
            return parsed, reasoning

    # Total failure
    logger.warning(f"Failed to extract JSON from response ({len(raw_response)} chars)")
    logger.debug(f"Raw response preview: {raw_response[:500]}")
    return None, raw_response


def _try_parse_json(text: str) -> Optional[Any]:
    """Try to parse JSON, return None on failure."""
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try fixing common issues
        fixed = _fix_common_issues(text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None


def _extract_braces(text: str) -> Tuple[Optional[Any], int]:
    """Extract JSON by finding first {/[ to last }/]."""
    # Try object first
    obj_start = text.find('{')
    obj_end = text.rfind('}')

    # Try array
    arr_start = text.find('[')
    arr_end = text.rfind(']')

    candidates = []
    if obj_start >= 0 and obj_end > obj_start:
        candidates.append((obj_start, obj_end + 1))
    if arr_start >= 0 and arr_end > arr_start:
        candidates.append((arr_start, arr_end + 1))

    # Try the earliest match first
    candidates.sort(key=lambda x: x[0])

    for start, end in candidates:
        try:
            parsed = json.loads(text[start:end])
            return parsed, start
        except json.JSONDecodeError:
            fixed = _fix_common_issues(text[start:end])
            try:
                parsed = json.loads(fixed)
                return parsed, start
            except json.JSONDecodeError:
                continue

    return None, -1


def _fix_common_issues(text: str) -> str:
    """Fix common JSON issues from LLM responses."""
    # Smart quotes to ASCII
    text = text.replace('\u201c', '"').replace('\u201d', '"')  # " "
    text = text.replace('\u2018', "'").replace('\u2019', "'")  # ' '
    text = text.replace('\u00ab', '"').replace('\u00bb', '"')  # << >>

    # Chinese quotes
    text = text.replace('\u300c', '"').replace('\u300d', '"')  # corner brackets
    text = text.replace('\uff02', '"')  # fullwidth quotation mark

    # Remove invisible characters
    invisible = [
        '\u200b',  # zero-width space
        '\u200c',  # zero-width non-joiner
        '\u200d',  # zero-width joiner
        '\ufeff',  # BOM
        '\u00a0',  # non-breaking space -> regular space
    ]
    for char in invisible:
        if char == '\u00a0':
            text = text.replace(char, ' ')
        else:
            text = text.replace(char, '')

    # Trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Single quotes to double quotes (careful — only in JSON context)
    # This is risky, so only do it if there are no double quotes at all
    if '"' not in text and "'" in text:
        text = text.replace("'", '"')

    return text


def validate_recommendation(rec: dict) -> Tuple[bool, list]:
    """Validate a trade recommendation dict has required fields."""
    errors = []

    required = ["symbol", "direction", "conviction"]
    for field in required:
        if field not in rec:
            errors.append(f"Missing required field: {field}")

    if "direction" in rec and rec["direction"] not in ("long", "short", "wait"):
        errors.append(f"Invalid direction: {rec['direction']}")

    if "conviction" in rec:
        try:
            c = int(rec["conviction"])
            if not 0 <= c <= 100:
                errors.append(f"Conviction out of range: {c}")
        except (ValueError, TypeError):
            errors.append(f"Non-numeric conviction: {rec['conviction']}")

    return len(errors) == 0, errors
