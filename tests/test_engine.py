"""Return by Death Manor - Unit Test Suite"""

import unittest
import os
import sys
import json

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, "game"))

from engine.constants import CHARACTERS, AGENDAS, DECOY_SECRETS, ACTIONS_PER_SLOT
from engine.state import RunState, GameState, new_game_state, reset_loop
from engine.generator import generate_run
from engine.validator import validate_run
from engine.solver import solve
from engine.facts import build_all_facts
from engine.cli import run_simulation

class TestGameEngine(unittest.TestCase):

    def test_01_seed_validation(self):
        """Test 1: 100 seeds generate 100% valid runs."""
        for seed in range(1, 101):
            run_state = generate_run(seed)
            errors = validate_run(run_state)
            self.assertEqual(errors, [], f"Seed {seed} failed validation: {errors}")

    def test_02_solvability(self):
        """Test 2: All generated runs are solvable in <= 2 loops."""
        for seed in range(101, 151):
            run_state = generate_run(seed)
            solution = solve(run_state)
            self.assertTrue(solution["solved"], f"Seed {seed} could not be solved")
            self.assertLessEqual(solution["loop_count"], 2, f"Seed {seed} required {solution['loop_count']} loops")

    def test_03_no_innocent_exclusive_facts(self):
        """Test 3: No innocent character holds an exclusive fact."""
        for seed in range(200, 230):
            run_state = generate_run(seed)
            innocents = [c for c in CHARACTERS if c != run_state.killer]
            for fact in run_state.facts:
                if fact.char in innocents:
                    self.assertFalse(fact.exclusive, f"Innocent {fact.char} holds exclusive fact {fact.id}")

    def test_04_reset_loop_preservation(self):
        """Test 4: reset_loop preserves kept state and resets reset state."""
        run_state = generate_run(999)
        gs = new_game_state(run_state, start_day=1)
        
        # Modify state during play
        gs.current_day = 2
        gs.current_slot = "evening"
        gs.strain = 2
        gs.loop_no = 1
        gs.wrong_kill = True
        gs.bullet_available = False
        gs.known_facts.add("fact:test1")
        gs.notebook_entries.append("fact:test1")
        gs.fragments_seen.append("You hear a slow tick.")
        gs.trust["marika"] = 3
        gs.locked_out.add("elise")
        
        # Reset loop
        new_gs = reset_loop(gs, run_state)
        
        # Check KEPT state
        self.assertEqual(new_gs.loop_no, 2)
        self.assertEqual(new_gs.strain, 2)
        self.assertIn("fact:test1", new_gs.known_facts)
        self.assertEqual(new_gs.notebook_entries, ["fact:test1"])
        self.assertEqual(new_gs.fragments_seen, ["You hear a slow tick."])
        
        # Check RESET state
        self.assertEqual(new_gs.current_day, 2)
        self.assertEqual(new_gs.current_slot, "morning")
        self.assertTrue(new_gs.bullet_available)
        self.assertFalse(new_gs.wrong_kill)
        self.assertEqual(new_gs.trust, run_state.start_trust)
        self.assertEqual(new_gs.locked_out, set())
        self.assertEqual(new_gs.slot_actions_remaining, ACTIONS_PER_SLOT)

    def test_05_fallback_full_simulation(self):
        """Test 5: Fallback mode plays a full simulated run without exceptions."""
        for seed in [10, 42, 77, 108]:
            success = run_simulation(seed=seed, verbose=False)
            self.assertTrue(success)

    def test_06_reject_innocent_slip_keywords(self):
        """Test 6: Validator or Dialogue checks reject an innocent line with slip keyword."""
        run_state = generate_run(555)
        innocent = [c for c in CHARACTERS if c != run_state.killer][0]
        
        # Simulate LLM output for innocent containing forbidden keyword
        from llm import validate_dialogue_response
        fake_response = {
            "npc_line": "The brake lines were cut before the accident.",
            "mood": "calm",
            "choices": [
                {"intent": "probe:routine", "text": "Tell me your routine"},
                {"intent": "comfort", "text": "I'm with you"},
                {"intent": "small_talk", "text": "Nice day"},
                {"intent": "leave", "text": "Goodbye"}
            ],
            "exit_code": None
        }
        
        # Validation must reject this because innocent used a slip keyword
        choices_spec = ["probe:routine", "comfort", "small_talk", "leave"]
        valid, reason = validate_dialogue_response(
            fake_response, choices_spec, reveal_now=[],
            slip_keywords=["brake"], is_innocent=True
        )
        self.assertFalse(valid, f"Expected validation to fail, but it passed! Reason: {reason}")

if __name__ == "__main__":
    unittest.main()
