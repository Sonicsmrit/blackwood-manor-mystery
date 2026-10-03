"""Return by Death Manor - Deterministic Run Generator"""

import random
from typing import Optional, Dict, List
from .constants import CHARACTERS, AGENDAS, DECOY_SECRETS, BASE_LOCATIONS, SLOTS, LOCATIONS
from .state import RunState
from .facts import build_all_facts
from .validator import validate_run

ROUTINE_CLAIMS = {
    "marika": {"morning": "gate", "afternoon": "parlor", "evening": "gate"},
    "elise": {"morning": "upstairs", "afternoon": "study", "evening": "upstairs"},
    "vance": {"morning": "upstairs", "afternoon": "upstairs", "evening": "kitchen"},
    "hargrove": {"morning": "kitchen", "afternoon": "parlor", "evening": "kitchen"},
    "odile": {"morning": "parlor", "afternoon": "kitchen", "evening": "parlor"}
}

DECOY_DEVIATION_SLOT_AND_LOC = {
    "lingering": ("evening", "parlor"),
    "unsent_letters": ("afternoon", "study"),
    "night_visits": ("evening", "parlor"),
    "diary": ("afternoon", "upstairs"),
    "phone_calls": ("evening", "upstairs"),
    "skimming_pills": ("morning", "kitchen"),
    "pawned_watch": ("afternoon", "gate"),
    "drinking": ("evening", "study"),
    "stolen_silver": ("afternoon", "parlor"),
    "eavesdropping": ("evening", "upstairs")
}

HOOKS = [
    "Something about this house is wrong, and it already knows you.",
    "A single bullet rests in your coat; the clock resets when you bleed.",
    "The faces here remember you, but their smiles hide a sharpened blade.",
    "The fog refuses to lift until the blood debt of the crash is settled."
]

def generate_run(seed: int, previous_killer: Optional[str] = None) -> RunState:
    """
    Generate a full solvable and fair RunState from a numeric seed.
    Guarantees validation passes according to rules V1-V8.
    """
    for attempt in range(25):
        rng = random.Random(seed + attempt * 1000)
        
        # 1. Pick Killer (different from previous)
        possible_killers = [c for c in CHARACTERS if c != previous_killer]
        killer = rng.choice(possible_killers)
        
        # 2. Pick Agenda
        agenda = rng.choice(list(AGENDAS.keys()))
        cause = AGENDAS[agenda]["cause"]
        
        # 3. Pick Decoy Secret for each innocent
        secrets: Dict[str, str] = {}
        for char in CHARACTERS:
            if char != killer:
                secrets[char] = rng.choice(DECOY_SECRETS[char])
        
        # 4. Start trust
        start_trust = {
            "marika": 0,
            "elise": 0,
            "vance": 1,
            "hargrove": 2,
            "odile": 1
        }
        
        # 5. Build Positions
        positions: Dict[str, Dict[str, Dict[str, str]]] = {}
        
        # Day 1: Exactly routine claims for everyone
        for char in CHARACTERS:
            positions[char] = {
                "1": dict(ROUTINE_CLAIMS[char]),
                "2": dict(ROUTINE_CLAIMS[char])
            }
        
        # Day 2 Innocents: Deviate according to decoy secret
        for inc, secret in secrets.items():
            dev_slot, dev_loc = DECOY_DEVIATION_SLOT_AND_LOC[secret]
            positions[inc]["2"][dev_slot] = dev_loc
            
        # Day 2 Killer: Deviate at exactly 1 slot to an alternate location
        # Choose a deviation slot and alternate location
        killer_routine = ROUTINE_CLAIMS[killer]
        dev_slot = rng.choice(SLOTS)
        current_claimed = killer_routine[dev_slot]
        
        # Select an alternate location that is not current claimed and not base if possible
        possible_locs = [loc for loc in LOCATIONS if loc != current_claimed]
        dev_loc = rng.choice(possible_locs)
        positions[killer]["2"][dev_slot] = dev_loc
        
        # 6. Fragment order
        frag_order = ["smell", "sound", "sight"]
        rng.shuffle(frag_order)
        
        # 7. Hook
        hook = rng.choice(HOOKS)
        
        # Construct temporary state
        run_state = RunState(
            seed=seed,
            killer=killer,
            agenda=agenda,
            cause=cause,
            secrets=secrets,
            start_trust=start_trust,
            positions=positions,
            facts=[],
            fragment_order=frag_order,
            hook=hook
        )
        
        # Derive all facts
        run_state.facts = build_all_facts(run_state)
        
        # Validate
        errors = validate_run(run_state)
        if not errors:
            return run_state
            
    # If 25 attempts failed (should never happen), raise with errors
    raise RuntimeError(f"Failed to generate valid run for seed {seed}: {errors}")
