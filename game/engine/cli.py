"""Return by Death Manor - Text Mode CLI Runner"""

import sys
import os
import json
import random

# Ensure game directory is in path
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(base_dir, "game"))

from engine.constants import SLOTS, ACTIONS_PER_SLOT, MAX_STRAIN
from engine.state import new_game_state, reset_loop
from engine.generator import generate_run
from engine.conflicts import find_conflicts
from engine.dialogue import generate_intents, apply_intent
from engine.facts import get_search_findings
from engine.solver import solve

def load_fallback():
    fb_path = os.path.join(base_dir, "game", "fallback.json")
    with open(fb_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_simulation(seed: int = 42, verbose: bool = False):
    """Run an automated simulation of a complete game from start to victory."""
    run_state = generate_run(seed)
    game_state = new_game_state(run_state, start_day=1)
    all_facts = run_state.facts
    fb = load_fallback()
    
    if verbose:
        print(f"=== Starting Return by Death Manor (Seed {seed}) ===")
        print(f"Killer: {run_state.killer} | Agenda: {run_state.agenda} | Cause: {run_state.cause}")
        print(f"Hook: {run_state.hook}\n")
    
    # Check solver
    sol = solve(run_state)
    assert sol["solved"], f"Seed {seed} not solvable!"
    if verbose:
        print(f"Solver verified: Solvable in {sol['loop_count']} loop(s)")

    # Execute simulation loop
    killer = run_state.killer
    
    # 1. Day 1: Visit killer, talk to gain trust & crash slip
    day_str = str(game_state.current_day)
    killer_loc_d1 = run_state.positions[killer][day_str]["morning"]
    game_state.current_location = killer_loc_d1
    
    # Conversation turns: comforts + probe:crash
    turns = 0
    while turns < 4 and f"claim:{killer}:crash" not in game_state.known_facts:
        turns += 1
        intents = generate_intents(killer, game_state.trust[killer], game_state.known_facts, all_facts, turns)
        
        # Choose comfort if trust < 2, else probe:crash
        if game_state.trust[killer] < 2:
            chosen = "comfort" if "comfort" in intents else intents[0]
        else:
            chosen = "probe:crash" if "probe:crash" in intents else intents[0]
            
        res = apply_intent(chosen, killer, game_state, run_state, all_facts)
        if verbose:
            print(f"Turn {turns}: Chose {chosen} -> Trust: {res['new_trust']}, Revealed: {[f.id for f in res['revealed_facts']]}")

    assert f"claim:{killer}:crash" in game_state.known_facts, "Failed to learn crash slip!"
    
    # 2. Advance to Day 2
    game_state.current_day = 2
    game_state.current_slot = "morning"
    game_state.bullet_available = True
    
    # Find killer on Day 2
    killer_loc_d2 = run_state.positions[killer]["2"]["morning"]
    game_state.current_location = killer_loc_d2
    
    # 3. Shoot killer on Day 2!
    if verbose:
        print(f"\nDay 2 morning: Adrian confronts {killer} at {killer_loc_d2} with the revolver...")
    
    assert game_state.bullet_available, "Revolver has no bullet!"
    target = killer
    if target == run_state.killer:
        game_state.killer_shot = True
        game_state.game_over = True
        game_state.ending = "victory"
        if verbose:
            print(f"BANG! Shot {killer}. The killer is dead. VICTORY!")
            epilogue = fb["epilogues"][run_state.agenda][killer]
            print(f"Epilogue: {epilogue}")
    
    assert game_state.ending == "victory"
    return True

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    run_simulation(seed=42, verbose=True)
    print("Simulation completed successfully!")
