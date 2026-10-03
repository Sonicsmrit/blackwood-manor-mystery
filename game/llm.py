"""Return by Death Manor - LLM Integration Layer

Supports multiple AI backends for dynamic dialogue generation:
  1. Gemini (GOOGLE_API_KEY / GEMINI_API_KEY) - Google's Gemini 3.8 Flash
  2. Groq (GROQ_API_KEY) - Fast, free tier available, uses Llama models
  3. Anthropic (ANTHROPIC_API_KEY) - Claude models
  4. Fallback - Static pre-written dialogue from fallback.json

Features:
  - Ingests detailed markdown character trait sheets from characters/<char>.md
  - Applies humanizer dialogue principles for natural, breathing conversational cadence
  - Directs the AI to select an on-screen facial model/expression for each line
  - Generates 4 contextual player choices matching required game mechanics
"""

import os
import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

import ssl

API_TIMEOUT = 3.0

_ssl_context_cache = None

def _strip_emojis(text: str) -> str:
    """Thoroughly strip all emoji characters, icons, and non-standard symbols."""
    if not text or not isinstance(text, str):
        return ""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess, etc.
        "\U0001FA70-\U0001FAFF"  # symbols extended
        "\U00002600-\U000026FF"  # misc symbols (hearts, swords, etc)
        "\U00002300-\U000023FF"  # misc technical
        "\U00002B00-\U00002BFF"  # arrows/stars
        "♥❤🔍⚔↩✦✧★☆✓✗•⚡"
        "]+",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub("", text)
    cleaned = re.sub(r' +', ' ', cleaned).strip()
    return cleaned

def _get_ssl_context():
    """Create an SSL context that works reliably in Ren'Py's embedded Python runtime."""
    global _ssl_context_cache
    if _ssl_context_cache is None:
        ca_certs = [
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/ca-bundle.pem",
            "/etc/ssl/cert.pem"
        ]
        for ca in ca_certs:
            if os.path.exists(ca):
                try:
                    _ssl_context_cache = ssl.create_default_context(cafile=ca)
                    return _ssl_context_cache
                except Exception:
                    pass
        try:
            _ssl_context_cache = ssl._create_unverified_context()
        except Exception:
            _ssl_context_cache = None
    return _ssl_context_cache

# Valid facial models / sprite expressions supported per character
VALID_FACIAL_MODELS = {
    "marika": ["neutral", "calm", "angry", "sly", "sad", "tearful", "shy", "apologetic", "creepy"],
    "elise": ["neutral", "talking", "somber", "angry", "distressed", "bloodied"],
    "vance": ["neutral", "talking", "clinical", "bloodied"],
    "hargrove": ["neutral", "talking", "grave", "bloodied"],
    "odile": ["neutral", "talking", "nervous", "bloodied"]
}

# ─── Key & Mode Management ───────────────────────────────────────────────────

_secrets_cache = None

def _load_secrets() -> Dict[str, str]:
    global _secrets_cache
    if _secrets_cache is None:
        secrets_path = os.path.join(os.path.dirname(__file__), "secrets.json")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    _secrets_cache = json.load(f)
            except Exception:
                _secrets_cache = {}
        else:
            _secrets_cache = {}
    return _secrets_cache

def _get_key(env_name: str) -> Optional[str]:
    """Get API key from environment or secrets.json."""
    key = os.environ.get(env_name)
    if key:
        return key
    return _load_secrets().get(env_name)

def get_mode() -> str:
    """Determine which LLM backend to use."""
    forced = os.environ.get("LLM_MODE")
    if forced in ("live", "groq", "gemini", "anthropic", "fallback"):
        return forced
    if _get_key("GOOGLE_API_KEY") or _get_key("GEMINI_API_KEY"):
        return "gemini"
    if _get_key("GROQ_API_KEY"):
        return "groq"
    if _get_key("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "fallback"

# ─── Character Trait Markdown Loader ──────────────────────────────────────────

_char_md_cache: Dict[str, str] = {}

def _load_character_md(char_id: str) -> str:
    """Load character markdown profile containing traits, humanizer notes, and facial models."""
    global _char_md_cache
    if char_id in _char_md_cache:
        return _char_md_cache[char_id]

    # Search in characters/ directory relative to project root or game dir
    base_dirs = [
        os.path.join(os.path.dirname(__file__), "..", "characters"),
        os.path.join(os.path.dirname(__file__), "characters"),
        os.path.join(os.getcwd(), "characters")
    ]
    for bdir in base_dirs:
        md_file = os.path.join(bdir, f"{char_id}.md")
        if os.path.exists(md_file):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    _char_md_cache[char_id] = content
                    return content
            except Exception:
                pass
    return ""

def _load_adrian_md() -> str:
    """Load Adrian protagonist profile for contextual choice generation."""
    return _load_character_md("adrian")

# ─── Roster Loading ──────────────────────────────────────────────────────────

_roster_cache = None

def _load_roster() -> Dict[str, Any]:
    global _roster_cache
    if _roster_cache is None:
        roster_path = os.path.join(os.path.dirname(__file__), "roster.json")
        with open(roster_path, "r", encoding="utf-8") as f:
            _roster_cache = json.load(f)
    return _roster_cache

# ─── API Callers ──────────────────────────────────────────────────────────────

def _call_gemini(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Google Gemini API using ultra-fast, low-latency models."""
    key = _get_key("GOOGLE_API_KEY") or _get_key("GEMINI_API_KEY")
    if not key:
        return None

    # Ultra-fast models that do not hit 429 rate limits and respond in ~1.2s
    models_to_try = [
        os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest"),
        "gemini-3.5-flash-lite"
    ]

    for model in models_to_try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               + model + ":generateContent?key=" + key)
        headers = {"Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.8,
                "maxOutputTokens": 450
            }
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT, context=_get_ssl_context()) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                candidates = body.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except Exception as e:
            # Try next model immediately without sleeping
            continue
    return None


def _call_groq(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Groq API (OpenAI-compatible)."""
    key = _get_key("GROQ_API_KEY")
    if not key:
        return None

    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.85,
        "max_tokens": 600
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT, context=_get_ssl_context()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
    except Exception as e:
        print("[LLM] Groq call failed: " + str(e))
    return None


def _call_anthropic(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Anthropic Messages API."""
    key = _get_key("ANTHROPIC_API_KEY")
    if not key:
        return None

    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": model,
        "max_tokens": 600,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT, context=_get_ssl_context()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0].get("text")
    except Exception as e:
        print("[LLM] Anthropic call failed: " + str(e))
    return None


def _call_llm_api(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Try the active LLM backend."""
    mode = get_mode()
    result = None
    if mode == "gemini" or mode == "live":
        result = _call_gemini(system_prompt, user_prompt)
        if result:
            return result
    if mode == "groq" or (mode == "live" and not result):
        result = _call_groq(system_prompt, user_prompt)
        if result:
            return result
    if mode == "anthropic" or (mode == "live" and not result):
        result = _call_anthropic(system_prompt, user_prompt)
        if result:
            return result
    return None


# ─── Relationship Web ────────────────────────────────────────────────────────
#
# Previously every character only ever had an opinion about Adrian, which made
# five people in one house feel like five exhibits in separate rooms. These are
# the private opinions they hold about each other, injected into the system
# prompt so they can refer to, resent, protect, and talk around one another.

RELATIONSHIPS = {
    "marika": {
        "elise": "She barred you from the house after dark and calls you a stray. You are frightened of her and you despise her, and under both you half-suspect she is right that you do not belong here.",
        "vance": "A paid stranger with more access to Adrian's bedroom than you have. You resent the uniform and the authority it borrows.",
        "hargrove": "The only one who ever brought you tea at the gate. You are careful not to get him in trouble for it.",
        "odile": "A frightened girl who sees everything and says nothing. You suspect she knows exactly what happens in this house at night.",
    },
    "elise": {
        "marika": "A predatory stranger who appeared two years ago and has been eating this family since. You would have her removed from the valley if you could do it quietly.",
        "vance": "Your hire, your expense, and the only competent adult here. You speak to her as staff and resent needing her.",
        "hargrove": "He has known you since you were born and he is the closest thing to a parent you have left. You would never say so.",
        "odile": "Furniture that listens. Useful, replaceable, and lately she flinches when you enter a room, which irritates you.",
    },
    "vance": {
        "marika": "An unregulated emotional variable at the gate who agitates your patient. Clinically unhelpful.",
        "elise": "The woman signing your cheques. You are professionally deferential and privately certain she is unwell with grief.",
        "hargrove": "An old man working past the point his joints allow. You have quietly noted his hands shake.",
        "odile": "Overworked and underfed. You have told her twice to sleep and she has not.",
    },
    "hargrove": {
        "marika": "A young woman standing in the cold because of a quarrel that is not hers. You have taken her tea more than once and you will not apologise for it.",
        "elise": "You watched her learn to walk in this hall. She is hard now because she is frightened, and you let her be hard.",
        "vance": "Efficient, cold, and necessary. You do not care for how she speaks about the family in the family's own house.",
        "odile": "You trained her. You are protective of her and you have noticed she has been sleeping badly.",
    },
    "odile": {
        "marika": "You pity her, standing out there in the damp. You would never say so where Miss Elise could hear.",
        "elise": "She can dismiss you with one sentence and no references. Every word you say near her is measured against that.",
        "vance": "She is kind to you in a brisk way, which confuses you. You have seen her counting bottles more than once.",
        "hargrove": "He taught you the house. He is the only person here you would call a friend, and you worry about him.",
    },
}


def _relationship_block(char_id: str, present_names: List[str]) -> str:
    """How this character privately regards the others, flagging who is in earshot."""
    web = RELATIONSHIPS.get(char_id, {})
    if not web:
        return ""

    display = {
        "marika": "Marika",
        "elise": "Elise",
        "vance": "Nurse Vance",
        "hargrove": "Hargrove",
        "odile": "Odile",
    }
    present_lower = {str(n).lower() for n in present_names}

    lines = []
    for other, feeling in web.items():
        label = display.get(other, other.capitalize())
        here = label.lower() in present_lower or other in present_lower
        suffix = "  [IN THE ROOM RIGHT NOW]" if here else ""
        lines.append(f"- {label}: {feeling}{suffix}")
    return "\n".join(lines)


# How a trust score should read as behaviour rather than as a number.
TRUST_BEHAVIOUR = {
    0: "You do not trust Adrian with anything that costs you. Answer, but answer around the question. Give him the shape of a truth, never its contents.",
    1: "You are willing to talk but you are watching his face while you do it. Offer small true things. Withhold anything that could be used against you.",
    2: "You have decided he is probably not your enemy. You volunteer things he did not ask for. You let a little bitterness or grief through.",
    3: "You trust him, and that frightens you slightly. You say the thing you have not said out loud to anyone in this house.",
}


def _loop_pressure(loop_no: int, strain: int, deaths: int) -> str:
    """What the others can perceive about a man who has already died tonight.

    They have no memory of the loop. They only see the symptoms -- which is
    exactly what makes Return by Death land.
    """
    if loop_no <= 1 and strain <= 0:
        return (
            "Adrian is newly home, concussed and lost. He asks like a man with no map. "
            "Treat his confusion as genuine, because it is."
        )

    tells = [
        "He is calmer than a frightened amnesiac should be, and it is the wrong kind of calm.",
        "He asks questions in a strange order, as though he already has the answers and is checking them.",
        "He sometimes reacts a half-second before you finish a sentence.",
        "He has started watching the clocks.",
    ]
    observed = " ".join(tells[: min(len(tells), 1 + max(0, strain))])

    crack = ""
    if strain == 1:
        crack = " There is a dark hairline mark on his wrist you have not seen before; he keeps pulling his cuff over it."
    elif strain == 2:
        crack = " Dark fissures run up his forearm past the cuff. He looks like something that has been broken and badly reset."
    elif strain >= 3:
        crack = " He looks barely held together. You can hardly stand to look directly at him."

    return (
        f"IMPORTANT -- ADRIAN'S CONDITION: {observed}{crack} "
        "You have NO memory of any previous night, any previous version of this conversation, or any death. "
        "You cannot name what is wrong with him, and you must never mention loops, repeats, or time. "
        "But you have noticed something is off, and it unsettles you. Let that leak into your tone, "
        "a remark about how he is acting, or a question you ask him -- at most once in this reply, and never as exposition."
    )


# ─── Prompt Building ─────────────────────────────────────────────────────────

def _build_system_prompt(char_id: str, name: str, persona: str, scene: Optional[Dict[str, Any]] = None) -> str:
    """Build the system prompt from the character's dossier, their private
    opinions of everyone else, and what the loop has done to Adrian."""
    char_md = _load_character_md(char_id)
    adrian_md = _load_adrian_md()
    valid_models = VALID_FACIAL_MODELS.get(char_id, ["neutral"])
    valid_models_str = ", ".join(valid_models)

    scene = scene or {}
    present_names = scene.get("present_characters", []) or []
    relationships = _relationship_block(char_id, present_names)
    pressure = _loop_pressure(
        int(scene.get("loop_number", 1) or 1),
        int(scene.get("strain", 0) or 0),
        int(scene.get("deaths", 0) or 0),
    )

    if present_names:
        witnesses = (
            "WHO ELSE CAN HEAR YOU: " + ", ".join(str(n) for n in present_names) + ". "
            "This changes what you are willing to say out loud. Staff do not speak freely in front of "
            "the family; the family does not air itself in front of staff. If something you want to say "
            "is unsafe with them standing there, say the safe version, and let the unsafe one show in how you say it."
        )
    else:
        witnesses = (
            "WHO ELSE CAN HEAR YOU: nobody. You are alone with Adrian. "
            "You are freer than usual, and some part of you knows it."
        )

    base_instructions = f"""You voice {name} in 'Return by Death Manor', a gothic psychological mystery visual novel set in an isolated 1920s mountain estate.

=== CHARACTER DOSSIER & VOICE SPECIFICATION ===
{char_md if char_md else f"Name: {name}\nPersona: {persona}"}

=== PROTAGONIST CONTEXT (ADRIAN) ===
{adrian_md}

=== WHAT YOU PRIVATELY THINK OF THE OTHERS ===
These are your own opinions, not public facts. Never recite them. Let them colour a glance,
a pause, a refusal to answer in front of someone, or one barbed half-sentence.
{relationships}

{witnesses}

=== THE MAN IN FRONT OF YOU ===
{pressure}

=== HUMANIZER & NATURAL SPEECH DIRECTIVES ===
1. SPOKEN WORDS ONLY: Output ONLY spoken words that {name} says aloud with their mouth. NEVER include narration, stage actions, or asterisk descriptions (NO *sighs*, NO *looks down*, NO *whispering*). Convey emotion purely through authentic diction, pauses, and the 'expression' field.
2. HUMAN REALISM: People in trauma do not deliver neat essays. Speak with natural cadence, pauses ('...'), interruptions ('—'), and subtext. Never sound robotic.
3. NO BANNED CLICHES: Never use AI tropes like "Indeed", "Allow me to explain", "As you recall", "I must confess", or sterile exposition.
4. ABSOLUTELY NO EMOJIS OR ICONS ANYWHERE: Do not include ANY emojis or symbols (NO ♥, 🔍, ⚔, ↩, ✦, 😊, etc.) in the dialogue or choices. Pure text only.
5. CONVERSATIONAL TENSION: Maintain the gothic atmosphere, quiet dread, and psychological realism.

=== OUTPUT JSON FORMAT ===
You MUST reply with ONLY a valid JSON object matching this EXACT schema:
{{
  "dialogue": "Spoken line delivered aloud by {name} (1-3 sentences, max 260 chars)",
  "choices": [
    {{"intent": "<spec_intent_1>", "text": "Adrian's response option 1 (max 90 chars)"}},
    {{"intent": "<spec_intent_2>", "text": "Adrian's response option 2 (max 90 chars)"}},
    {{"intent": "<spec_intent_3>", "text": "Adrian's response option 3 (max 90 chars)"}},
    {{"intent": "<spec_intent_4>", "text": "Adrian's response option 4 (max 90 chars)"}}
  ],
  "expression": "one of [{valid_models_str}]"
}}"""
    return base_instructions


def _build_user_prompt(
    intent: str,
    trust: int,
    revealed_facts: list,
    deflected: bool,
    choices_spec: List[str],
    context: Dict[str, Any]
) -> str:
    """Build the user prompt with scene context and conversation history."""
    reveal_texts = []
    if revealed_facts:
        for f in revealed_facts:
            if hasattr(f, "text"):
                reveal_texts.append(f.text)
            elif isinstance(f, str):
                reveal_texts.append(f)

    guarded = []
    if deflected and ":" in intent:
        guarded.append(intent.split(":", 1)[1])

    scene = context.get("scene", {})
    history = context.get("history", [])

    prompt_data = {
        "scene_setting": {
            "time_and_place": f"Day {scene.get('day', 1)} - {scene.get('slot', 'morning')} at {scene.get('location', 'the manor')}",
            "people_present": scene.get("present_characters", []),
            "loop_number": scene.get("loop_number", 1),
            "strain": scene.get("strain", 0),
            "revolver_carried": scene.get("bullet_carried", False)
        },
        "character_secret_and_role": scene.get("secret_truth", "Normal resident of the manor."),
        "player_action": intent,
        "trust_level": trust,
        # Trust is otherwise just an integer the model has to guess at.
        "how_trust_should_sound": TRUST_BEHAVIOUR.get(
            max(0, min(3, int(trust or 0))), TRUST_BEHAVIOUR[0]
        ),
        "already_discussed_with_him": scene.get("discussed_topics", []),
        "conversation_history": history,
        "reveal_now": reveal_texts,
        "guarded": guarded,
        "deflected": deflected,
        "choices_spec": choices_spec,
        "writing_note": (
            "Do not repeat a point you have already made in conversation_history -- "
            "if he asks again, react to the fact that he is asking again. "
            "Adrian's four replies must sound like one frightened, concussed man choosing his words, "
            "not a menu of quest options."
        ),
    }
    return json.dumps(prompt_data, ensure_ascii=False)


# ─── Response Validation ─────────────────────────────────────────────────────

def _validate_and_fix(char: str, response_text: str, choices_spec: List[str]) -> Optional[Dict[str, Any]]:
    """Parse, validate, and fix the LLM response. Returns None on failure."""
    if not response_text:
        return None

    # Parse JSON — try direct, then extract from markdown
    result = None
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                return None

    if not isinstance(result, dict):
        return None

    # Validate required dialogue field (support dialogue and npc_line)
    dialogue = result.get("dialogue") or result.get("npc_line", "")
    if not isinstance(dialogue, str) or not dialogue.strip():
        return None

    # Strip emojis and asterisk stage directions like *sighs*
    dialogue = _strip_emojis(dialogue)
    dialogue = re.sub(r'\*[^*]+\*', '', dialogue).strip()
    if not dialogue:
        return None

    # Truncate if too long
    if len(dialogue) > 280:
        dialogue = dialogue[:277] + "..."

    result["dialogue"] = dialogue
    result["npc_line"] = dialogue

    # Validate and normalize facial model / expression
    valid_models = VALID_FACIAL_MODELS.get(char, ["neutral"])
    expr = result.get("expression") or result.get("mood", "neutral")
    if not expr or expr not in valid_models:
        # Try mood as fallback
        mood = result.get("mood", "neutral")
        if mood in valid_models:
            result["expression"] = mood
        elif char == "elise" and mood in ["angry", "distressed", "somber"]:
            result["expression"] = mood
        elif char == "vance" and mood in ["clinical"]:
            result["expression"] = mood
        elif char == "hargrove" and mood in ["grave"]:
            result["expression"] = mood
        elif char == "odile" and mood in ["nervous"]:
            result["expression"] = mood
        else:
            result["expression"] = valid_models[0]
    else:
        result["expression"] = expr
    result["mood"] = result["expression"]

    # Validate choices
    choices = result.get("choices", [])
    if not isinstance(choices, list):
        choices = []

    # Ensure exactly 4 choices matching the spec intents, stripped of emojis
    fixed_choices = []
    for i, spec_intent in enumerate(choices_spec):
        if i < len(choices) and isinstance(choices[i], dict) and choices[i].get("text"):
            raw_text = str(choices[i]["text"])
            text = _strip_emojis(raw_text)[:110]
            if not text:
                text = _strip_emojis(_fallback_choice_text(spec_intent))
            fixed_choices.append({"intent": spec_intent, "text": text})
        else:
            fallback_text = _strip_emojis(_fallback_choice_text(spec_intent))
            fixed_choices.append({"intent": spec_intent, "text": fallback_text})

    result["choices"] = fixed_choices

    # Check forbidden words
    line_lower = dialogue.lower()
    for forbidden in ["ai", "video game", "loop", "time travel", "reset"]:
        if forbidden in line_lower:
            return None

    if "exit_code" not in result:
        result["exit_code"] = None

    return result


def validate_dialogue_response(
    response: Dict[str, Any],
    choices_spec: List[str],
    reveal_now: list = None,
    slip_keywords: List[str] = None,
    is_innocent: bool = False
) -> Tuple[bool, str]:
    """Validate an LLM dialogue response against the spec 10.4 rules.

    Returns (valid, reason); reason is empty when valid.
    """
    if not isinstance(response, dict):
        return False, "response is not a dict"

    dialogue = response.get("dialogue") or response.get("npc_line", "")
    if not isinstance(dialogue, str) or not dialogue.strip():
        return False, "dialogue missing or empty"
    if len(dialogue) > 280:
        return False, "dialogue exceeds 280 characters"

    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != len(choices_spec):
        return False, "choices must have one entry per choices_spec item"
    for i, choice in enumerate(choices):
        if not isinstance(choice, dict) or not choice.get("text"):
            return False, "choice %d missing text" % i
        if len(str(choice["text"])) > 110:
            return False, "choice %d text exceeds 110 characters" % i
        if choice.get("intent") != choices_spec[i]:
            return False, "choice %d intent does not match choices_spec" % i

    line_lower = dialogue.lower()
    for forbidden in ["ai", "video game", "loop", "time travel", "reset"]:
        if re.search(r"\b" + re.escape(forbidden) + r"\b", line_lower):
            return False, "dialogue contains forbidden word: " + forbidden

    # Spec 10.4 rule 6: innocents must never utter a slip keyword.
    if is_innocent and slip_keywords:
        for keyword in slip_keywords:
            if str(keyword).lower() in line_lower:
                return False, "innocent line contains slip keyword: " + keyword

    # Spec 10.4 rule 4: revealed facts must actually appear in the line.
    if reveal_now:
        for fact in reveal_now:
            tokens = getattr(fact, "must_include", None)
            if tokens is None:
                tokens = [fact] if isinstance(fact, str) else []
            for token in tokens:
                if str(token).lower() not in line_lower:
                    return False, "reveal_now token missing from line: " + str(token)

    return True, ""


def _fallback_choice_text(intent: str) -> str:
    """Generate a generic choice text for a given intent."""
    if intent.startswith("probe:"):
        topic = intent.split(":", 1)[1]
        topics_map = {
            "routine": "Where do you usually spend your time?",
            "house": "What can you tell me about this place?",
            "adrian": "What do you know about me... before?",
            "crash": "What happened in the crash?"
        }
        return topics_map.get(topic, "Tell me more about " + topic + ".")
    intent_map = {
        "comfort": "I appreciate you being here.",
        "press": "Stop dodging. Tell me the truth.",
        "small_talk": "How are you holding up?",
        "leave": "I should go. Thank you."
    }
    return intent_map.get(intent, intent.replace("_", " ").capitalize())


# ─── Main Dialogue Generation ────────────────────────────────────────────────

def generate_dialogue(
    char: str,
    intent: str,
    trust: int,
    revealed_facts: list,
    deflected: bool,
    choices_spec: List[str],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate dialogue using LLM if available, otherwise fall back to static content.
    Returns:
        Dict with "npc_line", "expression", "mood", "choices", "exit_code"
    """
    if context is None:
        context = {}

    mode = get_mode()

    if mode != "fallback":
        try:
            result = _generate_dialogue_llm(
                char, intent, trust, revealed_facts,
                deflected, choices_spec, context
            )
            if result is not None:
                print(f"[LLM] Dynamic dialogue generated via {mode} (expression: {result.get('expression')})")
                return result
        except Exception as e:
            print("[LLM] Dialogue generation failed, using fallback: " + str(e))

    return generate_dialogue_fallback(
        char, intent, trust, revealed_facts,
        deflected, choices_spec
    )


def _generate_dialogue_llm(
    char: str,
    intent: str,
    trust: int,
    revealed_facts: list,
    deflected: bool,
    choices_spec: List[str],
    context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Generate dialogue via LLM API call."""
    roster = _load_roster()
    char_info = roster.get(char, {})
    name = char_info.get("name", char.capitalize())
    persona = char_info.get("persona", name + ". A resident of the manor.")

    system_prompt = _build_system_prompt(char, name, persona, (context or {}).get("scene", {}))
    user_prompt = _build_user_prompt(
        intent, trust, revealed_facts, deflected, choices_spec, context
    )

    response_text = _call_llm_api(system_prompt, user_prompt)

    is_innocent = context.get("is_innocent", False)
    slip_keywords = context.get("slip_keywords") or []
    # Rule 4 applies only when the exclusive slip itself is being revealed.
    slip_must_appear = bool(
        revealed_facts and not is_innocent
        and any(getattr(f, "exclusive", False) for f in revealed_facts)
    )

    attempts = 2 if (response_text is not None and slip_must_appear) else 1
    reason = ""
    for attempt in range(attempts):
        if response_text is None:
            return None
        validated = _validate_and_fix(char, response_text, choices_spec)
        if validated is None:
            return None

        # Fail safe: an innocent must never be heard uttering a slip keyword (rule 6).
        valid, reason = validate_dialogue_response(
            validated, choices_spec,
            reveal_now=[],
            slip_keywords=slip_keywords if is_innocent else None,
            is_innocent=is_innocent
        )

        # Rule 4: the killer's slip must casually feature the agenda keyword.
        if valid and slip_must_appear:
            line_lower = (validated.get("npc_line") or "").lower()
            if not any(k.lower() in line_lower for k in slip_keywords):
                valid, reason = False, "slip keyword missing from slip line"

        if valid:
            return validated

        print("[LLM] Rejected dialogue (" + reason + "); attempt " + str(attempt + 1) + ".")
        if attempt + 1 < attempts:
            response_text = _call_llm_api(system_prompt, user_prompt)

    print("[LLM] Using authored fallback after validation failure.")
    return None


# ─── Fallback Data ────────────────────────────────────────────────────────────

def get_fallback_data() -> Dict[str, Any]:
    fb_path = os.path.join(os.path.dirname(__file__), "fallback.json")
    with open(fb_path, "r", encoding="utf-8") as f:
        return json.load(f)


CHARACTER_SPOKEN_DIALOGUE = {
    "marika": {
        "greeting": "Adrian... you came looking for me? Please, don't leave me alone out here. The wind cuts right through my coat...",
        "comfort": "You... you're still so gentle with me. Even with your memories scattered into pieces, your eyes look at me the exact same way.",
        "press": "Why are you looking at me like that?! Look at my hands, Adrian—I'm shaking! I spent two years loving you, and you stare at me like I'm a killer...",
        "deflected": "Please, don't... my chest aches just thinking about that night. Can't we just hold onto right now?",
        "default": "I'm right here beside you, Adrian. Whatever you need to ask, I'm listening.",
        "crash": "The rain was deafening on the gorge road... I screamed at your father to pull the handbrake, but the pedal just gave way. Everything spun into black water.",
        "routine": "Elise locks the heavy oak doors the second twilight touches the pines. I sleep in the cold stone gatehouse until dawn, watching your window.",
        "house": "This house is a mausoleum, Adrian. The portraits glare at us, and the walls seem to remember every cruel thing ever said here. I want us to leave.",
        "adrian": "Before the wreck... you used to sneak warm pastries from the pantry just to make me smile. You swore we'd buy a cottage by the coast."
    },
    "elise": {
        "greeting": "Out of bed again, Adrian? You sway on your feet like a ghost. The draft along this wainscoting will inflame your concussion.",
        "comfort": "Spare me your pity, brother. I do not have the luxury of collapsing. Someone has to hold what remains of our family together.",
        "press": "Lower your voice this instant. You may have left your dignity at the bottom of the gorge, but under our father's roof, you will show restraint.",
        "deflected": "Father's ledgers and bank accounts are my burden, not yours. Go lie down before Vance catches you wandering.",
        "default": "Speak your mind, Adrian. I have forty probate documents to balance before sunset and little patience to waste.",
        "crash": "The county constables called it hydraulic failure on wet shale. But father drove that mountain pass for thirty years without scratching a fender.",
        "routine": "I spend mornings in father's private quarters, afternoons dissecting the estate debts in the study, and evenings keeping vigil upstairs.",
        "house": "Three generations of Blackwood blood built these walls. Creditors and stray village girls think they can tear it apart—they are mistaken.",
        "adrian": "You were always the headstrong one, brother... shouting at father over the inheritance trusts the very morning of the accident."
    },
    "vance": {
        "greeting": "Adrian. Wandering again. Let me feel your wrist... your pulse is thready. Have you taken the blue sedative capsules?",
        "comfort": "Sentimentality does not knit fractured temporal bones, Adrian. Still... in seven years of triage nursing, rarely does a head-trauma patient show courtesy.",
        "press": "Raise your voice all you please; neurological reflexes and blood pressure don't deceive. Sit down before your equilibrium fails entirely.",
        "deflected": "Gossip concerning the late master falls well outside my clinical remit. Consult your sister for domestic disputes.",
        "default": "I am monitoring your hematoma recovery, Adrian. Make your inquiry concise.",
        "crash": "Cranial trauma of your severity typically induces complete retrograde amnesia. You are clinically fortunate to be walking at all.",
        "routine": "I conduct patient rounds upstairs morning and afternoon, and prepare clinical solutions in the kitchen after supper.",
        "house": "This estate is damp, unheated, and criminally isolated. From a sanitary perspective, it is thoroughly unfit for convalescence.",
        "adrian": "Prior to the collision, your medical dossier noted vigorous health. Now your motor coordination is dangerously unstable."
    },
    "hargrove": {
        "greeting": "Young master Adrian... Ah, forgive an old man's tears, but seeing you on your feet warms an old heart. May I fetch warm broth from the stove?",
        "comfort": "Your kindness echoes your late mother's grace, sir. In forty years serving this estate, she alone treated the servants as kin.",
        "press": "I carried you upon my shoulders when you were a lad of six, young master. I will not have my loyalty questioned in this sacred hall.",
        "deflected": "Pardon me, sir, but some confidences between the master and his ledger are best left buried in the churchyard.",
        "default": "I remain devoted to your service, young master Adrian. What may I attend to?",
        "crash": "A black nightmare, young master... The carriage road beneath the limestone crags has taken three carriages in my lifetime. An unforgiving descent.",
        "routine": "Mornings I tend the kitchen hearths and pantry stores; afternoons I polish the family silver and oversee the parlor fireplace.",
        "house": "I know every sigh in these floorboards, sir. Forty years of family triumphs, and now... so many empty bedrooms echoing in the dark.",
        "adrian": "I remember you reading by the study hearth until three in the morning, young master... always chasing truth in old legal texts."
    },
    "odile": {
        "greeting": "M-master Adrian! Oh! Forgive me, sir, I was only wiping the banister... D-did you ring for tea, or fresh lavender linens?",
        "comfort": "You... you're truly kind to say so, sir. Miss Elise usually scolds me if the teacup clatters... You've always been the gentle one.",
        "press": "Please, sir, don't raise your voice! I don't know anything about the master's wills or papers, I swear on my mother's grave!",
        "deflected": "I... I daren't speak, sir! If Miss Elise catches me gossiping about family secrets, she'll cast me out into the snow without references!",
        "default": "I'm right here, master Adrian... Is there anything you'd have me fetch?",
        "crash": "The night of the storm... I heard shouting in the courtyard before the car left. Terrible, angry words that made the horses shiver.",
        "routine": "I sweep the parlor and vestibule in the morning, wash the heavy bed-linens in the basement kitchen in the afternoon, and stoke fires at dusk.",
        "house": "The chimney flues carry whispers at night, sir... You can hear muffled voices traveling down from the upstairs corridors into the pantry.",
        "adrian": "You were the only soul in this house who ever thanked me when I stoked your bedroom hearth, master Adrian. I never forgot that."
    }
}


def generate_dialogue_fallback(
    char: str,
    intent: str,
    trust: int,
    revealed_facts: list,
    deflected: bool,
    choices_spec: List[str]
) -> Dict[str, Any]:
    """Generate fallback dialogue when LLM is unavailable or invalid - always first-person spoken speech."""
    fb = get_fallback_data()
    valid_models = VALID_FACIAL_MODELS.get(char, ["neutral"])
    char_speech = CHARACTER_SPOKEN_DIALOGUE.get(char, {})

    expression = "neutral"
    if intent == "greeting":
        npc_line = char_speech.get("greeting", "Adrian... you're here.")
        mood = "neutral"
        expression = "neutral"
    elif deflected:
        npc_line = char_speech.get("deflected", "I'd rather not speak of that right now.")
        mood = "apologetic"
        expression = "apologetic" if "apologetic" in valid_models else ("nervous" if "nervous" in valid_models else "neutral")
    elif revealed_facts:
        fact = revealed_facts[0]
        fid = getattr(fact, "id", str(fact))
        if ":routine" in fid:
            routine_lines = fb.get("routine_claim_lines", {})
            npc_line = routine_lines.get(char, char_speech.get("routine", "I wait by the gate in the morning and evening."))
        elif ":house" in fid:
            house_dict = fb.get("house_lines", {})
            lines = house_dict.get(char, [char_speech.get("house", "This house holds too many secrets.")])
            npc_line = lines[0] if isinstance(lines, list) else str(lines)
        elif ":adrian" in fid:
            adrian_dict = fb.get("adrian_lines", {})
            lines = adrian_dict.get(char, [char_speech.get("adrian", "Before the accident, things were different.")])
            npc_line = lines[0] if isinstance(lines, list) else str(lines)
        elif "slip" in fid or "crash" in fid:
            crash_slips = fb.get("crash_slip_lines", {})
            found_line = None
            for cause, chars in crash_slips.items():
                if isinstance(chars, dict) and char in chars:
                    found_line = chars[char]
                    break
            npc_line = found_line or char_speech.get("crash", "The crash on the mountain pass was no accident.")
        else:
            topic = getattr(fact, "topic", "default")
            npc_line = char_speech.get(topic, char_speech.get("default", "I'm telling you what I know."))

        exclusive = getattr(fact, "exclusive", False)
        mood = "sly" if exclusive else "neutral"
        expression = "sly" if exclusive and "sly" in valid_models else ("talking" if "talking" in valid_models else "neutral")
    elif intent.startswith("probe:"):
        topic = intent.split(":", 1)[1]
        npc_line = char_speech.get(topic, char_speech.get("default", "What do you wish to know?"))
        mood = "neutral"
        expression = "talking" if "talking" in valid_models else "neutral"
    elif intent == "comfort":
        npc_line = char_speech.get("comfort", "Thank you, Adrian... that means more than you know.")
        mood = "calm"
        expression = "calm" if "calm" in valid_models else ("talking" if "talking" in valid_models else "neutral")
    elif intent == "press":
        npc_line = char_speech.get("press", "Stop pressing me! I have told you all that I know!")
        mood = "angry"
        expression = "angry" if "angry" in valid_models else ("clinical" if "clinical" in valid_models else ("grave" if "grave" in valid_models else "neutral"))
    else:
        npc_line = char_speech.get("default", "I'm listening, Adrian.")
        mood = "neutral"
        expression = "neutral"

    # 2. Determine 4 choice texts stripped of any emojis
    choices = []
    for spec in choices_spec:
        variants = fb.get("choices", {}).get(spec, [_fallback_choice_text(spec)])
        raw_text = variants[hash(spec + char) % len(variants)]
        text = _strip_emojis(raw_text)
        choices.append({"intent": spec, "text": text})

    clean_line = _strip_emojis(npc_line)

    return {
        "dialogue": clean_line,
        "npc_line": clean_line,
        "expression": expression,
        "mood": mood,
        "choices": choices,
        "exit_code": None
    }
