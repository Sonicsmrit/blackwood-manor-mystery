"""Return by Death Manor - Ren'Py Bridge Layer"""

import sys
import os
import json
import threading
from typing import Optional, Dict, Any, Callable

try:
    import renpy
    IN_RENPY = True
except ImportError:
    IN_RENPY = False

def run_in_thread_with_timeout(func: Callable, args=(), kwargs=None, timeout: float = 12.0) -> Any:
    """
    Execute a function in a background thread with a strict timeout.
    Returns the result, or None if timed out.
    """
    if kwargs is None:
        kwargs = {}
        
    result_box = {"result": None, "done": False, "error": None}
    
    def worker():
        try:
            result_box["result"] = func(*args, **kwargs)
        except Exception as e:
            result_box["error"] = e
        finally:
            result_box["done"] = True

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    
    if result_box["done"] and result_box["error"] is None:
        return result_box["result"]
    return None

def get_character_display_name(char_id: str) -> str:
    names = {
        "marika": "Marika",
        "elise": "Elise",
        "vance": "Nurse Vance",
        "hargrove": "Hargrove",
        "odile": "Odile",
        "adrian": "Adrian"
    }
    return names.get(char_id, char_id.capitalize())

def get_location_display_name(loc_id: str) -> str:
    names = {
        "parlor": "The Parlor",
        "study": "The Study",
        "kitchen": "The Kitchen",
        "upstairs": "Upstairs Hallway",
        "gate": "The Manor Gate"
    }
    return names.get(loc_id, loc_id.capitalize())


# ─── Presence facts ──────────────────────────────────────────────────────────
#
# Presence records are stored in known_facts as bare ID strings. build_all_facts
# emits only world/claim/finding/fragment, so there is no Fact object behind them
# and therefore no .text -- which is why an observed absence used to be recorded
# and then displayed nowhere.
#
# That mattered: the notebook painted a red "CONTRADICTS THEMSELF" badge off the
# back of these records while the evidence itself stayed invisible. The badge is
# gone (see custom_screens.rpy); these helpers put the actual observation on the
# Timeline tab instead, in words, and leave the reading to the player.
#
# Absence IDs are written by script.rpy as:
#   presence:absence:{char}:{claimed_loc}:{slot}:{day}

def parse_presence_fact(fact_id: str):
    """Split a presence fact ID into its parts.

    Returns (kind, char_id, loc_id, slot, day) or None if the ID is not one we
    can render. `kind` is "absence" or "seen".
    """
    if not isinstance(fact_id, str):
        return None
    parts = fact_id.split(":")
    if len(parts) != 6 or parts[0] != "presence":
        return None
    if parts[1] not in ("absence", "seen"):
        return None
    try:
        day = int(parts[5])
    except (TypeError, ValueError):
        return None
    return parts[1], parts[2], parts[3], parts[4], day


def presence_absence_text(char_id: str, loc_id: str, slot: str, day: int) -> str:
    """An observed absence, phrased as what Adrian walked into.

    Names the person and the room and nothing else. It deliberately does not
    assert that they lied: every character deviates from their routine once,
    killer or not, so a single empty room is not evidence of anything on its own.
    The claim they are being measured against is on their card in the People tab.
    """
    who = get_character_display_name(char_id)
    where = get_location_display_name(loc_id)
    return f"{where} was empty. {who} said {('she' if char_id in ('marika', 'elise', 'odile') else 'he')} would be there."


def presence_absence_text_for(fact_id: str):
    """Same as presence_absence_text, keyed by fact ID. None if unparseable."""
    parsed = parse_presence_fact(fact_id)
    if not parsed or parsed[0] != "absence":
        return None
    return presence_absence_text(parsed[1], parsed[2], parsed[3], parsed[4])


def evidence_label(kind: str) -> str:
    """A neutral heading for an Evidence card.

    Replaces the raw Fact.id that used to head these cards. An id like
    `finding:elise:obsession` names the character outright, and the killer's
    text_key is the literal string `finding.killer.obsession`, so neither field
    is safe to render -- not even in a "subtle" colour. Keying off `kind` alone
    describes what the object *is* without grading it.
    """
    return {
        "world": "A document",
        "finding": "Something left behind",
    }.get(kind, "Something you noted")
