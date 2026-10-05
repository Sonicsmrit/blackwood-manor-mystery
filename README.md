# Blackwood Manor Mystery

> **Cambridge x Arcade AI Hackathon — Game Tech Track**
>
> *Five suspects. One killer. One bullet. Infinite deaths.*
>
> `(・・;)ゞ`

---

## The Mystery

You wake up in a hospital bed with **cranial trauma and no memories**.

A young woman named **Marika** tells you she's your girlfriend and takes you to your family's secluded mountain estate: **Blackwood Manor**.

Inside, you meet four other people:

* **Marika** — the woman who claims to be your girlfriend
* **Elise** — your sharp younger sister
* **Nurse Vance** — the family's hired nurse
* **Hargrove** — the manor's longtime butler
* **Odile** — the housemaid

One of them is a **cold-blooded killer**.

Every night, the killer strikes.

You die.

Then you wake up again.

But this time, **you remember everything.**

`(；一_一)`

---

## Return by Death

Blackwood Manor is built around a simple idea:

> **The world resets. Your memories don't.**

When you die, you return to the morning of Day 2 with:

* Your memories
* Your notebook
* Discovered facts
* Evidence
* Fragments from previous deaths

But everything else resets.

The characters return to their routines.

Conversations happen again.

People forget what happened.

You don't.

And waiting inside your bedside drawer is your late father's revolver.

**One bullet.**

That's it.

`(╥﹏╥)`

Use it carefully.

---

# Investigate. Remember. Die. Repeat.

You aren't given a list of suspects with a big red arrow pointing at the murderer.

You have to figure it out yourself.

### Observe

Watch where people go.

Pay attention to their routines.

Notice when someone is somewhere they shouldn't be.

A room being empty can be just as important as finding someone inside it.

### Interrogate

Talk to everyone.

Ask questions.

Compare their answers.

Look for contradictions.

But don't expect the characters to magically know things they shouldn't.

### Build Your Timeline

Every interaction can become evidence.

Your notebook records what you've discovered so you can compare events across loops.

Who was where?

Who said what?

Who disappeared?

What changed?

### Remember Your Deaths

Death isn't simply a game over.

Sometimes, dying gives you information.

You may remember a sound.

A location.

A face.

A final conversation.

A detail you couldn't have known while you were alive.

`(ಠ_ಠ)`

### Make Your Choice

Eventually, you'll have to decide who the killer is.

You have one bullet.

Shoot the right person.

Break the loop.

Shoot the wrong person...

`[ THE LOOP CONTINUES ]`

---

# The AI

The characters in Blackwood Manor aren't simply running through a giant collection of pre-written dialogue.

The game uses a **constraint-bound LLM dialogue system** to generate contextual conversations and player choices.

The AI Director considers:

* The character speaking
* What that character knows
* What the player knows
* What has happened during the current loop
* Previously discovered evidence
* The current location
* The current game state

This allows conversations to react to what the player has actually discovered.

## No Knowledge Leakage

One of the biggest problems with AI-powered mystery games is that an LLM can accidentally ruin its own mystery.

Blackwood Manor actively constrains character knowledge.

A character shouldn't suddenly say:

> "I saw you die in the basement yesterday."

when, from their perspective, yesterday never happened.

The AI has to stay inside the character's knowledge boundary.

The mystery remains a mystery.

`(￣ー￣)`

---

# The Mystery Engine

The core game logic lives independently from the Ren'Py presentation layer.

```text
                     BLACKWOOD MANOR
                           |
             +-------------+-------------+
             |                           |
             v                           v
       Ren'Py Game                 Core Engine
       Presentation                game/engine/
             |                           |
             |                 +---------+---------+
             |                 |         |         |
             |                 v         v         v
             |              State    Evidence   Fairness
             |                 |         |         |
             |                 +---------+---------+
             |                           |
             +-------------+-------------+
                           |
                           v
                     AI Director
```

This makes the mystery engine testable without launching the visual novel.

---

# Deterministic Fairness Engine

Located in:

```text
game/engine/
```

The mystery shouldn't be difficult because the game randomly decided to hide the only useful clue.

The engine includes an automated **solvability and fairness validator** that generates mystery runs and verifies that they can be solved within **1–2 loops**.

### The engine handles

* Deterministic mystery generation
* Character presence tracking
* Contradiction tracking
* Evidence generation
* Timeline construction
* Loop state management
* Death fragments
* Notebook persistence
* Solvability validation

The notebook doesn't simply announce:

```text
KILLER: HARGROVE
```

Instead, it gives you observations.

**You have to connect them.**

`(ง'̀-'́)ง`

---

# Return by Death State

`game/engine/state.py`

When the player dies, the game separates what should reset from what should persist.

```text
                         DEATH
                           |
              +------------+------------+
              |                         |
              v                         v
        RESET THE WORLD             KEEP KNOWLEDGE
              |                         |
        - Day state                - Notebook
        - Actions                  - Discovered facts
        - Trust                    - Evidence
        - Character state          - Death fragments
              |                         |
              +------------+------------+
                           |
                           v
                       DAY 2 AGAIN
```

The world forgets.

**You don't.**

---

# AI Director

Located in:

```text
game/llm.py
```

## Constraint-Bound Dialogue

The LLM generates contextual dialogue and player choices while respecting the game's state and each character's knowledge.

## Offline Fallback

No API key?

The game still works.

A complete fallback dialogue system is included at:

```text
game/fallback.json
```

The game can therefore be played **100% offline**.

## Optional Live AI

To enable live AI dialogue:

```text
game/secrets.example.json
        |
        v
game/secrets.json
```

The game supports:

* Google Gemini
* Groq
* Anthropic

`secrets.json` is gitignored.

Please don't commit your API keys.

`(￣▽￣;)`

---

# The Notebook

The notebook is the player's central investigation tool.

It contains four sections:

```text
+--------------------------------+
|          NOTEBOOK              |
+--------------------------------+
|                                |
|  Characters                    |
|  Timeline                      |
|  Findings                      |
|  Deaths                        |
|                                |
+--------------------------------+
```

### Characters

Keep track of the people living inside Blackwood Manor.

### Timeline

Reconstruct the events of each day.

### Findings

Record observations, contradictions, and evidence.

### Deaths

Remember fragments from previous loops.

The notebook doesn't solve the mystery.

It gives you the information needed to solve it.

---

# Visual System

Blackwood Manor uses a gothic visual style with atmospheric backgrounds, character expressions, and a dynamic chromatic-aberration effect.

## Dynamic Strain Shader

```text
11_shader_chromatic-aberration.rpy
```

The chromatic aberration effect scales with the player's **loop strain**.

The more the player repeats the loop, the more unstable the world becomes.

Because apparently dying over and over wasn't stressful enough.

`(ノಠ益ಠ)ノ彡┻━┻`

---

# Audio System

Located in:

```text
game/engine/audio_manifest.py
```

The game contains:

* 31 curated tracks
* 14 scenes with dedicated audio
* Title music
* Day and night ambience
* Kitchen ambience
* Storm sequences
* Burial sequence
* Both endings
* Dynamic silence-triggered ambience

Six interchangeable ambient tracks can play whenever the game would otherwise become silent, keeping the atmosphere alive between dialogue.

The system detects silence by polling the actual audio channels rather than relying on timestamps.

Audio assets are prepared using:

```text
tools/extract_audio.py
```

The tool extracts source archives into a gitignored `audio_inbox/` and generates a contact sheet for auditioning.

---

# Screenshots

## Start Menu

<img width="1896" height="1034" alt="Blackwood Manor start menu" src="https://github.com/user-attachments/assets/58b1de80-6939-4604-853e-f1dc607389ed" />

## Intro Sequence

<img width="1892" height="1024" alt="Blackwood Manor intro sequence" src="https://github.com/user-attachments/assets/c3e6e63d-e599-4ce7-815b-e00ea2876762" />

## Day 1

<img width="1898" height="1021" alt="Blackwood Manor Day 1" src="https://github.com/user-attachments/assets/837d765b-f53f-4698-8502-f700c890cfbd" />

## Dialogue

<img width="1915" height="1022" alt="Blackwood Manor dialogue" src="https://github.com/user-attachments/assets/f58bce8d-01a2-44d8-9bbd-9a5b6378da06" />

## Notebook

<img width="1872" height="1007" alt="Blackwood Manor notebook" src="https://github.com/user-attachments/assets/2e226b5a-d6dd-4bb0-8871-6545a760024b" />

## Death / Loop

<img width="1653" height="885" alt="Blackwood Manor death screen" src="https://github.com/user-attachments/assets/91090bc6-c5a6-49c2-bc93-ab4313fc4254" />

---

# Running the Game

## Option 1 — Ren'Py

Download the [Ren'Py SDK](https://www.renpy.org/latest/html/).

Then launch the project:

```bash
/path/to/renpy-8.x.x-sdk/renpy.sh .
```

---

## Option 2 — Headless Simulation

The mystery engine can run independently of the visual novel:

```bash
python3 game/engine/cli.py --verbose
```

This allows mystery runs to be played or simulated directly from the terminal.

---

## Option 3 — Test Suite

Run the automated engine tests:

```bash
python3 -m unittest tests/test_engine.py
```

The tests verify:

* Mystery generation
* Deterministic seeds
* State persistence
* Loop behaviour
* Evidence generation
* Fairness rules
* Solvability

When a Ren'Py SDK is available, the test suite also runs:

```bash
renpy.sh . lint
```

This catches actual Ren'Py parser/build errors that ordinary Python tests cannot.

`(｀・ω・´)ゞ`

---

# Project Structure

```text
Blackwood-Manor/
|
+-- game/
|   |
|   +-- engine/
|   |   +-- state.py
|   |   +-- conflicts.py
|   |   +-- bridge.py
|   |   +-- audio_manifest.py
|   |   +-- cli.py
|   |
|   +-- llm.py
|   +-- fallback.json
|   +-- secrets.example.json
|   |
|   +-- *.rpy
|
+-- tests/
|   +-- test_engine.py
|
+-- tools/
|   +-- extract_audio.py
|
+-- CREDITS.md
+-- README.md
```

---

# Built For Arcade x Cambridge

Blackwood Manor Mystery was built for the **Cambridge x Arcade AI Hackathon**, Game Tech Track.

The goal wasn't simply to attach an LLM to a game.

The goal was to make AI part of the **actual mystery system** while keeping the game fair, deterministic, replayable, and solvable.

`( •̀ᴗ•́ )و`

---

# Credits & Attribution

See [CREDITS.md](CREDITS.md) for complete licensing and asset information, including the chromatic aberration shader by **GRIMUMU**.

---

> **The world forgets.**
>
> **You don't.**
>
> `( ͡° ͜ʖ ͡°)`
