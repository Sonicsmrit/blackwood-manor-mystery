# Return by Death Manor: Game Logic Spec

Handoff for Claude Code. Build the whole game from this document. Where it says "verify", check against the installed environment instead of trusting the spec.

Deadline context: Cambridge x Arcade AI Hackathon, Game Tech Track. Submission is a project link plus a demo video, due Sunday 14:00 BST. Build for reliability first. Scoring weights: Execution 25%, Track fit 25%, Innovation 20%, AI x Gaming 15%, Impact 10%, Demo 5%.

---

## 0. Rules for the builder

- Engine: Ren'Py 8.x (assets and the shader are Ren'Py-native). Game logic lives in plain Python modules under `game/engine/` with no `renpy` imports, except `llm.py` and `bridge.py`. This keeps logic testable with pytest.
- Code style: minimal, sleek comments. No frameworks, no abstract base classes, no over-engineering. Dataclasses and dicts are fine.
- The player never types free text. Every input is a button.
- Code owns the truth. The LLM only phrases things and picks among enumerated options. The game must be fully playable with the LLM disabled (`FALLBACK_ONLY`).
- Never hardcode an API key. Read `ANTHROPIC_API_KEY` from the environment or from a gitignored `game/secrets.json`. Model name from env `GAME_MODEL`, default `claude-haiku-4-5-20251001`.
- Verify before relying on: `renpy.fetch`, `renpy.invoke_in_thread`, `renpy.register_shader` availability in the installed Ren'Py version. If `renpy.fetch` is missing or blocked, use `urllib.request` inside a thread.

---

## 1. Concept

Mansion horror, time loop, deduction. The player (working name **Adrian**) wakes in a hospital with a brain injury and no memory. A girl, **Marika**, claims to be his girlfriend. He doesn't remember her. She takes him to the family mansion where his younger sister **Elise**, the butler **Hargrove**, the nurse **Vance**, and the maid **Odile** live. Elise says their parents died in a car crash and won't let Marika stay overnight.

One of the five is a hidden killer. Every night of Day 2 the killer comes for Adrian. He dies, wakes on the morning of Day 2, and keeps his memories (Return by Death). He has a revolver with one bullet. Shoot the killer before night and he survives. Shoot the wrong person and he still dies at night. After 3 resets the loop swallows him for good.

Per run, the killer and their agenda are random. An LLM "Director" picks the scenario from a validated menu. Everything else (schedules, clues, fairness) is code.

---

## 2. Cast

Five NPCs, data-driven (`roster.json`). Odile is a required cast member, not optional.

| id | Name | Role | Voice | Start trust | Base location (their belongings) |
|---|---|---|---|---|---|
| marika | Marika | Claimed girlfriend, evenings forced to the gate | Warm, intense, a little too familiar, hurt when doubted | 0 | gate |
| elise | Elise | Younger sister, grieving, protective, sharp | Clipped, formal, flashes of child-like need | 0 | upstairs |
| vance | Nurse Vance | Hired by Elise to keep Adrian calm and medicated | Brisk, professional, tired | 1 | upstairs |
| hargrove | Hargrove | Family butler, serves Adrian and Elise | Courteous, warm, old-fashioned | 2 | kitchen |
| odile | Odile | Long-serving housemaid, keeps the house running | Soft-spoken, deferential, notices everything, says little | 1 | parlor |

Player name is a config constant `PLAYER_NAME = "Adrian"`.

---

## 3. World model

### 3.1 Constants

```python
DAYS = [1, 2]
SLOTS = ["morning", "afternoon", "evening"]
LOCATIONS = ["parlor", "study", "kitchen", "upstairs", "gate"]
ACTIONS_PER_SLOT = 2
CONVO_MAX_TURNS = 5
MAX_STRAIN = 3
TRUST_MIN, TRUST_MAX = 0, 3
```

### 3.2 Time structure

- **Day 1** (played only in loop 1): 3 slots, free exploration, scripted bookends. Killer behaves normally. No shooting.
- **Day 2**: 3 slots, then night. Revolver available from the start of Day 2 morning (scripted beat).
- **Night 2**: if the killer is alive, Adrian dies. If the killer was shot, the game ends in victory.
- **Reset**: after death, wake at Day 2 morning. Loops 2 and 3 start at Day 2, so they have 6 actions each. Loop 1 has 12 (Day 1 plus Day 2).

### 3.3 Actions per slot

Each slot the player picks a location (free, one per slot), then spends up to 2 actions there:

- **Talk** to one character present (one conversation, up to 5 turns).
- **Search** the location (reveals findings, subject to the watching rule below).
- **Shoot** (Day 2 only). Target must be present at the current location. Confirmation dialog. Ends the day immediately.

When the evening slot ends without a shot, show a last-chance prompt: Hold fire or Shoot.

### 3.4 Positions

`positions[char][day][slot] -> location`, generated per run from the seed under these constraints:

- Every character appears at 2 or more distinct locations across the day.
- Marika is at `gate` in the evening on both days (Elise's rule), except where a killer or decoy deviation overrides it.
- Each character has a stated routine claim (section 5) that is true on Day 1.
- The killer and each decoy deviate from their stated routine at exactly one Day 2 slot (the deviation slot). Innocents with no decoy never deviate.

### 3.5 Backgrounds

Only one location art set exists (`ROOM1-4.png`, one parlor in four lighting variants). Locations are faked with tints:

| Location | Base | Treatment |
|---|---|---|
| parlor | ROOM1 | none |
| study | ROOM3 (warm) | slight darken, desk props (PROP files) |
| kitchen | ROOM2 (grey) | slight green tint |
| upstairs | ROOM4 (dark) | none |
| gate | ROOM4 | blue night tint plus blur |

Evening slot: add a dusk matrix tint on all locations. Use Ren'Py `matrixcolor`.

---

## 4. Run state

Generated once per run by `engine/generator.py`, stored in the `store` and never regenerated on reset.

```json
{
  "seed": 42,
  "killer": "hargrove",
  "agenda": "inheritance",
  "cause": "brakes_cut",
  "secrets": {"marika": "lingering", "elise": "night_visits", "vance": "phone_calls", "odile": "stolen_silver"},
  "start_trust": {"marika": 0, "elise": 0, "vance": 1, "hargrove": 2, "odile": 1},
  "positions": {"hargrove": {"1": {"morning": "kitchen", "afternoon": "parlor", "evening": "kitchen"},
                              "2": {"morning": "kitchen", "afternoon": "parlor", "evening": "study"}}},
  "facts": [],
  "fragment_order": ["smell", "sound", "sight"],
  "hook": "Something about this house is wrong, and it already knows you."
}
```

Everything else (facts, claims, findings) is derived from `killer`, `agenda`, `secrets`, and `positions` by deterministic functions.

---

## 5. Evidence system

Everything the player learns becomes a **Fact** and a Notebook entry. The notebook is written from fact IDs, never parsed from LLM text.

### 5.1 Fact schema

```json
{"id": "claim:hargrove:crash", "kind": "claim|finding|presence|fragment|world",
 "char": "hargrove", "topic": "crash", "text_key": "slip.brakes_cut",
 "gate": {"via": "talk|search|observe|death", "loc": null, "slot": null, "day": null, "min_trust": 2},
 "exclusive": true, "conflicts_with": ["world:official_report"]}
```

### 5.2 Topics

Every character has four topics: `routine`, `house`, `adrian` (who you were), `crash`.

| Topic | Min trust | Notes |
|---|---|---|
| routine | 0 | States where they spend a given slot. True on Day 1. |
| house | 1 | Harmless lore. Carries decoy secret hints. |
| adrian | 1 | Backstory fragments, Marika's version of the relationship. |
| crash | 2 (vague) / 2 (specific) | See below. |

### 5.3 Claims

- **Routine claim**: "I take tea in the kitchen every afternoon." True on Day 1. On Day 2 it is false for the killer and for any character with a decoy secret that deviates.
- **Crash claim, vague version** (min trust 2): innocents say something non-specific ("a terrible accident, I couldn't say how"). Every innocent uses this version. Never a specific cause.
- **Crash claim, slip version** (min trust 2): the killer states the specific cause tied to their agenda, casually, as if common knowledge (section 6). **Exclusive.**

Both crash versions open at the same trust. Offering to talk about the crash must not
identify the killer, so the two are gated identically — see 5.4.

### 5.4 How choices are offered

Each turn the conversation offers 4 intents: 1-2 `probe:<topic>`, plus `comfort`,
`press`, and `small_talk` (from turn 3, `leave` replaces one of them).

Probe topics are picked by **reachability**, never by exclusivity:

1. Topics already askable (some unlearned fact with `min_trust <= trust`).
2. Topics that just became askable (`min_trust == trust`) are always offered
   first, so a newly unlocked topic can't drift back out of reach.
3. Any remaining probe slot is filled from topics askable within one trust point.
4. If nothing is left to ask about, one probe is drawn from the full topic list.

Reachability reads only `min_trust`, and the `crash` gates are now identical for
every character, so the same probe topics are offered to everyone at the same trust.
The choice list therefore carries **no** information about who the killer is. An
earlier rule that preferred `exclusive` topics did: `probe:crash` appeared for the
killer on every turn and for nobody else, naming them before any deduction.

### 5.4 World facts

- `world:official_report` (Study, Search): the official crash report says the wreck has not been examined and cause is undetermined. Any specific cause stated by anyone conflicts with it.
- `world:hospital_letter` (Study, Search): your discharge letter, gives the date of the crash and the hospital's name. Anchors the timeline.

### 5.5 Presence facts

- Automatic. On entering a location in a slot, record everyone present.
- Absences are recorded when a routine claim names that location and slot and the character is not there.
- A deviation is a **conflict** between the routine claim and the observed absence.

### 5.6 Findings (Search)

Each character has items at their base location. Search at a location returns findings whose owner is **not present** there in that slot. If the owner is present: "You can't search with <name> watching." This forces use of presence knowledge.

- **Killer findings** (exclusive): depend on agenda (section 6).
- **Decoy findings** (non-exclusive): from the character's decoy secret (section 7).

### 5.7 Death fragments

Each death reveals one fragment pointing at the killer, in `fragment_order` (a seeded permutation of sound, smell, sight). Fragments are ambiguous by group: the **staff** (hargrove, vance, odile) share each category, and the **kin pair** (elise, marika) share each category. A fragment narrows the killer to a group, never to one person.

| Char | Sound | Smell | Sight |
|---|---|---|---|
| hargrove | a slow pocket-watch tick | starch and beeswax | a white cuff on a dark sleeve |
| vance | a wristwatch tick and squeaking soles | iodine and starched linen | a white cuff on a grey sleeve |
| elise | a lullaby hummed off-key | lavender soap | a ribbon trailing in the dark |
| marika | a hymn hummed, faintly bell-like | lavender and rain | long pale-gold hair falling across your face |
| odile | a jangle of keys | lemon polish and starch | a white lace cap in the dark |

Fragment display: black screen, 2 seconds, one line in italics ("You hear a slow tick."), then reset.

### 5.8 Contradiction engine

`find_conflicts(known_fact_ids, all_facts) -> list[(factA, factB)]` still models which pairs
of known facts cannot both be true:

- routine claim vs observed absence
- crash slip vs `world:official_report`

**It is not surfaced in the notebook, and must not be.** The notebook used to paint a
character card red and stamp it "CONTRADICTS THEMSELF" off these pairs, and that flag was
worthless: the generator gives *every* character exactly one deviation slot, killer and
innocent alike (`validator.py` V3 requires one per innocent, tied to their decoy secret). So
one empty room per person, for all five, and the red could fire on the entire cast at once.
It narrowed the field not at all and called an innocent a liar for running an errand.

`find_conflicts` remains engine API only. `test_17` asserts no `.rpy` screen calls it, so the
verdict cannot return through a new import.

A deviation is **not** evidence and is never recorded as a fact. The `presence:deviation:`
branch that used to sit in `conflicts.py` was dead — nothing ever wrote one — and it has been
removed rather than left to imply a deviation is something the notebook could catch.

#### 5.8.1 Showing evidence instead

Absence records are bare ID strings in `known_facts` with no `Fact` object behind them, since
`build_all_facts` emits only `world`/`claim`/`finding`/`fragment`. They therefore have no
`.text` and were previously rendered nowhere — the notebook displayed the verdict while
withholding the evidence. `bridge.py` now supplies the words:

| Helper | Purpose |
|---|---|
| `parse_presence_fact(id)` | `presence:{absence\|seen}:{char}:{loc}:{slot}:{day}` → parts, `None` if unparseable |
| `presence_absence_text(char, loc, slot, day)` | "The Study was empty. Elise said she would be there." |
| `presence_absence_text_for(id)` | same, keyed by fact ID |
| `evidence_label(kind)` | neutral heading for an Evidence card, keyed off `kind` alone |

The absence sentence reports only what Adrian walked into. It must not claim anyone lied: a
single empty room proves nothing, because everyone deviates once. The claim being measured
against is on that person's card in the People tab, and reading one against the other is the
player's job.

The Timeline tab renders absences as that sentence, alongside sightings, keyed off
`known_facts` rather than off the generator's position map. The old lookup reconstructed an
expected sighting key from `run_state.positions`, so a room the player entered that turned
out empty could never appear at all — the exact case the evidence exists to show.

---

## 6. Agendas

Three templates. Each fixes a cause, a slip, and a finding for the killer. Any character can be the killer under any agenda.

| Agenda | Cause id | Slip (what the killer lets drop on `crash`) | Killer finding (at their base location) | Motive |
|---|---|---|---|---|
| inheritance | brakes_cut | the brake lines were cut | a forged will naming the killer as heir of last resort | per-killer, see 6.1 |
| cover_up | drugged_driver | their father's drink was drugged before he drove | altered records and a hidden sedative vial | per-killer, see 6.1 |
| obsession | forced_off_road | another car ran them off the road | keepsakes: photos of Adrian, scratched out around other faces | per-killer, see 6.1 |

### 6.1 Motives are per (agenda, killer)

One motive per pair: 3 agendas × 5 characters = 15 entries. Any character can be
the killer under any agenda, so every pair is reachable and must be authored.

Invariant: **a killer's own display name never appears in their own motive.**
The `inheritance` motive used to be a single shared string, *"They profit if
Adrian and Elise die."* Because that text reaches the killer's own LLM prompt,
it made Elise — when she was the killer — believe she profited from her own
death. Motives are therefore keyed per character; `inheritance` gives Elise a
disinheritance framing that matches her `inheritance`/`elise` epilogue, and the
other four characters keep the original wording.

The LLM phrases the slip in the character's own voice but must contain the `slip_keywords` (validated, see section 10):

- brakes_cut: `["brake"]`
- drugged_driver: `["drink", "drug"]` (either one)
- forced_off_road: `["another car", "off the road", "ran them"]` (any one)

---

## 7. Decoy secrets

Each innocent receives one harmless secret. It produces a deviation at one slot, one non-exclusive finding, and optional flavor in their `house` claim.

| Char | Secret id | Deviation | Finding | Flavor |
|---|---|---|---|---|
| marika | lingering | sneaks back near the house at night, so evening claim is false | muddy footprints and a folded blanket by the gate | she hates leaving you alone |
| marika | unsent_letters | afternoon at the study, reading | letters to your parents she never sent | she knew them |
| elise | night_visits | checks your door at night, evening claim false | her slippers by your door, a note "is he breathing?" | she's terrified of losing you too |
| elise | diary | afternoon alone upstairs | a diary page about wanting to run away | she's overwhelmed |
| vance | phone_calls | evening on the upstairs landing on the phone | a call log to the same unknown number | she's lying to someone about the job |
| vance | skimming_pills | morning in the kitchen | empty sleeping-pill blister packs | she can't sleep either |
| hargrove | pawned_watch | afternoon at the gate meeting a pawnbroker | a pawn ticket for the family watch | money troubles |
| hargrove | drinking | evening in the kitchen when he claims to be elsewhere | a hidden bottle in the pantry | grief |
| odile | stolen_silver | afternoon in the parlor when she claims to be elsewhere | a silver spoon wrapped in her apron | she is sending money home |
| odile | eavesdropping | evening on the upstairs landing | a glass left against a door | she's afraid of losing her place |

Rule: a secret's finding never matches any killer finding's `exclusive` flag, and no innocent ever receives a `crash` slip.

---

## 8. Trust and dialogue mechanics

### 8.1 Trust

- Integer 0 to 3 per character, reset to `start_trust` at the start of every loop (NPCs forget).
- Persists across slots within a loop.
- **comfort**: +1 (capped).
- **press**: reveals a gated fact if `trust >= min_trust - 1`, then trust -1. At trust 0 with press: the character ends the conversation and refuses to talk again until the next slot (lockout).
- **probe:<topic>**: reveals the topic's fact(s) if `trust >= min_trust`, otherwise the character deflects gracefully and nothing is revealed.
- **small_talk**: no change.
- **leave**: ends the conversation.

### 8.2 Conversation loop

Up to `CONVO_MAX_TURNS` turns. Each turn:

1. Code chooses 4 **intent slots** (section 8.3).
2. Code decides what the NPC will reveal this turn from the previous pick (`reveal_now`).
3. LLM phrases the NPC line and the 4 choice texts.
4. Player picks one.
5. Code applies trust and reveal rules, logs facts, and loops. The conversation ends when the LLM returns `exit_code: "finished"`, the player picks `leave`, turns run out, or lockout triggers.

### 8.3 Choice intents

Exactly 4 per turn, chosen by code, shuffled by the seeded RNG:

- 1 or 2 `probe:<topic>` for topics where this character still has unrevealed facts the player has not yet learned in any loop. Include the highest-value one (an exclusive fact) when it exists.
- 1 `comfort`
- 1 `press` on the gated topic if one exists and trust is below the gate, else `small_talk`
- Always include `leave` from turn 3 onward, replacing `small_talk` if needed.

At least one choice in each of the first 3 turns must be a probe on a not-yet-revealed topic, so conversations never dead-end. The LLM writes the text; code overwrites any intent the LLM tries to change.

---

## 9. Shooting, death, strain, endings

### 9.1 Shoot

- Day 2 only. Target must be present at the current location.
- **Target is the killer** → victory, jump to the ending.
- **Target is innocent** → the target is removed from the rest of the day, the bullet is spent, `wrong_kill = True`. The burial round begins (section 13.2.2).
- The revolver is available in **any** Day 2 slot, including a daytime one. The knife remains night-only. Both wrong kills set `wrong_kill_weapon` to `"revolver"` or `"knife"` and route to the shared `wrong_kill_coverup` → `after_hours` label.

### 9.1a The clock is not moved by a killing

A killing does **not** set `current_slot` to `"evening"` or to a night value. The engine models exactly three slots (`engine/constants.py: SLOTS`), and adding a fourth would `KeyError` in `routine_claims`, the position map, the validator and the solver.

Two separate flags carry the distinction:

| Flag | Meaning | Set by |
|---|---|---|
| `night_sequence` | the genuine midnight menu | `day2_night_transition` → `True`; `day2_morning_transition` → `False` |
| `after_hours_active` | the burial reward round is running | `after_hours` |

`night_sequence` exists because a daytime revolver kill can occur while `current_slot == "evening"` — indistinguishable from the midnight slot by value alone. It is the flag, not the slot, that decides whether the HUD reads `Night`, whether the burial art is `_night`, and whether the survivors talk about the small hours.

Both flags are cleared by `reset_loop` alongside `revolver_found` and `knife_found`.

After the burial round the flow is unchanged: `advance_slot` sees `after_hours_active` and jumps straight to `night_death`, so a daytime killing still ends with Adrian dying that night.

### 9.2 Night

If the killer is alive, Adrian dies. Death sequence:

1. Cut to black, play the next death fragment (section 5.7).
2. Increment strain by 1 (and by 2 total if `wrong_kill`).
3. If strain > MAX_STRAIN → permanent loss ("swallowed").
4. Else reset.

### 9.3 Reset (`reset_loop()`)

**Kept**: notebook, all known facts, `strain`, `loop_no`, `fragments_seen`, run state.
**Reset**: day to 2, slot to morning, trust to `start_trust`, bullet restored, `wrong_kill` cleared, all NPC states. Increase `loop_no`.

### 9.4 Strain (the arm)

| Strain | HUD | Shader on scene and sprites |
|---|---|---|
| 0 | arm intact | none |
| 1 | hairline cracks | `chromatic_2` |
| 2 | wider cracks | `chromatic_5` |
| 3 | deep cracks, tremor | `chromatic_9` |

Death flash: `chromatic_10` for 0.4 seconds with a screen shake. HUD shows an arm indicator or 3 pips, plus loop number and a bullet icon.

### 9.5 Endings

- **VICTORY**: the killer shot. Epilogue: the killer's confession from the agenda motive in the killer's voice, one line per remaining character, a final line that Adrian remembers one true thing about Marika. Epilogue text is LLM-phrased from `{killer, agenda, cause, motive}` with an authored fallback.
- **SWALLOWED**: strain exceeded. Fade to white with maximum chromatic, one line.
- **No timeout ending**: the loop continues until victory or swallowing.

---

## 10. LLM integration

### 10.1 Modes

```
LLM_MODE = "live" | "cached" | "fallback"
```

- `live`: call the API, cache each response to `game/cache/<hash>.json`.
- `cached`: only read from cache; on miss use fallback.
- `fallback`: never call the API. Uses `fallback.json`.

Default: `fallback` unless `ANTHROPIC_API_KEY` is present. Add `--record` behavior: in `live`, write every response so a full run can later be replayed in `cached` mode (for the demo video).

### 10.2 Director call (run start)

Input: roster, agendas table, secrets table, `previous_killer` (from `persistent`), run seed.

System prompt:

```
You are the story director of a gothic mystery game. Choose the scenario for this run
from the options provided. Never invent options. Reply with JSON only.
Rules: the killer must differ from previous_killer. Assign exactly one secret_id to each
innocent character, chosen from that character's listed secret ids. hook is one sentence,
max 140 characters, in second person, no names, no spoilers.
Schema: {"killer": id, "agenda": id, "secrets": {char_id: secret_id, ...}, "hook": string}
```

Validate with `validate_run` (section 11). Retry up to 2 times. Then fall back to deterministic seeded RNG. Everything else about the run (cause, positions, facts, fragment order) is derived by code.

### 10.3 Dialogue call (per turn)

System prompt (per character, filled from `roster.json`):

```
You voice {name} in a gothic horror visual novel. Persona: {persona}.
Speak only as {name}. Reply with JSON only.

Input fields:
- scene: location, slot, who else is present
- history: last 4 exchanges
- reveal_now: facts you must convey this turn, in your own voice and your own words.
  If empty, say nothing of consequence about the case.
- guarded: topics you deflect gracefully. Do not invent specifics about them.
- forbidden: words you never say.
- mood_hint
- choices_spec: 4 intents for the player's replies

Rules:
- npc_line: 1 to 3 sentences, max 280 characters.
- If reveal_now includes a specific cause, mention it casually as if it were common
  knowledge. Never hint that it is significant.
- Never mention AI, loops, the game, or anything outside the provided facts.
- choices: the player is Adrian, an amnesiac, cautious and polite. One choice per
  entry in choices_spec, in order, max 110 characters each, matching the intent:
  probe:<topic> asks about that topic naturally, comfort is empathetic, press is blunt,
  small_talk is neutral, leave ends politely.
- exit_code: "finished" if the conversation has naturally concluded, else null.

Schema: {"npc_line": str, "mood": "neutral|calm|angry|sly|sad|tearful|shy|apologetic|creepy",
         "choices": [{"intent": str, "text": str}, x4], "exit_code": null|"finished"}
```

Important: **the killer's persona prompt never states they are the killer.** Every character's prompt has the same shape: a `guarded` list and a `reveal_now` list. Only the killer's `reveal_now` ever contains the slip. This makes leakage structurally impossible: innocents are never told who the killer is.

### 10.4 Output validation

On every response:

1. Valid JSON, schema keys present.
2. Exactly 4 choices. Overwrite each `intent` with `choices_spec[i]`.
3. `npc_line` ≤ 280 characters, each choice text ≤ 110.
4. If `reveal_now` is non-empty, `npc_line` contains at least one `slip_keywords` token (or the fact's `must_include` list). If not, regenerate once, then use the authored fallback line for that fact.
5. `npc_line` contains none of `forbidden`.
6. Innocents' lines never contain any slip keyword, and nobody uses words like "killer" or "murderer" unless the fact text does.

Any failure after one retry uses the fallback for that character, topic, and trust band.

### 10.5 Fallback content

`fallback.json`, authored once, keyed by `(char, topic, variant)`. Three variants per entry. Also:

- 3 variants of player choice text per intent.
- One authored line per revealable fact (the exact content of `reveal_now`).
- Generic deflection lines per character.

Claude Code should generate this file from the persona table and fact texts, then keep it small. The fallback path must play a complete run end to end.

### 10.6 Ren'Py bridge

- API calls run in a thread (`renpy.invoke_in_thread`) with a 12 second timeout. During the wait, show an animated "..." indicator by polling in a loop with `renpy.pause(0.1)`.
- On timeout or exception, use the fallback immediately.
- Disable rollback during runs (`config.rollback_enabled = False`) so rollback can't desync run state.
- Saving and loading is allowed. All run state must live in `store` variables (serializable dicts and dataclasses with plain fields).

---

## 11. Generator and fairness validator

### 11.1 `generate_run(seed, director=None)`

1. Get `{killer, agenda, secrets, hook}` from the Director, or from the seeded RNG as fallback.
2. Run `validate_choice` on the Director output (valid ids, killer != previous, one secret per innocent from that character's list).
3. Build `positions` with constraints (section 3.4).
4. Derive facts: killer facts (slip, finding, deviation), decoy facts, world facts, routine claims, fragments.
5. Run `validate_run`. On failure, re-roll positions with a new sub-seed, up to 20 tries, then raise.

### 11.2 `validate_run(state) -> list[str]` (empty list means valid)

- **V1**: exactly one killer, drawn from the roster.
- **V2**: the killer has all three evidence kinds: slip (exclusive), presence conflict, finding (exclusive).
- **V3**: every innocent has exactly one decoy secret, producing a deviation and a finding.
- **V4**: no innocent holds an exclusive fact. No innocent states a specific cause.
- **V5**: every fact's gate is reachable: the required character is at the required location in the required slot (for talk and observe gates), and search gates have a slot where the owner is absent while another action is available.
- **V6**: the killer's exclusive facts are discoverable using only loops 1 and 2 (see solver).
- **V7**: fragments are assigned one per category with the group-sharing rule satisfied (staff group of three, kin pair).
- **V8**: every `slip_keywords` check passes against the authored fallback line.

### 11.3 `solve(state)`

Plan search with perfect knowledge:

- Budget: loop 1 = 12 actions, loop 2 = 6 actions.
- Trust: a conversation reaches `trust >= 2` for the slip only if `start_trust + comfort_picks >= 2` within `CONVO_MAX_TURNS - 1` turns, remaining one turn for the probe.
- Success: the plan collects the slip plus at least one of (finding, presence conflict) within loops 1 and 2.
- Returns the shortest plan and its loop count.

Use brute force over `(slot, location, action)`. State space is tiny.

### 11.4 Required tests (pytest, run outside Ren'Py)

1. 10,000 seeds: `validate_run` returns `[]` for every generated run.
2. Every killer x agenda x secrets combination solvable in at most 2 loops.
3. No innocent ever holds an exclusive fact.
4. `reset_loop()` preserves exactly the kept state and resets exactly the reset state.
5. Fallback mode plays a full simulated run, including shooting the killer, without an exception.
6. Validator rejects an LLM response containing a slip keyword from an innocent.

---

## 12. Notebook UI

Tabs: **Characters**, **Timeline**, **Findings**, **Deaths**.

- **Characters**: one card per character, their trust note (current loop), and every claim you have heard from them. Uniform styling — no card is coloured or badged.
- **Timeline**: Day 1 and Day 2 slots as rows. Each slot lists who you saw and where, plus any room you entered that turned out empty (`presence_absence_text`).
- **Findings**: item list with icon (use `PROP*` images, assigned after the asset audit).
- **Deaths**: one entry per death showing the fragment and the loop.

Rules: never show a suspicion percentage, a ranking, or a per-character marker of guilt. The
notebook supplies claims and observations; the player draws the conclusion.

**Never render a raw `Fact.id` or `Fact.text_key`.** The id is `finding:{char}:...` and the
killer's own finding carries `text_key` `finding.killer.obsession` — either one names the
murderer outright, even in a muted colour. Evidence cards are headed by `evidence_label(kind)`
("A document", "Something left behind") and tinted uniformly. `test_17` guards all of this.

---

## 13. Screens and flow

### 13.1 Screens

`hud`, `location_picker` (5 buttons plus who is present on each, shown after first visit), `conversation` (portrait, textbox UI, namebox, 4 choice buttons, thinking indicator), `notebook`, `shoot_confirm`, `death`, `ending`, `credits`, `title`.

### 13.2 Flow

```
title → director (loading) → day1_intro (scripted) → day1_slots → day1_night (safe)
→ day2_morning (revolver beat) → day2_slots → last_chance
→ [shot killer] ending_victory
→ [else] night_death → fragment → strain check → [swallowed] ending_swallowed | reset → day2_morning
```

#### 13.2.1 Time of day in the HUD

`SLOTS` is exactly `["morning", "afternoon", "evening"]` and **no night slot exists**.
`advance_slot` leaves `current_slot == "evening"` when it routes into the night, so the
HUD cannot derive "Night" from the slot.

The display therefore goes through `time_of_day_label(slot, at_night)` in
`engine/state.py`, wrapped by `get_time_display()` in `script.rpy` for the HUD's top-left
label. The flag is `night_sequence`, **not** `after_hours_active`: the revolver is available
in any slot, so a daytime killing opens the same burial round and must keep reporting its
real hour.

| `night_sequence` | label |
| --- | --- |
| `False` | `slot.capitalize()` (`Morning` / `Afternoon` / `Evening`) |
| `True` | `Night` |

Do **not** add a fourth slot to `SLOTS` to fix this. `routine_claims` is keyed by slot in
four places (`generator.py`, `validator.py`, `solver.py`, and inline in `script.rpy`)
and a night slot raises `KeyError` there, makes `get_bg_image_name` fall through to daytime
art, and breaks the fairness validator. The display layer is the only correct place.

Background art follows the same flag via `get_scene_bg(loc, slot, at_night)`, which returns
`bg <loc>_night` when `at_night`, `bg <loc>_evening` in the evening slot, else `bg <loc>`.
`after_hours` pins `current_location` to the parlor, and the player cannot travel during
after-hours (actions are talk / search / shoot / pass only), so only the parlor and gate
backgrounds are reachable there. `test_14` asserts every case resolves to a declared `image`.

#### 13.2.2 The burial round (wrong kill, both weapons)

Both weapons route to one label. `execute_shot` and `execute_stab` each record
`wrong_kill_weapon` and, on a wrong kill, jump to `wrong_kill_coverup` → `after_hours`.

| | `night_sequence` | Survivor reaction | Surrenders | Buried |
| --- | --- | --- | --- | --- |
| Knife | `True` (night menu only) | nothing heard | knife | knife |
| Revolver | either | shot heard outside | revolver | revolver |

The revolver's report is the only difference in reach; the burial, the trust, the round and
the `night_death` handoff are shared.

`build_conversation_context` threads `wrong_kill`, `after_hours`, `at_night`, `weapon` and
`killed_name` into `scene_desc`. When `night_sequence` is set, `scene_desc["slot"]` is
reported to the LLM as `"night"`; otherwise the real slot is reported, so an afternoon
burial is never described as midnight.

`llm.burial_guilt_pressure(name, killed_name, at_night)` then injects a
`=== TONIGHT, AND WHAT YOU DID TOGETHER ===` or `=== TODAY, AND WHAT YOU DID TOGETHER ===`
block. The `at_night` branch controls the hour framing ("the small hours" vs. "middle of
the day, the curtains are still open") and the `why everyone is still awake` detail.
Voice rules:

- The survivors dug the grave and are covering for Adrian. They **know** he did it.
- They are **bound** to him, not loyal to him — that is permanent and worse.
- Frightened and exhausted; composure from dinner is gone; guilt said once, then dropped.
- More forthcoming, because guilt is the only lever left on someone already implicated.
  This coexists with the `+1` trust `after_hours` grants (`script.rpy`): guilt opens them
  up *and* destabilises them, and both must be stated or the tone reads as one or the other.
- Never mention repeating, undoing or reliving what happened. The night-only wording was
  widened to "what happened" so the closing line does not contradict a daylight burial.

**Hard constraint:** this block must stay free of `FORBIDDEN_WORDS`. Validation runs
`_forbidden_hit` over every generated line, so seeding `loop` or `reset` into the
instructions does not fail a test — it makes the model echo the word, and then every reply
is rejected and the game silently falls back to canned lines. `test_11` guards this, across
both `at_night` values.

### 13.3 Scripted scenes (Day 1)

Keep each short, authored directly in Ren'Py script, 4 to 10 lines:

1. **Hospital wake**: bandaged, no memory, Marika at the bedside. "I don't remember having a girlfriend."
2. **The drive**: Marika explains; Adrian is cautious.
3. **Arrival**: Elise confronts Marika at the door. Gate by sunset.
4. **Vance**: first pills, the rules.
5. **Hargrove**: tour of the house, warm.
6. **Odile**: tea in the parlor, turns down the bed, avoids eye contact.
7. **Night 1**: quiet. One line of unease.

Day 2 morning beat: Adrian finds his father's revolver with one bullet in the nightstand.

---

## 14. Sprites, assets, UI

### 14.1 Asset audit (do this first)

Write `tools/audit_assets.py` that lists and previews every file in the packs and builds `assets/manifest.json`. Verified from preview so far:

- Horror pack characters have clean sprites `*_FULL1` and bloodied sprites `*_FULL3`: MAID, NURSE, GIRL, BUTLER. Other FULL numbers are unverified: inspect.
- Face files (`*_FACE#.png`) are unverified as overlays. Check image sizes and, if needed, the `ASSET PACK.psd` layer offsets with `psd-tools`. If overlay offsets can't be recovered reliably, **skip faces** and use FULL sprites only.
- `ROOM1-4` are 1635x1080 variants of one parlor. `textbox UI 1-8`, `namebox`, and `PROP1-17` are unverified: view and assign.
- Marika (4 outfit packs, 9 expressions each): `base, angry, creepy, cry, okay, sad, shy, smirk, sorry`. Sprite size 832x1280.
- Excluded: Aiko (different art style), Sutemo PSD (unopened).

### 14.2 Sprite mapping

| Char | Clean | Bloodied (death scene, reveal) |
|---|---|---|
| elise | GIRL_FULL1 | GIRL_FULL3 |
| vance | NURSE_FULL1 | NURSE_FULL3 |
| hargrove | BUTLER_FULL1 | BUTLER_FULL3 |
| odile | MAID_FULL1 | MAID_FULL3 |
| marika | by mood (below), outfit per day | none (use `creepy` at reveal) |

Marika mood map: neutral→base, calm→okay, angry→angry, sly→smirk, sad→sad, tearful→cry, shy→shy, apologetic→sorry, creepy→creepy.

Marika outfits: Day 1 black dress. Day 2 and later rotate seeded among red, purple, blue shirt. This is cosmetic, not a clue.

For other characters the `mood` field is displayed only as a subtle sprite effect (small nudge or tint), since faces are unlikely to be usable.

### 14.3 Shader

Include `11_shader_chromatic-aberration.rpy` unmodified. It provides `chromatic_1` to `chromatic_10`. Apply to the scene and sprite layers by strain level (section 9.4). The license requires crediting GRIMUMU.

### 14.4 Credits

`CREDITS.md` and an in-game credits screen: GRIMUMU (shader, required). Check the original download pages for the horror pack and Marika packs and add the authors and license terms there. No license file shipped with those zips.

### 14.5 Audio

31 curated tracks ship from four `shdemo-*.zip` archives that sat at the project root and are gitignored. They were auditioned through `tools/extract_audio.py`, which extracts the archives to the gitignored `audio_inbox/` and builds a contact sheet; the picks are copied into the repo under semantic names, so the manifest records intent rather than archive ids.

`game/engine/audio_manifest.py` holds `MUSIC`, `AMBIENCE`, `AMBIENT_POOL` and `LEGACY_SFX`. It is a `.py` rather than a `.rpy` so tests can assert against it without booting Ren'Py, the same reasoning as `bridge.py`.

Channels: `music` (beds, 0.55), `ambience` (wind and the silence pool, 0.35), `stinger` (one-shots, 1.0), alongside the existing `voice_sfx`. Music sits well below the voice blips deliberately — those play on every dialogue line, so a louder bed would fight the text.

Scene map:

| Scene | Key |
|---|---|
| main menu | `title`, alternating with `title_alt` once per launch |
| day1_intro, day1_evening_bond | `atmos_low`, `evening_final` |
| day_slot_start | `kitchen` in the kitchen (`kitchen_alt` from loop 2 on), `night` at night, else `atmos_general` |
| evening → evening slot | `evening_final` on Day 2, else `atmos_general` |
| day1_night_transition | `night` + looping `storm_wind` |
| day2_morning_transition, loop reset | `clock` |
| day2_night_transition | `atmos_low`, `suspense` when aiming |
| wrong_kill_coverup | `wrong` sting, then `death_atmos` |
| after_hours | `body_thud`, `atmos_general` |
| night_death | `death`, `return_by_death`, silence over the flash, then `strain3` once at max strain |
| loop_confession_attempt | `atmos_short`, then `death` |
| ending_victory / ending_swallowed | `ending` / `game_over`, then `clock` |

The eight original synthesized effects stay in place; nothing in the curated set is unambiguously better for a UI click.

**Silence pool.** Six interchangeable atmospheric tracks play at random when the house is quiet, with `AMBIENCE_COOLDOWN` between them. Driven by a `timer` on the `ambience_idle_watcher` overlay screen rather than the HUD, because the HUD is hidden during cutscenes and conversation — where the silence lands. Both constants and all volumes are tunable at the top of the manifest.

Silence is **polled, not stamped**. `audio_is_silent()` asks `renpy.music.get_playing()` about the `sfx`, `voice_sfx`, `stinger` and `ambience` channels, because the 29 original `play sound` statements are scattered through the labels and the voice blip is triggered from screen code — neither passes through an audio helper, so no stamp would ever see them. `music` is excluded from that list on purpose: a bed is meant to be playing whenever the player is in a scene, so counting it would mean the pool never fires at all. The ambience channel is *not* excluded: `storm_wind` is 26 seconds of weather the scene asked for, and since the pool shares its channel, treating a loop as "background, therefore silence" would let the next tick cut the storm dead. The `time.monotonic()` clock is only used for the cooldown; the SDK's own time accessor is absent in this build, which is what `traceback.txt` records.

The watcher's state lives in a dict rather than two module globals. Assigning to a bare global from inside a function makes it local, so the first version of these helpers raised `UnboundLocalError` on the very first `set_music()` call — a failure invisible to lint, to the file-existence tests, and to anything short of running the game.

**Piano accent.** `piano` is the one curated hit with no scene: a 4s phrase meant to surface anywhere. It rides the `stinger` channel at `PIANO_ACCENT_VOLUME` relative volume, so it layers over a bed instead of replacing it, and is rolled once per idle tick against `PIANO_ACCENT_CHANCE` — a per-second probability of 1/250, putting the expected gap between phrases at a bit over four minutes. Because it lands on an audible channel, a winning roll makes the house non-silent and the pool stands down for that tick; two layers at once would read as a cue rather than as the house settling.

The source tracks were not cut for looping, so a bed that outlasts its scene may seam where it repeats.

### 14.6 Testing the parser, not just the intent

Every test above runs outside Ren'Py, which is the point — and also the trap. Three separate build-breaking errors have passed this suite: a dedented `return` (`2cbbf11`), 39 bare `set_music(...)` calls sitting in Ren'Py statement position instead of `$ set_music(...)` (`d11bab3`), and the `UnboundLocalError` above. None was visible to a test that only checked wiring.

So the suite now ends with three that do:

- the audio helpers are sliced out of `script.rpy` and executed against a stub Ren'Py, so "does this raise when called" and "does silence mean what it claims" are real assertions rather than grep hits;
- `renpy.sh . lint` runs against the project, and any `File "game/....rpy", line N:` in its output fails the test. It skips when no SDK is found, so a bare checkout still runs;
- a narrow structural check that no audio call sits in a label without its `$`, tracking `python:` block state so the legal in-block form is not flagged.

Every one of those guards has been mutation-tested: reintroduce the original bug, confirm the right test fails.

---

## 15. Content to author

### 15.1 Personas (feed `roster.json`)

- **marika**: "Marika. Warm, intense, hurt when doubted. Says she has been with Adrian for two years. Never explains how she knew about the crash. Speaks in short, tender sentences."
- **elise**: "Elise, Adrian's younger sister. Formal, clipped, protective, occasionally childlike. Distrusts Marika. Lost her parents recently."
- **vance**: "Nurse Vance. Brisk, professional, tired. Hired by Elise to keep Adrian medicated and calm. Avoids opinions about the family."
- **odile**: "Odile, the housemaid. Soft-spoken, deferential, observant, says less than she knows. Calls Adrian 'sir'. Anxious about keeping her place."
- **hargrove**: "Hargrove, the family butler. Courteous, warm, old-fashioned. Has served the family for decades. Calls Adrian 'young master'."

### 15.2 Authored lines checklist

- Topic lines per character for each trust band (fallback.json).
- One reveal line per fact.
- Death fragment lines (section 5.7), as written.
- Epilogues for 3 agendas x 5 killers (15 short fallbacks), generated by Claude Code from the agenda motive table and the persona, around 40 words each.

---

## 16. Build order

1. **Engine** (`generator`, `validator`, `solver`, `state`, `facts`, `conflicts`). Pytest suite from section 11.4 passing. Runnable CLI that plays a full run in text mode using fallback lines.
2. **Fallback content** (`fallback.json`, `roster.json`).
3. **Ren'Py skeleton**: screens, flow, scripted Day 1, fallback dialogue playing end to end.
4. **LLM layer**: Director and Dialogue calls, cache, record and replay, validation, threading.
5. **Visuals**: sprites, tinted locations, shader tied to strain, arm HUD, death and reset effects, notebook polish.
6. **Packaging**: desktop build (Windows and Linux), `README.md`, `CREDITS.md`, `--record` of one full demo run.

Cut list, in order, if time runs short: notebook Timeline tab, location tints, Director call (use seeded RNG), shader effects on sprites, epilogue LLM phrasing.

---

## 17. Submission notes

- Submit a project link (repository or itch.io page) plus a demo video of a full recorded run.
- Demo video should show: the Director choosing a scenario, a conversation with LLM-generated choices, the notebook lighting up a contradiction, a death and fragment, a reset with the shader glitch, and the final shot.
- Judges may not have API access. The build must run in `fallback` or `cached` mode by default. Never ship a key.
- Track-fit pitch (Game Tech Track): "An LLM story director that generates a different solvable mystery each run, with a deterministic validator guaranteeing fairness and a constrained dialogue engine that can't leak or contradict the truth."

---

## 18. Definition of done

- Fallback mode plays a complete run: loops, deaths, fragments, shot, ending.
- Live mode plays the same run with LLM-written lines and choices.
- 10,000-seed validation passes.
- Notebook presents claims and observations without grading them; the player identifies the killer.
- The killer and agenda differ across runs, and the loop count to solve is 1 to 3 for a careful player.
- Demo video recorded.
