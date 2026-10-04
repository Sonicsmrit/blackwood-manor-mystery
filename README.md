# Blackwood Manor Mystery

> **Cambridge x Arcade AI Hackathon — Game Tech Track**  

---

## 📖 Concept

You wake up in a hospital bed with cranial trauma and no memories. A young woman named **Marika** claims to be your girlfriend and brings you to your family's secluded mountain estate. There you meet your sharp younger sister **Elise**, the hired **Nurse Vance**, the longtime butler **Hargrove**, and the housemaid **Odile**.

One of the five is a cold-blooded killer. Every night of Day 2, the killer strikes in the darkness. You die, but wake up on the morning of Day 2 with your memories and notebook intact (**Return by Death**). In your bedside drawer rests your late father's revolver with **one single bullet**.

Deduce the killer before nightfall. Uncover lies, catch deviations in their daily routines, piece together death sensory fragments, and pull the trigger. If you shoot the wrong person, the loop swallows you forever.

---

## 🛠️ Architecture & Features

1. **Deterministic Fairness Engine (`game/engine/`)**
   - **Pure Python with Zero Engine Dependencies**: Fully testable outside Ren'Py via standard unit tests.
   - **Automated Solvability & Fairness Validator**: Generates provably solvable mystery runs within 1 to 2 loops.
   - **Presence & Contradiction Tracking (`conflicts.py`, `bridge.py`)**: Records who you saw and which rooms turned out empty, and surfaces them as plain observations. The notebook never grades a character — you weigh the claims against what you saw and name the killer yourself.
   - **Return by Death State Persistence (`state.py`)**: Keeps notebook entries, discovered facts, and death fragments while cleanly resetting loop day, actions, and trust.

2. **AI Director & Dialogue Engine (`game/llm.py`)**
   - **Constraint-Bound LLM Dialogue**: Generates contextual lines and player choices while strictly preventing knowledge leakage.
   - **100% Offline Playable Fallback (`game/fallback.json`)**: Seamlessly plays offline without requiring an API key.
   - **Optional live director**: copy `game/secrets.example.json` to `game/secrets.json` and fill in **one** key (Google/Gemini, Groq, or Anthropic). `secrets.json` is gitignored — never commit it.

3. **Gothic Visuals & Dynamic Strain Shader**
   - Integrated chromatic aberration lens distortion (`11_shader_chromatic-aberration.rpy`) scaling with loop strain.
   - 4-tab Interactive Notebook (Characters, Timeline, Findings, Deaths).
   - Atmospheric 1080p backgrounds and character expressions.

4. **Curated Audio (`game/engine/audio_manifest.py`)**
   - 31 hand-picked tracks wired across 14 scenes: title, day/night beds, kitchen, storm, burial, both endings.
   - **Silence-triggered atmosphere**: six interchangeable ambient tracks play at random whenever nothing is audible, so the gaps between lines are never quite empty.
   - Silence is measured by polling the audio channels, not by a timestamp — the 29 original `play sound` calls and the voice blip never pass through an audio helper, so only the channels themselves know what is playing.
   - Built with `tools/extract_audio.py`, which extracts the source archives to a gitignored `audio_inbox/` and builds a contact sheet for auditioning.
   - The test suite runs `renpy.sh . lint` against the project when an SDK is present. Three build-breaking errors in this project's history passed every other test, because nothing had handed the scripts to the real parser.

---
# Game Screenshots

## Start Menu
<img width="1896" height="1034" alt="image" src="https://github.com/user-attachments/assets/58b1de80-6939-4604-853e-f1dc607389ed" />

## Intro Sequence
<img width="1892" height="1024" alt="image" src="https://github.com/user-attachments/assets/c3e6e63d-e599-4ce7-815b-e00ea2876762" />

## Day 1 Screen
<img width="1898" height="1021" alt="image" src="https://github.com/user-attachments/assets/837d765b-f53f-4698-8502-f700c890cfbd" />

## Dialogue Exchange
<img width="1915" height="1022" alt="image" src="https://github.com/user-attachments/assets/f58bce8d-01a2-44d8-9bbd-9a5b6378da06" />

## Notebook
<img width="1872" height="1007" alt="image" src="https://github.com/user-attachments/assets/2e226b5a-d6dd-4bb0-8871-6545a760024b" />

## LOOP death
<img width="1653" height="885" alt="image" src="https://github.com/user-attachments/assets/91090bc6-c5a6-49c2-bc93-ab4313fc4254" />


---

## 🚀 How to Run

### Option 1: Run the Visual Novel in Ren'Py
Download the [Ren'Py SDK](https://www.renpy.org/latest/html/), then launch the game from this project directory:
```bash
/path/to/renpy-8.x.x-sdk/renpy.sh .
```

### Option 2: Run the Headless Simulation CLI
Play or simulate an automated run in terminal:
```bash
python3 game/engine/cli.py --verbose
```

### Option 3: Run the Test Suite
Verify that all mystery runs, seeds, state preservation, and fairness rules pass:
```bash
python3 -m unittest tests/test_engine.py
```

---

## 📜 Attributions & Credits
See [CREDITS.md](CREDITS.md) for full licensing and asset details, including the chromatic aberration shader by **GRIMUMU**.
