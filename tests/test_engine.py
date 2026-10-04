"""Return by Death Manor - Unit Test Suite"""

import unittest
import os
import re
import subprocess
import sys
import json
import textwrap
import time
import types

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, "game"))

from engine.constants import CHARACTERS, AGENDAS, DECOY_SECRETS, ACTIONS_PER_SLOT
from engine.state import RunState, GameState, new_game_state, reset_loop
from engine.generator import generate_run
from engine.validator import validate_run
from engine.solver import solve
from engine.facts import build_all_facts
from engine.cli import run_simulation


# The Ren'Py SDK, when a copy can be found. Every audio call in script.rpy lives
# in a label body rather than a python: block, and a bare Python call in a Ren'Py
# statement position is a parse error -- 39 of them shipped that way in d11bab3
# and nothing here caught it. The real parser is the assertion.
SDK_CANDIDATES = [
    os.path.expanduser("~/renpy-8.5.3-sdk"),
    os.path.expanduser("~/Downloads/renpy-8.5.3-sdk"),
    os.path.expanduser("~/renpy"),
    "/usr/share/renpy",
]


def find_renpy_launcher():
    for cand in SDK_CANDIDATES:
        launcher = os.path.join(cand, "renpy.sh")
        if os.path.isfile(launcher):
            return launcher
    return None


def extract_rpy_slice(src, start_marker, end_marker):
    """Return the dedented text from one marker up to (not including) another.

    The audio helpers live inside Ren'Py `init python:` blocks, so they cannot be
    imported -- but they are ordinary Python, and running them against a stub is
    the only way to catch the class of bug no parse check can see: a helper that
    raises the instant it is called.
    """
    start = src.index(start_marker)
    end = src.index(end_marker, start)

    # Markers match mid-line, so back up to the line start. Otherwise the first
    # line loses its indentation and textwrap.dedent has no common prefix left.
    start = src.rindex("\n", 0, start) + 1
    return textwrap.dedent(src[start:end])


class FakeChannel:
    """Stand-in for a Ren'Py audio channel, tracking what is playing."""

    def __init__(self):
        self.playing = None
        self.looping = None

    def play(self, path, loop=False, relative_volume=1.0):
        # Ren'Py only keeps the loop queue for files queued with loop=True.
        self.playing = path
        self.looping = [path] if loop else None

    def stop(self, fadeout=None):
        self.playing = None
        self.looping = None


class FakeRenpyAudio:
    """Just enough of renpy.music / renpy.sound for the audio helpers."""

    def __init__(self):
        self.channels = {}
        self.relative_volumes = []

    def _chan(self, name):
        return self.channels.setdefault(name, FakeChannel())

    def register_channel(self, name, mixer=None, loop=False):
        self._chan(name)

    def set_volume(self, volume, delay=0, channel="music"):
        pass

    def play(self, path, channel="music", loop=False, fadein=None,
             relative_volume=1.0, **kw):
        self.relative_volumes.append((channel, path, relative_volume))
        self._chan(channel).play(path, loop=loop,
                                 relative_volume=relative_volume)

    def stop(self, channel="music", fadeout=None):
        self._chan(channel).stop()

    def get_playing(self, channel="music"):
        return self._chan(channel).playing

    def get_loop(self, channel="music"):
        return self._chan(channel).looping


class FakeRenpy:
    """The renpy module as far as the audio helpers are concerned."""

    def __init__(self):
        self.audio = FakeRenpyAudio()
        self.music = self.audio
        self.sound = self.audio
        self.random = __import__("random")
        self.store = types.SimpleNamespace()
        self.config = types.SimpleNamespace()
        self.persistent = types.SimpleNamespace()

    @staticmethod
    def loadable(path):
        return True


class AudioHelperTestCase(unittest.TestCase):
    """Executes the real audio helpers out of script.rpy against a stub.

    Ren'Py will not let a test import from an `init python:` block, so the
    helpers are sliced out of the file and exec'd. That keeps the test honest --
    it runs the code the game runs, not a copy that can drift.
    """

    @classmethod
    def setUpClass(cls):
        from engine import audio_manifest

        with open(os.path.join(base_dir, "game", "script.rpy"),
                  encoding="utf-8") as fh:
            src = fh.read()

        clock = extract_rpy_slice(
            src, "_ambience_clock = {", "_AUDIO_EVENT_CHANNELS = ")
        start = src.index("_AUDIO_EVENT_CHANNELS = ")
        channels = textwrap.dedent(
            src[start:src.index("\n", start) + 1])
        audio = extract_rpy_slice(
            src, 'renpy.music.register_channel("ambience"',
            "# Both curated title tracks get used")

        cls.renpy = FakeRenpy()
        ns = dict(vars(audio_manifest))
        ns["renpy"] = cls.renpy
        ns["time"] = time
        for chunk in (clock, channels, audio):
            exec(compile(chunk, "script.rpy", "exec"), ns)
        cls.ns = ns

    def setUp(self):
        self.renpy.audio.channels.clear()
        self.renpy.audio.relative_volumes.clear()
        self.ns["_ambience_clock"]["last_pool_at"] = 0.0

    def call(self, name, *a, **kw):
        return self.ns[name](*a, **kw)

    def playing(self, channel):
        return self.renpy.audio.get_playing(channel)

    def off_cooldown(self):
        """Put the pool's cooldown in the past so silence is the only gate."""
        self.ns["_ambience_clock"]["last_pool_at"] = time.monotonic() - 10_000

    def silence_piano(self):
        """Pin the accent roll to a loss, so a test can isolate the pool.

        The piano accent shares the idle tick and plays on the stinger channel,
        which makes the house non-silent -- so an unlucky roll suppresses the
        pool for that tick. That is the intended behaviour, but it is noise in a
        test that is only asking about the pool.
        """
        self._real_random = self.renpy.random.random
        self.renpy.random.random = lambda: 0.999999

    def restore_random(self):
        if hasattr(self, "_real_random"):
            self.renpy.random.random = self._real_random
            del self._real_random

    def tearDown(self):
        self.restore_random()

    def script(self):
        with open(os.path.join(base_dir, "game", "script.rpy"),
                  encoding="utf-8") as fh:
            return fh.read()


class TestAudioHelpers(AudioHelperTestCase):
    """The runtime behaviour of the audio layer, which lint cannot check."""

    def test_26_every_helper_runs_without_raising(self):
        """Test 26: calling each helper must not raise.

        This is the test that would have caught the original bug. The helpers
        stamped the watcher's timestamp by assigning to a bare global, which
        Python treats as a local, so set_music() raised UnboundLocalError on its
        first call -- invisible to lint, to the file-existence tests, and to
        anything short of actually running the game.
        """
        self.call("set_music", "night")
        self.call("set_music", "kitchen", loop=False, fade=0.5)
        self.call("set_ambience", "storm_wind", loop=True)
        self.call("sfx_sting", "static")
        self.call("play_ambience_bed", "atmos_low")
        self.call("piano_accent_tick")
        self.call("stop_ambience", fade=0.1)
        self.call("stop_music", fade=0.1)
        self.call("idle_ambience_tick")

        self.assertEqual(self.playing("music"), None)
        self.assertEqual(self.playing("ambience"), None)

    def test_27_unknown_keys_no_op_instead_of_raising(self):
        """Test 27: a bad key must be harmless, not fatal mid-scene."""
        for call in (("set_music",), ("set_ambience",), ("sfx_sting",)):
            self.call(call[0], "no_such_track")
        self.call("play_ambience_bed", "no_such_track")
        self.call("piano_accent_tick")
        self.assertEqual(self.playing("music"), None)

    def test_28_every_audible_channel_counts_as_sound(self):
        """Test 28: silence must include sfx and voice, not just the helpers.

        The 29 original `play sound` statements and the screen-driven voice blip
        never pass through an audio helper, so a helper-only stamp would call the
        house silent while a gunshot is going off.
        """
        self.assertTrue(self.call("audio_is_silent"),
                        "with nothing playing the house is silent")

        for channel, path, loop in (
                ("sfx", "audio/gunshot.wav", False),
                ("voice_sfx", "audio/voice_adrian.wav", True),
                ("stinger", "audio/ambience/static.ogg", False)):
            with self.subTest(channel=channel):
                self.renpy.audio.channels.clear()
                self.renpy.audio.play(path, channel=channel, loop=loop)
                self.assertFalse(
                    self.call("audio_is_silent"),
                    f"a live {channel} channel must count as audio")

    def test_29_a_music_bed_alone_is_still_silence(self):
        """Test 29: music must not make the house non-silent.

        A bed is meant to be playing whenever the player is in a scene. Counting
        it would mean the pool never fires at all, which is the failure mode
        this guards.
        """
        self.call("set_music", "night")
        self.assertTrue(self.call("audio_is_silent"))

    def test_30_a_looping_bed_holds_the_pool_off(self):
        """Test 30: the storm must survive the idle watcher.

        storm_wind is 26s of weather the scene deliberately asked for, and the
        pool shares its channel, so a pool track would cut the storm mid-scene.
        An earlier attempt classified a loop as "deliberate background, therefore
        silence" -- which is exactly backwards: it let the next tick overwrite
        the storm. This test is the scar from that.
        """
        self.call("set_ambience", "storm_wind", loop=True)
        self.assertFalse(self.call("audio_is_silent"),
                         "a looping bed is audible, so the house is not silent")

        self.off_cooldown()
        self.silence_piano()
        self.call("idle_ambience_tick")
        self.assertEqual(self.playing("ambience"), "audio/ambience/storm_wind.ogg",
                         "the pool must not replace the looping storm bed")

    def test_31_the_pool_fires_on_silence_then_backs_off(self):
        """Test 31: silence triggers the pool, and the cooldown holds it back."""
        from engine import audio_manifest

        self.silence_piano()

        # Something audible: no pool.
        self.off_cooldown()
        self.renpy.audio.play("audio/heartbeat.wav", channel="sfx")
        self.call("idle_ambience_tick")
        self.assertEqual(self.playing("ambience"), None,
                         "the pool must stay quiet while something is audible")

        # Silent and off cooldown: it fires, with a curated track.
        self.renpy.audio.channels.clear()
        self.off_cooldown()
        self.call("idle_ambience_tick")
        played = self.playing("ambience")
        self.assertIsNotNone(played, "the pool must play once the house is quiet")
        self.assertIn(played, audio_manifest.AMBIENT_POOL,
                      "the pool may only play curated ambience")

        # Straight after: cooldown holds, even though ambience is free again.
        self.renpy.audio.channels.clear()
        self.call("idle_ambience_tick")
        self.assertEqual(self.playing("ambience"), None,
                         "the pool must respect AMBIENCE_COOLDOWN")

    def test_32_the_pool_reaches_every_track_and_nothing_else(self):
        """Test 32: six tracks would feel like one if the pick were constant."""
        self.silence_piano()
        seen = set()
        for _ in range(500):
            self.off_cooldown()
            self.renpy.audio.channels.clear()
            self.call("idle_ambience_tick")
            seen.add(self.playing("ambience"))
        from engine import audio_manifest
        self.assertEqual(seen, set(audio_manifest.AMBIENT_POOL))

    def test_33_the_piano_accent_layers_instead_of_replacing(self):
        """Test 33: piano is the one track meant to surface at any moment.

        It goes on the stinger channel at reduced relative volume so it can play
        over a bed rather than cutting it. Rolling it onto the ambience channel
        would replace storm_wind, which is the exact bug test 30 guards.
        """
        from engine import audio_manifest

        self.call("set_ambience", "storm_wind", loop=True)
        accent = audio_manifest.AMBIENCE["piano"]
        self.renpy.audio.play(accent, channel="stinger",
                              relative_volume=audio_manifest.PIANO_ACCENT_VOLUME)

        self.assertEqual(self.playing("ambience"), "audio/ambience/storm_wind.ogg",
                         "the accent must not disturb the bed")
        self.assertEqual(self.playing("stinger"), accent)

    def test_35_a_piano_accent_suppresses_the_pool_for_that_tick(self):
        """Test 35: the accent and the pool share a tick, so they must not clash.

        idle_ambience_tick() rolls the accent first. A hit lands on the stinger
        channel, which makes the house non-silent, so the pool correctly stands
        down for that tick. Two layers of atmosphere at once would read as a cue
        rather than as the house settling.
        """
        from engine import audio_manifest

        self.off_cooldown()

        # Accent wins the roll: no pool this tick.
        self.renpy.random.random = lambda: 0.0
        try:
            self.call("idle_ambience_tick")
        finally:
            self.restore_random()
        self.assertEqual(self.playing("stinger"),
                         audio_manifest.AMBIENCE["piano"])
        self.assertEqual(self.playing("ambience"), None,
                         "the pool must stand down for the tick an accent wins")

        # Accent loses, and the previous phrase has finished: pool fires.
        self.off_cooldown()
        self.silence_piano()
        self.renpy.audio.channels["stinger"].stop()
        self.call("idle_ambience_tick")
        self.assertIn(self.playing("ambience"), audio_manifest.AMBIENT_POOL)

    def test_34_the_piano_accent_is_actually_sparse(self):
        """Test 34: a roll that fires often stops being an accent.

        Driven by the 1s idle timer, so the constant is a per-second probability.
        """
        import random as _random
        from engine import audio_manifest

        chance = audio_manifest.PIANO_ACCENT_CHANCE
        self.assertLessEqual(chance, 0.01,
                             "above 1% per second it reads as a cue, not texture")

        # Force the roll to succeed and confirm it plays at the reduced volume.
        original = self.renpy.random.random
        self.renpy.random.random = lambda: 0.0
        try:
            self.call("piano_accent_tick")
        finally:
            self.renpy.random.random = original

        plays = [p for p in self.renpy.audio.relative_volumes
                 if p[1] == audio_manifest.AMBIENCE["piano"]]
        self.assertEqual(len(plays), 1, "a winning roll must play exactly once")
        channel, _, volume = plays[0]
        self.assertEqual(channel, "stinger")
        self.assertEqual(volume, audio_manifest.PIANO_ACCENT_VOLUME)
        self.assertLess(volume, audio_manifest.VOLUME_STINGER,
                        "piano is texture; it must sit under the stingers")

        # And the channel choice is the helper's own decision, not something the
        # test supplied. Moving the accent onto the ambience channel would let it
        # replace storm_wind, which is the bug test 30 guards -- so assert it here
        # against the real code path rather than against a hand-rolled play.
        self.renpy.audio.relative_volumes.clear()
        self.renpy.random.random = lambda: 0.0
        try:
            self.call("piano_accent_tick")
        finally:
            self.restore_random()
        self.assertEqual(
            [(c, p) for c, p, _ in self.renpy.audio.relative_volumes],
            [("stinger", audio_manifest.AMBIENCE["piano"])],
            "piano_accent_tick must play on stinger, never on ambience")

        # And a losing roll must stay silent.
        self.renpy.audio.relative_volumes.clear()
        self.renpy.random.random = lambda: 0.999999
        try:
            self.call("piano_accent_tick")
        finally:
            self.renpy.random.random = original
        self.assertEqual(self.renpy.audio.relative_volumes, [])

    def test_36_no_curated_track_ships_with_nowhere_to_play(self):
        """Test 36: a picked track with no call site is dead weight.

        Two of the 31 chosen tracks had no call site at all -- kitchen_alt and
        title_alt -- so they shipped in the build while counting as done in the
        manifest. kitchen_alt is now the kitchen bed from the second loop onward,
        and the main menu alternates between the two title tracks. Both are
        deterministic, not random, so the assertion is on the reference itself.
        """
        src = self.script()

        self.assertIn('set_music("kitchen_alt" if game_state.loop_no > 1 '
                      'else "kitchen")', src,
                      "kitchen_alt must be reachable from the location picker")
        self.assertIn('config.main_menu_music = MUSIC["title_alt"',
                      src,
                      "the alternate title must be a real menu option")

        # Every curated key must appear as a reference somewhere in the script.
        from engine import audio_manifest
        for key in list(audio_manifest.MUSIC) + list(audio_manifest.AMBIENCE):
            with self.subTest(key=key):
                self.assertIn('"%s"' % key, src,
                              f"{key} is curated but nothing references it")


class TestRenpyIntegration(unittest.TestCase):
    """Checks that need the actual Ren'Py parser rather than a stub."""

    def test_37_renpy_lint_parses_every_script(self):
        """Test 37: hand the scripts to the parser that will run them.

        Two separate build-breaking errors in this project's recent history -- a
        dedented `return` in build_conversation_context (2cbbf11) and 39 bare
        audio calls in statement position (d11bab3) -- passed every test written
        for them, because no test ever gave the scripts to the real parser. The
        audio tests prove the wiring points at files that exist; only this proves
        the files are scripts Ren'Py will load at all.

        Skipped rather than failed without an SDK, so a bare checkout still runs.
        """
        launcher = find_renpy_launcher()
        if not launcher:
            self.skipTest("no Ren'Py SDK found; skipping the real parser")

        result = subprocess.run(
            [launcher, ".", "lint"], cwd=base_dir,
            capture_output=True, text=True, timeout=600)

        errors = re.findall(r'^File "(.+?)", line (\d+): (.+)$',
                            result.stdout, re.M)
        self.assertEqual(
            errors, [],
            "Ren'Py lint reported errors:\n" + "\n".join(
                f"  {f}:{n}  {msg}" for f, n, msg in errors))

    def test_38_audio_calls_in_labels_carry_the_python_prefix(self):
        """Test 38: the narrow regression test for the d11bab3 breakage.

        Kept separate from test 36 so the failure names the actual mistake even
        on a machine with no SDK installed. A bare `set_music(...)` in a label is
        a parse error; inside a `python:` block the same text is correct, so this
        has to track block state rather than just grep for the pattern.
        """
        with open(os.path.join(base_dir, "game", "script.rpy"),
                  encoding="utf-8") as fh:
            lines = fh.read().split("\n")

        audio = re.compile(r'(?<!\$)\b(set_music|set_ambience|sfx_sting|'
                           r'stop_music|stop_ambience|play_ambience_bed)\(')

        offenders = []
        in_python = None
        for lineno, line in enumerate(lines, 1):
            code = line.split("#")[0].rstrip()
            if not code.strip():
                continue
            indent = len(code) - len(code.lstrip())
            body = code.strip()

            # `def` lines declare; they are not call sites, and they close any
            # enclosing python: block for our purposes.
            if body.startswith("def "):
                in_python = None
                continue

            if in_python is not None:
                if indent <= in_python:
                    in_python = None
                else:
                    continue

            if body == "python:":
                in_python = indent
                continue

            if audio.search(code) and not body.startswith("$"):
                offenders.append((lineno, body[:70]))

        self.assertEqual(
            offenders, [],
            "audio calls outside a python: block need a $ prefix:\n" +
            "\n".join(f"  script.rpy:{n}  {t}" for n, t in offenders))

    def test_39_audio_state_is_mutated_not_rebound(self):
        """Test 39: the helpers must not shadow the watcher's own state.

        Assigning to a bare global from inside a function makes it local, so the
        original helpers raised UnboundLocalError on the first set_music() call.
        The clock is a dict now, and this asserts no bare assignment to the old
        names survives anywhere in the audio layer.
        """
        with open(os.path.join(base_dir, "game", "script.rpy"),
                  encoding="utf-8") as fh:
            lines = fh.read().split("\n")

        banned = re.compile(r'^\s*\$?\s*(?:_last_audio_at|_last_pool_at)\s*=')
        offenders = [(n, l.strip()) for n, l in enumerate(lines, 1)
                     if banned.match(l)]

        self.assertEqual(
            offenders, [],
            "audio state must go through _ambience_clock:\n" +
            "\n".join(f"  script.rpy:{n}  {t}" for n, t in offenders))


if __name__ == "__main__":
    unittest.main()

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

    def test_15_renpy_python_blocks_have_no_stranded_return(self):
        """Test 15: No `return` may be stranded outside a def by a bad indent.

        Ships-a-broken-build guard. A `return` in script.rpy made Ren'Py refuse to
        launch the game ("'return' outside function"): an edit had dedented the
        body of build_conversation_context by one level, which ended the def early
        and dropped the rest of it at script level.

        `py_compile` cannot catch this -- it only ever sees the .py files, never the
        .rpy -- so a broken indent passed the suite and reached a pushed commit.
        Two earlier versions of this guard also passed on the broken file, because
        wrapping a block in a function (how Ren'Py actually compiles it) makes a
        stranded `return` legal again, and dedenting the block body breaks
        multi-line parenthesised imports. So this works on indentation alone:

        For every `return` in a python block, walk backwards for the block openers
        that enclose it. Legal, because Ren'Py compiles blocks as functions:
            return            directly in the block body, no enclosing opener
            def f(): ...      return inside a def
        Illegal, and only reachable when a def above it dedented early:
            if x: ...         return nested in control flow at block level

        A `return` statement can never sit inside brackets, so continuation lines
        are irrelevant and no parsing is needed.
        """
        import re

        marker = re.compile(r"^(\s*)(?:init\s+|init\s+\d+\s*)?python:\s*$")
        openers = ("if ", "elif ", "else", "for ", "while ", "try", "except",
                   "finally", "with ", "match ", "case ")

        def indent_of(line):
            return len(line) - len(line.lstrip())

        def enclosing(body, idx, floor):
            """Block openers enclosing body[idx], innermost first."""
            stack = []
            level = indent_of(body[idx])
            j = idx - 1
            while j >= 0:
                line = body[j]
                if not line.strip() or line.lstrip().startswith("#"):
                    j -= 1
                    continue
                ind = indent_of(line)
                if ind < level:
                    stack.append(line.strip())
                    level = ind
                    if ind <= floor:
                        break
                j -= 1
            return stack

        for rel in ["script.rpy", "custom_screens.rpy", "options.rpy"]:
            path = os.path.join(base_dir, "game", rel)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().split("\n")

            total = len(lines)
            checked = 0
            i = 0
            while i < total:
                m = marker.match(lines[i])
                if not m:
                    i += 1
                    continue
                floor = len(m.group(1))
                body = []
                j = i + 1
                while j < total:
                    line = lines[j]
                    if not line.strip():
                        body.append(line)
                        j += 1
                        continue
                    # A column-0 comment does not end a python block.
                    if line.lstrip().startswith("#"):
                        body.append(line)
                        j += 1
                        continue
                    if indent_of(line) > floor:
                        body.append(line)
                        j += 1
                        continue
                    break

                for k, line in enumerate(body):
                    if not line.strip().startswith("return"):
                        continue
                    checked += 1
                    stack = enclosing(body, k, floor)
                    in_def = any(o.startswith("def ") or o.startswith("async def ")
                                 or o.startswith("class ") for o in stack)
                    if in_def or not stack:
                        continue
                    # No def above it, yet it is nested: the block dedented early.
                    self.fail(
                        f"{rel}:{i + 1 + k} `return` is outside every def but "
                        f"nested inside {' -> '.join(reversed(stack))}. A python "
                        f"block dedented early and stranded the rest of a def at "
                        f"script level; Ren'Py will refuse to launch with "
                        f"'return' outside function")
                i = j

            if rel == "script.rpy":
                self.assertGreater(checked, 0,
                                   "found no returns to check at all")


    def test_16_absence_records_are_visible_to_the_player(self):
        """Test 16: An observed absence must be renderable, in words.

        Absence facts are stored in known_facts as bare ID strings.
        build_all_facts emits only world/claim/finding/fragment, so there is no
        Fact object and no .text behind them -- which is exactly why the notebook
        could paint a red "CONTRADICTS THEMSELF" verdict while the evidence
        behind it stayed invisible. These helpers are what put the observation
        on the Timeline tab instead.
        """
        from bridge import (parse_presence_fact, presence_absence_text,
                            presence_absence_text_for)
        from engine.constants import LOCATIONS, SLOTS

        # Every shape the game can actually write must parse.
        for char in CHARACTERS:
            for loc in LOCATIONS:
                for slot in SLOTS:
                    for day in (1, 2):
                        fid = f"presence:absence:{char}:{loc}:{slot}:{day}"
                        parsed = parse_presence_fact(fid)
                        self.assertIsNotNone(parsed, f"failed to parse {fid}")
                        self.assertEqual(parsed[0], "absence")
                        self.assertEqual(parsed[1], char)
                        self.assertEqual(parsed[2], loc)
                        self.assertEqual(parsed[3], slot)
                        self.assertEqual(parsed[4], day)

                        line = presence_absence_text_for(fid)
                        self.assertTrue(line and line.strip())
                        # It must name the room and the person, or it is not
                        # evidence the player can reason from.
                        from bridge import (get_character_display_name,
                                            get_location_display_name)
                        self.assertIn(get_character_display_name(char), line)
                        self.assertIn(get_location_display_name(loc), line)

        # Sightings use the same ID shape with a different kind.
        seen = parse_presence_fact("presence:seen:elise:study:morning:1")
        self.assertEqual(seen[0], "seen")

        # And it must not claim they lied. A deviation is the fairness structure,
        # not evidence, so the sentence may only report what Adrian saw.
        line = presence_absence_text_for("presence:absence:vance:study:afternoon:2")
        for word in ["lie", "lying", "lied", "liar", "contradict", "guilt", "knew"]:
            self.assertNotIn(
                word, line.lower(),
                f"absence text asserts more than it observed: {word!r} in {line!r}")

        # Junk must not raise.
        for bad in ["", "nonsense", "presence:", "presence:absence:elise",
                    "presence:absence:elise:study:morning",
                    "presence:absence:elise:study:morning:2:extra",
                    "presence:absence:elise:study:morning:x", None, 7]:
            if bad is None or isinstance(bad, int):
                self.assertIsNone(parse_presence_fact(bad))
            else:
                self.assertIsNone(
                    parse_presence_fact(bad), f"should not have parsed {bad!r}")

    def test_17_notebook_renders_no_verdict(self):
        """Test 17: The notebook must not grade the evidence or the people.

        Guards the removal of the red "CONTRADICTS THEMSELF" badge, the "DAMNING"
        badge, and the raw Fact.id heading that named the character outright.
        Also asserts no screen calls find_conflicts, so the verdict cannot come
        back through a new import.
        """
        import glob
        import re

        banned_strings = ["CONTRADICTS THEMSELF", "DAMNING", "character_has_conflict"]
        banned_calls = ["find_conflicts"]

        # Nothing anywhere in the .rpy layer may reintroduce a verdict.
        # Comment lines are skipped: a comment explaining what was removed is
        # documentation, not something the player can ever see rendered, and
        # banning the words outright would forbid recording why they went.
        for path in sorted(glob.glob(os.path.join(base_dir, "game", "*.rpy"))):
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            code = "\n".join(
                l for l in raw.split("\n") if not l.lstrip().startswith("#"))
            for banned in banned_strings:
                self.assertNotIn(
                    banned, code,
                    f"{os.path.basename(path)} still renders {banned!r}")
            for call in banned_calls:
                for m in re.finditer(re.escape(call) + r"\s*\(", code):
                    self.fail(
                        f"{os.path.basename(path)} calls {call}() -- the "
                        f"notebook must not compute verdicts")

        # The Evidence tab must not render a raw id or text_key: the killer's
        # id is finding:{killer}:... and its text_key is the literal string
        # "finding.killer.obsession". Either one names the murderer.
        with open(os.path.join(base_dir, "game", "custom_screens.rpy"),
                  encoding="utf-8") as fh:
            screens = fh.read()
        self.assertNotIn("[item.id]", screens)
        self.assertNotIn("item.text_key", screens)
        self.assertNotIn("item.exclusive", screens)

        # ...and the neutral label it uses instead must exist and stay neutral.
        from bridge import evidence_label
        self.assertEqual(evidence_label("world"), "A document")
        self.assertEqual(evidence_label("finding"), "Something left behind")
        self.assertEqual(evidence_label("claim"), "Something you noted")
        for kind in ["world", "finding", "claim", "fragment", "presence", None]:
            label = evidence_label(kind).lower()
            for name in CHARACTERS:
                from bridge import get_character_display_name
                self.assertNotIn(
                    get_character_display_name(name).lower(), label,
                    f"evidence_label({kind!r}) leaks a character name")
            for word in ["kill", "murder", "guilt", "damning", "lie", "suspect"]:
                self.assertNotIn(word, label,
                                 f"evidence_label({kind!r}) grades the evidence: {word!r}")

    def test_18_absence_text_is_shown_on_the_timeline(self):
        """Test 18: The Timeline tab must actually render the absence text.

        test_16 proves the helper produces a sentence; this proves the screen
        asks for it. Without this the evidence would be computable but invisible,
        which is the bug being fixed.
        """
        with open(os.path.join(base_dir, "game", "custom_screens.rpy"),
                  encoding="utf-8") as fh:
            screens = fh.read()

        self.assertIn("presence_absence_text(", screens)
        self.assertIn("parse_presence_fact(", screens)

        # The old sighting-only lookup reconstructed an expected key from the
        # generator's position map, so a room you visited that turned out empty
        # could never render. The new index must be driven by known_facts.
        self.assertNotIn("run_state.positions[c][str(d)][s]", screens)

    def test_19_manifest_tracks_all_exist_on_disk(self):
        """Test 19: every path the audio manifest claims must actually ship.

        The manifest was built by copying files out of archives at the project
        root, which are not committed. A path that survived the copy but not the
        commit would be a silent runtime failure -- Ren'Py raises nothing for a
        missing file, it just plays nothing.
        """
        from engine.audio_manifest import (
            MUSIC, AMBIENCE, AMBIENT_POOL, LEGACY_SFX, all_tracks,
        )

        game_dir = os.path.join(base_dir, "game")

        missing = [p for p in all_tracks()
                   if not os.path.isfile(os.path.join(game_dir, p))]
        self.assertEqual(missing, [],
                         f"audio manifest points at files that do not exist: {missing}")

        # Non-empty, because a zero-byte ogg is worse than a missing one: it
        # exists, so nothing complains, and the channel just goes quiet.
        empty = [p for p in all_tracks()
                 if os.path.getsize(os.path.join(game_dir, p)) == 0]
        self.assertEqual(empty, [], f"empty audio files: {empty}")

        self.assertTrue(MUSIC, "no music tracks in the manifest")
        self.assertTrue(AMBIENT_POOL, "silence pool is empty")

    def test_20_every_audio_key_used_in_script_is_in_the_manifest(self):
        """Test 20: no .rpy may reference an audio key the manifest lacks.

        This is the audio equivalent of test_14. set_music() and friends return
        quietly when a key is unknown, so a typo would produce a scene with no
        music and no error anywhere -- exactly the class of bug that shipped an
        undeclared background before.
        """
        rpy_files = [f for f in os.listdir(os.path.join(base_dir, "game"))
                     if f.endswith(".rpy")]

        # set_music/set_ambience take MUSIC keys, sfx_sting takes AMBIENCE keys.
        usage = {"set_music": set(), "set_ambience": set(), "sfx_sting": set()}
        for name in rpy_files:
            with open(os.path.join(base_dir, "game", name), encoding="utf-8") as fh:
                for line in fh:
                    for fn in usage:
                        token = fn + "("
                        idx = line.find(token)
                        while idx != -1:
                            arg = line[idx + len(token):].split(",")[0]
                            # An inline conditional can put two keys in one call,
                            # so take every quoted token before the comma.
                            for key in re.findall(r'"([a-z0-9_]+)"', arg):
                                usage[fn].add(key)
                            idx = line.find(token, idx + 1)

        from engine.audio_manifest import MUSIC, AMBIENCE

        self.assertTrue(usage["set_music"],
                        "no set_music call found -- the scan itself is broken")

        bad_music = usage["set_music"] - set(MUSIC)
        bad_amb = usage["set_ambience"] - set(AMBIENCE)
        bad_sting = usage["sfx_sting"] - set(AMBIENCE)

        self.assertEqual(bad_music, set(),
                         f"set_music keys missing from MUSIC: {bad_music}")
        self.assertEqual(bad_amb, set(),
                         f"set_ambience keys missing from AMBIENCE: {bad_amb}")
        self.assertEqual(bad_sting, set(),
                         f"sfx_sting keys missing from AMBIENCE: {bad_sting}")

    def test_21_wired_audio_covers_every_scene_and_watches_for_silence(self):
        """Test 21: the wiring is present and the silence watcher cannot fire on
        top of a looping bed.

        Two failure modes this catches. The first is a scene that silently lost
        its music during an edit -- the symptom is invisible and there is no
        error, so only an assertion can catch it. The second is the watcher
        playing a pool track over storm_wind, which loops: two ambience tracks
        on one channel means the second interrupts the first mid-word.
        """
        from engine.audio_manifest import (
            AMBIENCE_LOOPING, AMBIENCE_COOLDOWN, AMBIENT_POOL,
        )

        with open(os.path.join(base_dir, "game", "script.rpy"),
                  encoding="utf-8") as fh:
            script = fh.read()

        # Every scene that plays a bed or a sting.
        for fn in ("set_music", "set_ambience", "sfx_sting", "stop_music",
                   "stop_ambience", "play_ambience_bed"):
            self.assertIn(fn + "(", script, f"{fn}() helper is never called")

        # The scenes the curation table promised audio for, and what each one
        # must still contain. Naming the exact call rather than accepting any
        # audio call matters: a scene that loses its bed but keeps its sting
        # would pass a looser check, which is exactly what mutation M5 caught.
        required = {
            "day1_intro": ['set_music("atmos_low")', 'sfx_sting("static")'],
            "day_slot_start": ['set_music("kitchen_alt" if game_state.loop_no > 1 else "kitchen")'],
            "advance_slot": ['sfx_sting("evening_bell")'],
            "day1_night_transition": ['set_music("night")',
                                      'set_ambience("storm_wind"'],
            "day2_morning_transition": ['set_music("clock")'],
            "day2_night_transition": ['set_music("atmos_low")'],
            "wrong_kill_coverup": ['sfx_sting("wrong")',
                                   'set_music("death_atmos")'],
            "day1_evening_bond": ['set_music("evening_final")'],
            "after_hours": ['set_music("atmos_general")',
                            'sfx_sting("body_thud")'],
            "night_death": ['set_music("death")',
                            'sfx_sting("return_by_death")',
                            "stop_music("],
            "loop_confession_attempt": ['set_music("death")'],
            "ending_victory": ['set_music("ending")'],
            "ending_swallowed": ['set_music("game_over")'],
        }

        for label, calls in required.items():
            self.assertIn("label " + label + ":", script,
                          f"label {label} no longer exists")
            body = script.split("label " + label + ":", 1)[1]
            # Take only this label's text, up to the next one.
            nxt = body.find("\nlabel ")
            if nxt != -1:
                body = body[:nxt]
            for call in calls:
                self.assertIn(call, body,
                              f"label {label} lost its audio call: {call}")

        # Only storm_wind loops, and the pool never does. If the pool gained a
        # looping entry it would fight itself on the ambience channel.
        self.assertTrue(AMBIENCE_LOOPING)
        for path in AMBIENT_POOL:
            self.assertFalse(
                any(path.endswith(key.split("/")[-1])
                    for key in AMBIENCE_LOOPING),
                f"{path} is in the pool and also loops; it would never stop")

        # The pool's cooldown is its only timing knob. An earlier version also
        # had a "quiet for N seconds" threshold, which went dead once silence
        # started being polled rather than stamped -- so assert it stays gone
        # rather than lingering as a knob that tunes nothing.
        self.assertFalse(
            hasattr(sys.modules["engine.audio_manifest"],
                    "IDLE_AMBIENCE_AFTER"),
            "IDLE_AMBIENCE_AFTER no longer gates anything; silence is polled")
        self.assertGreater(AMBIENCE_COOLDOWN, 0)

        # The watcher lives on an overlay screen rather than the HUD, because
        # the HUD is hidden during cutscenes and conversation.
        with open(os.path.join(base_dir, "game", "screens.rpy"),
                  encoding="utf-8") as fh:
            screens = fh.read()
        self.assertIn("screen ambience_idle_watcher():", screens)
        self.assertIn("idle_ambience_tick", screens)
        self.assertIn('config.overlay_screens.append("ambience_idle_watcher")',
                      screens)

        # And it must not depend on renpy.get_time(), which does not exist in
        # this SDK -- that is what traceback.txt is a record of.
        self.assertNotIn("renpy.get_time()", script)


if __name__ == "__main__":
    unittest.main()
