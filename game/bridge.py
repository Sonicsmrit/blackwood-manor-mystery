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
