"""Return by Death Manor - LLM Integration Layer"""

import os
import json
import hashlib
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

LLM_MODE = "fallback"  # "live" | "cached" | "fallback"
MODEL = os.environ.get("GAME_MODEL", "claude-haiku-4-5-20251001")
API_TIMEOUT = 12

def get_api_key() -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        secrets_path = os.path.join(os.path.dirname(__file__), "secrets.json")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    key = json.load(f).get("ANTHROPIC_API_KEY")
            except Exception:
                pass
    return key

def get_mode() -> str:
    global LLM_MODE
    forced = os.environ.get("LLM_MODE")
    if forced in ("live", "cached", "fallback"):
        return forced
    if get_api_key():
        return "live"
    return "fallback"

def _cache_path(prompt_hash: str) -> str:
    cache_dir = os.path.join(os.path.dirname(__file__), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{prompt_hash}.json")

def _call_api_raw(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Anthropic Messages API using urllib.request."""
    api_key = get_api_key()
    if not api_key:
        return None
        
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0].get("text")
    except Exception as e:
        print(f"[LLM] API call failed: {e}")
    return None

def validate_dialogue_response(
    response: Any,
    choices_spec: List[str],
    reveal_now: List[str],
    slip_keywords: List[str],
    is_innocent: bool
) -> Tuple[bool, str]:
    """
    Validate LLM dialogue output according to Section 10.4 of spec.
    Returns (is_valid, failure_reason).
    """
    if not isinstance(response, dict):
        return False, "Response must be a JSON object"
        
    for req_key in ["npc_line", "mood", "choices"]:
        if req_key not in response:
            return False, f"Missing required key: {req_key}"
            
    npc_line = response.get("npc_line", "")
    if not isinstance(npc_line, str) or len(npc_line) > 280:
        return False, "npc_line must be a string <= 280 characters"
        
    choices = response.get("choices", [])
    if not isinstance(choices, list) or len(choices) != 4:
        return False, "choices must be a list of exactly 4 items"
        
    for i, ch in enumerate(choices):
        if not isinstance(ch, dict) or "text" not in ch:
            return False, f"Choice {i} missing text"
        if len(ch.get("text", "")) > 110:
            return False, f"Choice {i} exceeds 110 characters"
        # Overwrite intent with spec
        ch["intent"] = choices_spec[i]

    # Check forbidden words
    line_lower = npc_line.lower()
    for forbidden in ["ai", "video game", "loop", "time travel", "reset"]:
        if forbidden in line_lower:
            return False, f"Forbidden word found: {forbidden}"
            
    # Innocents must never use slip keywords or accuse
    if is_innocent:
        for kw in slip_keywords:
            if kw.lower() in line_lower:
                return False, f"Innocent used forbidden slip keyword: {kw}"
        for bad in ["killer", "murderer"]:
            if bad in line_lower:
                return False, f"Innocent used forbidden accusation: {bad}"

    # If reveal_now is present and contains a slip, must contain at least one slip keyword
    if reveal_now and not is_innocent and slip_keywords:
        has_kw = any(kw.lower() in line_lower for kw in slip_keywords)
        if not has_kw:
            return False, f"Killer reveal line missing required slip keyword from {slip_keywords}"

    return True, "Valid"

def get_fallback_data() -> Dict[str, Any]:
    fb_path = os.path.join(os.path.dirname(__file__), "fallback.json")
    with open(fb_path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_dialogue_fallback(
    char: str,
    intent: str,
    trust: int,
    revealed_facts: list,
    deflected: bool,
    choices_spec: List[str]
) -> Dict[str, Any]:
    """Generate fallback dialogue when LLM is unavailable or invalid."""
    fb = get_fallback_data()
    
    # 1. Determine NPC line
    if deflected:
        lines = fb.get("deflections", {}).get(char, ["I'd rather not speak of that right now."])
        npc_line = lines[hash(intent) % len(lines)]
        mood = "apologetic"
    elif revealed_facts:
        fact = revealed_facts[0]
        npc_line = fact.text
        mood = "sly" if fact.exclusive else "neutral"
    elif intent.startswith("probe:"):
        topic = intent.split(":", 1)[1]
        lines_dict = fb.get(f"{topic}_lines", {}).get(char)
        if lines_dict and isinstance(lines_dict, list):
            npc_line = lines_dict[hash(char + topic) % len(lines_dict)]
        else:
            npc_line = f"{char.capitalize()} speaks quietly, offering little new information."
        mood = "neutral"
    elif intent == "comfort":
        npc_line = f"{char.capitalize()} softens slightly, offering a faint nod of reassurance."
        mood = "calm"
    elif intent == "press":
        npc_line = f"{char.capitalize()} stiffens, defensive under your pointed questioning."
        mood = "angry"
    else:
        npc_line = f"{char.capitalize()} looks out into the hallway, waiting for you to speak."
        mood = "neutral"

    # 2. Determine 4 choice texts
    choices = []
    for spec in choices_spec:
        variants = fb.get("choices", {}).get(spec, [f"[{spec}]"])
        text = variants[hash(spec + char) % len(variants)]
        choices.append({"intent": spec, "text": text})

    return {
        "npc_line": npc_line,
        "mood": mood,
        "choices": choices,
        "exit_code": None
    }
