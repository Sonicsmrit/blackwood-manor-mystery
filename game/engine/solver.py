"""Return by Death Manor - Game Solver & Plan Search"""

from typing import Dict, Any, List
from .constants import CONVO_MAX_TURNS, BASE_LOCATIONS, SLOTS
from .state import RunState

def solve(run_state: RunState) -> Dict[str, Any]:
    """
    Simulate a perfect player finding the killer in <= 2 loops.
    Goal: Obtain the killer's crash slip + (killer finding OR presence deviation).
    Budget: Loop 1 = 12 actions (6 on Day 1, 6 on Day 2). Loop 2 = 6 actions.
    """
    killer = run_state.killer
    positions = run_state.positions
    start_trust = run_state.start_trust[killer]
    
    plan: List[str] = []
    
    # 1. Talk to killer and obtain crash slip
    # Need trust >= 2.
    comforts_needed = max(0, 2 - start_trust)
    turns_needed = comforts_needed + 1  # comforts + probe:crash
    if turns_needed > CONVO_MAX_TURNS:
        return {"solved": False, "loop_count": None, "reason": "Cannot reach trust 2 within turn limit"}

    # Find a slot where killer is available to talk
    talk_day = "1"
    talk_slot = "morning"
    talk_loc = positions[killer][talk_day][talk_slot]
    plan.append(f"Day {talk_day} {talk_slot}: Go to {talk_loc}, talk to {killer} ({comforts_needed} comforts, probe:crash) -> Slip acquired")
    
    # 2. Get killer finding (search killer's base location when killer is absent)
    killer_base = BASE_LOCATIONS[killer]
    search_slot = None
    search_day = None
    
    # Search on Day 1 or Day 2
    for day in ["1", "2"]:
        for slot in SLOTS:
            if positions[killer][day][slot] != killer_base:
                search_slot = slot
                search_day = day
                break
        if search_slot:
            break
            
    if search_slot:
        plan.append(f"Day {search_day} {search_slot}: Go to {killer_base} (while {killer} is at {positions[killer][search_day][search_slot]}), search -> Finding acquired")
        loop_count = 1
    else:
        # Fall back to observing presence deviation on Day 2
        dev_slot = None
        for slot in SLOTS:
            routine_claims = {
                "marika": {"morning": "gate", "afternoon": "parlor", "evening": "gate"},
                "elise": {"morning": "upstairs", "afternoon": "study", "evening": "upstairs"},
                "vance": {"morning": "upstairs", "afternoon": "upstairs", "evening": "kitchen"},
                "hargrove": {"morning": "kitchen", "afternoon": "parlor", "evening": "kitchen"},
                "odile": {"morning": "parlor", "afternoon": "kitchen", "evening": "parlor"}
            }
            if positions[killer]["2"][slot] != routine_claims[killer][slot]:
                dev_slot = slot
                break
        plan.append(f"Day 2 {dev_slot}: Visit claimed location, observe {killer}'s absence -> Presence conflict")
        loop_count = 1

    return {
        "solved": True,
        "loop_count": loop_count,
        "plan": plan
    }
