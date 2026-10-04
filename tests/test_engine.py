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

    def test_07_probe_offer_carries_no_killer_fingerprint(self):
        """Test 7: Which probe topics are offered must not reveal the killer.

        Regression guard. Probe selection used to prioritise `exclusive` facts,
        and only the killer owns an exclusive crash claim, so `probe:crash`
        appeared for the killer every turn and for nobody else. Two assertions:

        (a) exact: topic reachability is byte-identical across all characters,
            which makes it structurally impossible for the offer to single
            anyone out;
        (b) statistical: sampled offer rates agree across characters.
        """
        from engine.dialogue import generate_intents, topic_reach
        import random

        for killer in ["vance", "marika", "hargrove", "odile"]:
            secrets = {c: DECOY_SECRETS[c][0] for c in CHARACTERS}
            secrets[killer] = "inheritance"
            rs = RunState(seed=1, killer=killer, agenda="inheritance",
                          cause="brakes_cut", secrets=secrets,
                          start_trust={c: 0 for c in CHARACTERS})
            facts = build_all_facts(rs)

            # (a) exact structural invariant, at every trust level.
            for trust in range(4):
                baseline = None
                for char in CHARACTERS:
                    reach = topic_reach(char, trust, set(), facts)
                    if baseline is None:
                        baseline = reach
                    self.assertEqual(
                        reach, baseline,
                        f"topic reachability differs for {char} vs others "
                        f"(killer={killer}, trust={trust})")

            # (b) sampled rates must line up.
            samples = 500
            for trust in range(4):
                rates = {}
                for char in CHARACTERS:
                    hits = sum(
                        1 for i in range(samples)
                        if "probe:crash" in generate_intents(
                            char, trust, set(), facts, 1,
                            rng=random.Random(i)))
                    rates[char] = hits / samples
                self.assertLess(
                    max(rates.values()) - min(rates.values()), 0.08,
                    f"probe:crash offer rates diverge (killer={killer}, "
                    f"trust={trust}): {rates}")

    def test_08_killer_slip_still_obtainable(self):
        """Test 8: Symmetrising the gates must not make the killer's slip unreachable."""
        from engine.dialogue import generate_intents
        from engine.constants import CONVO_MAX_TURNS
        import random

        for killer in ["vance", "marika", "hargrove", "odile"]:
            secrets = {c: DECOY_SECRETS[c][0] for c in CHARACTERS}
            secrets[killer] = "inheritance"
            rs = RunState(seed=1, killer=killer, agenda="inheritance",
                          cause="brakes_cut", secrets=secrets,
                          start_trust={c: 0 for c in CHARACTERS})
            facts = build_all_facts(rs)

            # Model a competent player: take probe:crash the moment it is
            # offered, otherwise spend the turn on comfort, which is the only
            # move that raises trust (dialogue.py: comfort -> trust + 1).
            slip_id = f"claim:{killer}:crash"
            solved_within = 0
            trials = 200
            for i in range(trials):
                rng = random.Random(i)
                known, trust = set(), 0
                for turn in range(CONVO_MAX_TURNS):
                    intents = generate_intents(killer, trust, known, facts, 1,
                                               rng=rng)
                    if "probe:crash" in intents:
                        known.add(slip_id)
                        break
                    trust = min(3, trust + 1)  # comfort
                if slip_id in known:
                    solved_within += 1

            self.assertEqual(
                solved_within, trials,
                f"killer slip not obtainable within {CONVO_MAX_TURNS} turns "
                f"(killer={killer}); got {solved_within}/{trials}")

    def test_09_motive_never_names_the_killer_as_a_victim(self):
        """Test 9: Every (agenda, killer) pair resolves a motive that fits the killer.

        Regression guard. The `inheritance` motive used to be one shared string,
        "They profit if Adrian and Elise die.", which reached the killer's own
        LLM prompt verbatim. With Elise as the killer she was instructed to feel
        guilty about her own death. Motives are now authored per pair; this
        asserts no killer's own display name ever appears in their own motive.
        """
        from engine.constants import AGENDAS, get_motive
        from bridge import get_character_display_name

        display = {c: get_character_display_name(c) for c in CHARACTERS}

        for agenda in AGENDAS:
            # Every agenda must remain assignable to every character.
            self.assertEqual(
                sorted(AGENDAS[agenda]["motive"].keys()), sorted(CHARACTERS),
                f"{agenda} is missing a motive for some character")

            for killer in CHARACTERS:
                motive = get_motive(agenda, killer)
                self.assertTrue(motive.strip(),
                                f"empty motive for {agenda}/{killer}")

                # The killer must never be described as someone they profit
                # from killing, or as a fellow victim.
                own = display[killer]
                self.assertNotIn(
                    own, motive,
                    f"{agenda}/{killer}: own name {own!r} appears in own motive")

        # Sanity: the generic inheritance wording is still used for the other
        # four, so the per-killer entry is an override and not a rewrite.
        self.assertIn("Elise", get_motive("inheritance", "marika"))
        self.assertNotIn("Elise", get_motive("inheritance", "elise"))

    def test_10_after_hours_reads_as_night(self):
        """Test 10: The HUD must not say 'Evening' during the midnight burial round.

        Regression guard. The engine models three slots (constants.SLOTS) and
        nothing ever assigns a night slot, so the midnight sequence leaves
        current_slot on 'evening' while the scene is the small hours.

        The revolver changed the shape of this: it is available in any slot, so a
        killing can start the same burial round in the afternoon. The label is
        therefore driven by night_sequence, not merely by being in after-hours --
        asserting that here is what stops a 3pm burial from claiming to be night.
        """
        from engine.state import time_of_day_label

        # The midnight sequence wins over whatever the slot says, including the
        # 'evening' it actually holds.
        for slot in ["morning", "afternoon", "evening", "night"]:
            self.assertEqual(
                time_of_day_label(slot, True), "Night",
                f"midnight sequence must read Night, not {slot!r}")
        self.assertEqual(time_of_day_label("evening", True), "Night")

        # Daytime kills keep the real clock, including the 7pm case whose slot is
        # indistinguishable from the midnight one.
        for slot in ["morning", "afternoon", "evening"]:
            self.assertEqual(
                time_of_day_label(slot, False), slot.capitalize(),
                f"a daytime killing must keep reporting {slot!r}")

        # The real slot sequence never reaches 'night', so the flag is the only
        # thing that can produce the label.
        from engine.constants import SLOTS
        self.assertNotIn("night", SLOTS)

    def test_11_burial_prompt_cannot_poison_validation(self):
        """Test 11: The injected burial instructions must not seed forbidden words.

        Regression guard, and the subtlest of these tests. validate_dialogue_response
        runs _forbidden_hit over every generated line, and FORBIDDEN_WORDS contains
        'loop' and 'reset'. Seeding one of those into the prompt does not fail a
        test -- it silently makes the model echo it, and then every reply gets
        rejected and the game falls back. So the guilt block has to be provably
        clean, and the vault it gets injected into has to be reachable.
        """
        from llm import burial_guilt_pressure, _forbidden_hit

        for at_night in [False, True]:
            for killed in ["", "Marika", "Elise", "Odile", "Hargrove", "Vance"]:
                block = burial_guilt_pressure("Odile", killed, at_night)
                self.assertTrue(block.strip(), "burial block must not be empty")
                hit = _forbidden_hit(block.lower())
                self.assertIsNone(
                    hit,
                    f"burial block seeds forbidden word {hit!r} "
                    f"(killed={killed!r}, at_night={at_night})")

        # A model that parrots the block back is still rejected, proving the
        # validator is actually live over this text.
        echoed = {"npc_line": "I keep thinking about the loop we are all in.",
                  "choices": []}
        self.assertIsNotNone(_forbidden_hit(echoed["npc_line"].lower()))

        # The block must also actually be reachable from the system prompt.
        from llm import _build_system_prompt
        scene = {"after_hours": True, "at_night": True, "killed_name": "Marika",
                 "day": 2, "slot": "night", "location": "the parlor",
                 "present_characters": ["Odile"], "loop_number": 1,
                 "strain": 0, "deaths": 0}
        prompt = _build_system_prompt("odile", "Odile", "servant", scene)
        self.assertIn("east wall", prompt.lower())
        self.assertIn("spade", prompt.lower())
        self.assertIn("Marika", prompt)

        # Absent after-hours, the burial block must not appear at all.
        normal = {"present_characters": ["Odile"], "loop_number": 1,
                  "strain": 0, "deaths": 0}
        self.assertNotIn(
            "east wall",
            _build_system_prompt("odile", "Odile", "servant", normal))

    def test_13_daytime_burial_never_claims_night(self):
        """Test 13: A daylight killing must not produce small-hours dialogue.

        The revolver is available in any slot, so the burial round can run in the
        afternoon with current_slot still on 'afternoon'. Only the midnight menu
        sets night_sequence, so the guilt block has to branch on it. Without the
        branch the survivors talk about the small hours in broad daylight, which
        is the one thing that makes the shared scene read as a bug.
        """
        from llm import burial_guilt_pressure, _build_system_prompt

        day = burial_guilt_pressure("Odile", "Marika", at_night=False)
        night = burial_guilt_pressure("Odile", "Marika", at_night=True)

        self.assertNotIn("small hours", day.lower())
        self.assertIn("small hours", night.lower())
        self.assertIn("TODAY", day)
        self.assertIn("TONIGHT", night)

        # "still awake" is a midnight detail; the daytime variant must not use it.
        self.assertNotIn("still awake", day.lower())
        self.assertIn("still awake", night.lower())

        # And the same has to hold through the assembled prompt, for a slot that
        # is genuinely the afternoon.
        scene = {"after_hours": True, "at_night": False, "killed_name": "Marika",
                 "day": 2, "slot": "afternoon", "location": "the parlor",
                 "present_characters": ["Odile"], "loop_number": 1,
                 "strain": 0, "deaths": 0}
        prompt = _build_system_prompt("odile", "Odile", "servant", scene)
        self.assertIn("TODAY, AND WHAT YOU DID TOGETHER", prompt)
        self.assertNotIn("small hours", prompt.lower())

    def test_14_coverup_backgrounds_exist_for_every_hour(self):
        """Test 14: get_scene_bg must resolve to a declared image for every case.

        The burial scene now asks for a background instead of hardcoding
        bg parlor_night, so it can hit a name no `image` statement declares --
        which is a runtime crash, not a fallback. This walks the same three cases
        the scene can produce and checks each against the images script.rpy
        actually defines.
        """
        images = os.path.join(base_dir, "game", "script.rpy")
        with open(images, encoding="utf-8") as fh:
            declared = set()
            for line in fh:
                line = line.strip()
                if line.startswith("image bg "):
                    # "image bg parlor = ..." -> the tag is "bg parlor".
                    declared.add(" ".join(line.split()[1:3]))

        locations = ["parlor", "study", "kitchen", "upstairs", "gate"]

        # Mirrors get_scene_bg in script.rpy.
        for loc in locations:
            for slot, at_night in [(s, False) for s in
                                   ["morning", "afternoon", "evening"]] + \
                                  [(s, True) for s in
                                   ["morning", "afternoon", "evening"]]:
                name = ("bg " + loc + "_night") if at_night else (
                    "bg " + loc + "_evening" if slot == "evening"
                    else "bg " + loc)
                self.assertIn(
                    name, declared,
                    f"coverup background {name!r} (loc={loc}, slot={slot}, "
                    f"at_night={at_night}) is not declared in script.rpy")

    def test_12_wrong_kill_reaches_the_llm_context(self):
        """Test 12: The burial state must survive into the prompt that is actually sent.

        The whole stress fix depends on build_conversation_context threading
        wrong_kill through. That function lives in script.rpy and cannot be
        imported here, so this asserts the contract it has to satisfy instead:
        the keys _build_system_prompt and _build_user_prompt read.
        """
        from llm import _build_system_prompt, _build_user_prompt

        scene = {"after_hours": True, "wrong_kill": True, "killed_name": "Marika",
                 "at_night": True, "weapon": "knife",
                 "day": 2, "slot": "night", "location": "the parlor",
                 "present_characters": ["Odile", "Vance"], "loop_number": 2,
                 "strain": 2, "deaths": 1, "bullet_carried": False,
                 "is_killer": False, "discussed_topics": [],
                 "secret_truth": "INNOCENT: you are hiding a secret."}

        system = _build_system_prompt("odile", "Odile", "servant", scene)
        self.assertIn("TONIGHT, AND WHAT YOU DID TOGETHER", system)

        user = _build_user_prompt("probe:routine", 1, [], False,
                                  ["probe:routine"], {"scene": scene, "history": []})
        self.assertIn('"burial_tonight": true', user.replace("True", "true"))
        self.assertIn('"burial_was_at_night": true', user.replace("True", "true"))
        self.assertIn("Marika", user)

        # A wrong kill that has NOT yet reached after-hours (revolver path, or
        # the instant between the stab and the burial) must not drag in the
        # grave voice early.
        early = dict(scene, after_hours=False)
        self.assertNotIn(
            "east wall", _build_system_prompt("odile", "Odile", "servant", early))

if __name__ == "__main__":
    unittest.main()
