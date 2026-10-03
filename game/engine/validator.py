"""Return by Death Manor - Fairness Validator"""

import json
import os
from typing import List, Dict, Any
from .constants import CHARACTERS, AGENDAS, DECOY_SECRETS, DEATH_FRAGMENTS, BASE_LOCATIONS, SLOTS

def validate_run(run_state) -> List[str]:
    """
    Validate run state fairness according to section 11.2 of the spec.
    Returns list of error strings; empty list means valid.
    """
    errors: List[str] = []
    
    killer = run_state.killer
    agenda = run_state.agenda
    cause = run_state.cause
    secrets = run_state.secrets
    positions = run_state.positions
    facts = run_state.facts

    # V1: exactly one killer, drawn from the roster
    if killer not in CHARACTERS:
        errors.append(f"V1: killer {killer} not in roster")
    
    # V2: killer has slip (exclusive), presence conflict, finding (exclusive)
    slip_facts = [f for f in facts if f.kind == "claim" and f.char == killer and f.topic == "crash" and f.exclusive]
    if len(slip_facts) != 1:
        errors.append(f"V2: killer must have exactly 1 exclusive slip fact, found {len(slip_facts)}")
    
    killer_finding = [f for f in facts if f.kind == "finding" and f.char == killer and f.exclusive]
    if len(killer_finding) != 1:
        errors.append(f"V2: killer must have exactly 1 exclusive finding, found {len(killer_finding)}")

    # Check killer presence deviation on Day 2
    killer_deviations = 0
    routine_claims = {
        "marika": {"morning": "gate", "afternoon": "parlor", "evening": "gate"},
        "elise": {"morning": "upstairs", "afternoon": "study", "evening": "upstairs"},
        "vance": {"morning": "upstairs", "afternoon": "upstairs", "evening": "kitchen"},
        "hargrove": {"morning": "kitchen", "afternoon": "parlor", "evening": "kitchen"},
        "odile": {"morning": "parlor", "afternoon": "kitchen", "evening": "parlor"}
    }
    
    for slot in SLOTS:
        claimed_loc = routine_claims[killer][slot]
        actual_loc = positions[killer]["2"][slot]
        if actual_loc != claimed_loc:
            killer_deviations += 1
    if killer_deviations != 1:
        errors.append(f"V2: killer must deviate at exactly 1 Day 2 slot, found {killer_deviations}")

    # V3: every innocent has exactly one decoy secret, producing a deviation and a finding
    innocents = [c for c in CHARACTERS if c != killer]
    for inc in innocents:
        if inc not in secrets:
            errors.append(f"V3: innocent {inc} missing secret")
        elif secrets[inc] not in DECOY_SECRETS[inc]:
            errors.append(f"V3: innocent {inc} secret {secrets[inc]} invalid")

        # Innocent finding
        inc_finding = [f for f in facts if f.kind == "finding" and f.char == inc]
        if len(inc_finding) != 1:
            errors.append(f"V3: innocent {inc} must have exactly 1 finding, found {len(inc_finding)}")
        
        # Innocent deviation on Day 2
        inc_deviations = 0
        for slot in SLOTS:
            if positions[inc]["2"][slot] != routine_claims[inc][slot]:
                inc_deviations += 1
        if inc_deviations != 1:
            errors.append(f"V3: innocent {inc} must deviate at exactly 1 Day 2 slot, found {inc_deviations}")

    # V4: no innocent holds an exclusive fact. No innocent states a specific cause
    for f in facts:
        if f.char in innocents and f.exclusive:
            errors.append(f"V4: innocent {f.char} holds exclusive fact {f.id}")

    # V5: every fact's gate is reachable
    # For talk: character is at that location
    # For search: owner must be absent at least one slot at their base location
    for inc in CHARACTERS:
        base_loc = BASE_LOCATIONS[inc]
        # Check if there is at least one slot on Day 1 or Day 2 where inc is NOT at base_loc
        absent_slots_d1 = [s for s in SLOTS if positions[inc]["1"][s] != base_loc]
        absent_slots_d2 = [s for s in SLOTS if positions[inc]["2"][s] != base_loc]
        if not absent_slots_d1 and not absent_slots_d2:
            errors.append(f"V5: {inc} is never absent from base location {base_loc}, blocking search")

    # V7: fragments are assigned one per category with group-sharing rule
    if len(run_state.fragment_order) != 3 or set(run_state.fragment_order) != {"smell", "sound", "sight"}:
        errors.append(f"V7: invalid fragment order {run_state.fragment_order}")
    for cat in ["sound", "smell", "sight"]:
        cat_frags = [f for f in facts if f.kind == "fragment" and f.id.startswith(f"fragment:{cat}:")]
        if len(cat_frags) != 1:
            errors.append(f"V7: expected 1 fragment for {cat}, found {len(cat_frags)}")

    # V8: every slip_keywords check passes against authored fallback lines
    fallback_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fallback.json")
    if os.path.exists(fallback_path):
        with open(fallback_path, "r", encoding="utf-8") as f:
            fb = json.load(f)
        slip_texts = fb.get("crash_slip", {}).get(cause, {})
        killer_slip_text = slip_texts.get(killer, "").lower()
        keywords = AGENDAS[agenda]["slip_keywords"]
        matches = any(kw.lower() in killer_slip_text for kw in keywords)
        if not matches:
            errors.append(f"V8: fallback slip line for {killer} under {cause} does not contain keywords {keywords}")
        
        # Check innocents do NOT contain slip keywords
        for inc in innocents:
            vague_text = fb.get("crash_vague", {}).get(inc, "").lower()
            for all_kw in ["brake", "drugged", "sedative", "ran them off"]:
                if all_kw in vague_text:
                    errors.append(f"V8: innocent {inc} vague text contains forbidden slip keyword '{all_kw}'")

    return errors
