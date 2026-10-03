## Return by Death Manor - Main Script
init offset = 2

init python:
    import sys
    import os
    import json
    import random

    # Add game directory to Python path
    sys.path.insert(0, config.gamedir)

    from engine.constants import (
        PLAYER_NAME, DAYS, SLOTS, LOCATIONS, ACTIONS_PER_SLOT,
        CONVO_MAX_TURNS, MAX_STRAIN, TRUST_MIN, TRUST_MAX,
        CHARACTERS, TOPICS, BASE_LOCATIONS, AGENDAS
    )
    from engine.state import RunState, GameState, new_game_state, reset_loop
    from engine.generator import generate_run
    from engine.facts import build_all_facts, get_available_facts, get_search_findings
    from engine.conflicts import find_conflicts
    from engine.dialogue import generate_intents, apply_intent
    from engine.solver import solve
    from bridge import get_character_display_name, get_location_display_name
    from llm import generate_dialogue_fallback

# Disable rollback to maintain state consistency across loops
define config.rollback_enabled = False

# Character definitions
define adrian = Character("Adrian", color="#ffffff")
define marika_char = Character("Marika", color="#ff69b4")
define elise_char = Character("Elise", color="#9370db")
define vance_char = Character("Nurse Vance", color="#20b2aa")
define hargrove_char = Character("Hargrove", color="#daa520")
define odile_char = Character("Odile", color="#bc8f8f")
define unknown = Character("???", color="#888888")
define death_narrator = Character(None, what_italic=True, what_size=28, what_color="#ffffff")

# Background images
image white = "#ffffff"
image black = "#000000"
image bg parlor = "images/bg/ROOM1.png"
image bg study = Transform("images/bg/ROOM3.png", matrixcolor=BrightnessMatrix(-0.08) * TintMatrix("#f5e6d0"))
image bg kitchen = Transform("images/bg/ROOM2.png", matrixcolor=TintMatrix("#e4f2e4"))
image bg upstairs = "images/bg/ROOM4.png"
image bg gate = Transform("images/bg/ROOM4.png", matrixcolor=TintMatrix("#7588a8") * BrightnessMatrix(-0.15))

# Character sprites
# Marika
image marika neutral = "images/characters/marika/base/Marika_base.webp"
image marika calm = "images/characters/marika/base/Marika_okay.webp"
image marika angry = "images/characters/marika/base/Marika_angry.webp"
image marika sly = "images/characters/marika/base/Marika_smirk.webp"
image marika sad = "images/characters/marika/base/Marika_sad.webp"
image marika tearful = "images/characters/marika/base/Marika_cry.webp"
image marika shy = "images/characters/marika/base/Marika_shy.webp"
image marika apologetic = "images/characters/marika/base/Marika_sorry.webp"
image marika creepy = "images/characters/marika/base/Marika_creepy.webp"

# Elise
image elise neutral = "images/characters/elise/GIRL_FULL1.png"
image elise bloodied = "images/characters/elise/GIRL_FULL3.png"

# Vance
image vance neutral = "images/characters/vance/NURSE_FULL1.png"
image vance bloodied = "images/characters/vance/NURSE_FULL3.png"

# Hargrove
image hargrove neutral = "images/characters/hargrove/BUTLER_FULL1.png"
image hargrove bloodied = "images/characters/hargrove/BUTLER_FULL3.png"

# Odile
image odile neutral = "images/characters/odile/MAID_FULL1.png"
image odile bloodied = "images/characters/odile/MAID_FULL3.png"

# Transforms
transform sprite_standing:
    xalign 0.5
    yalign 1.0

transform death_shake:
    linear 0.05 xoffset -15
    linear 0.05 xoffset 15
    linear 0.05 xoffset -10
    linear 0.05 xoffset 10
    linear 0.05 xoffset 0

# Game variables
default run_state = None
default game_state = None
default all_facts = []
default current_loc_presence = {}
default chosen_loc = "parlor"
default active_speaker = "marika"
default active_speaker_name = "Marika"
default active_speaker_color = "#ff69b4"
default active_npc_line = ""
default active_choices = []
default active_mood = "neutral"

################################################################################
## Game Initialization & Flow
################################################################################
label start:
    # 1. Initialize random seeded run
    python:
        seed_val = renpy.random.randint(1, 999999)
        run_state = generate_run(seed_val)
        all_facts = run_state.facts
        game_state = new_game_state(run_state, start_day=1)

    # 2. Begin scripted Day 1 introduction
    jump day1_intro

################################################################################
## Day 1 Scripted Introduction
################################################################################
label day1_intro:
    scene black with fade
    pause 1.0

    # Beat 1: Hospital wake
    "A sterile white ceiling. The smell of antiseptic and wet stone."
    "Your skull throbs behind your eyes with dull, rhythmic agony."

    show marika shy at sprite_standing with dissolve
    marika_char "Adrian? You're awake... Thank God. The doctors said you might not open your eyes for days."

    adrian "Who... who are you?"

    show marika sad at sprite_standing
    marika_char "It's me. Marika. Don't you remember me? We've been together for two years..."
    marika_char "The doctor warned me your memories might be scattered after the crash. But you're alive. That's all that matters."

    # Beat 2: The drive
    scene bg gate with fade
    show marika calm at sprite_standing with dissolve
    "The journey through the fog was quiet. Winding pine roads, steep drops into mist, and stone gates."
    marika_char "This is your family manor. Elise brought you back as soon as the hospital signed the discharge."

    # Beat 3: Arrival & Elise confrontation
    scene bg parlor with fade
    show elise neutral at sprite_standing with dissolve
    elise_char "You brought him back. Finally."
    show marika shy at sprite_standing
    marika_char "Elise, please. He needs quiet. The head injury—"
    show elise neutral at sprite_standing
    elise_char "I know what my brother needs. And you know the arrangement, Marika: you are not permitted inside past sunset. Wait at the gate."
    show marika sad at sprite_standing
    marika_char "Elise..."
    show elise neutral at sprite_standing
    elise_char "The gate, Marika. Now."
    hide marika with dissolve

    # Beat 4: Vance
    show vance neutral at sprite_standing with dissolve
    vance_char "Adrian. I am Nurse Vance. Elise retained my services through the regional clinic."
    vance_char "Two blue capsules after meals. Total bed rest when the dizziness strikes. No excursions beyond the grounds."

    # Beat 5: Hargrove
    hide vance with dissolve
    show hargrove neutral at sprite_standing with dissolve
    hargrove_char "Welcome home, young master Adrian. Forty years I have served your family; the house felt hollow without you."
    hargrove_char "Dinner is prepared in the kitchen. Do ring if the draft in your quarters becomes troublesome."

    # Beat 6: Odile
    hide hargrove with dissolve
    show odile neutral at sprite_standing with dissolve
    odile_char "Tea for you, sir. Chamomile... just as your late mother preferred."
    odile_char "I have turned down the sheets upstairs, sir. If you need anything... anything at all, do call."
    hide odile with dissolve

    # Beat 7: Night 1
    scene bg upstairs with fade
    "Night settles over the manor with oppressive weight."
    "The grandfather clock in the stairwell ticks with slow, deliberate hollow knocks."
    "Safe for now. But in the quiet darkness, something cold coils at the back of your mind."

    # Day 1 Investigation Loop
    "Morning arrives through dust-streaked leaded windows."
    show screen hud
    jump day_slot_start

################################################################################
## Main Day & Slot Loop
################################################################################
label day_slot_start:
    # Update current slot character positions
    python:
        day_str = str(game_state.current_day)
        slot_str = game_state.current_slot
        current_loc_presence = {loc: [] for loc in LOCATIONS}
        for c in CHARACTERS:
            c_pos = run_state.positions[c][day_str][slot_str]
            current_loc_presence[c_pos].append(c)

    # Let player choose a location for this slot
    call screen location_picker(current_loc_presence)
    $ chosen_loc = _return
    $ game_state.current_location = chosen_loc

    # Set background for the location
    if chosen_loc == "parlor":
        scene bg parlor with dissolve
    elif chosen_loc == "study":
        scene bg study with dissolve
    elif chosen_loc == "kitchen":
        scene bg kitchen with dissolve
    elif chosen_loc == "upstairs":
        scene bg upstairs with dissolve
    elif chosen_loc == "gate":
        scene bg gate with dissolve

    # Record presence and absence facts
    python:
        present = current_loc_presence[chosen_loc]
        # Record who is seen
        for c in present:
            pres_fact = f"presence:seen:{c}:{chosen_loc}:{game_state.current_slot}:{game_state.current_day}"
            game_state.known_facts.add(pres_fact)

        # Record absences (if character claimed to be here but is absent)
        routine_claims = {
            "marika": {"morning": "gate", "afternoon": "parlor", "evening": "gate"},
            "elise": {"morning": "upstairs", "afternoon": "study", "evening": "upstairs"},
            "vance": {"morning": "upstairs", "afternoon": "upstairs", "evening": "kitchen"},
            "hargrove": {"morning": "kitchen", "afternoon": "parlor", "evening": "kitchen"},
            "odile": {"morning": "parlor", "afternoon": "kitchen", "evening": "parlor"}
        }
        for c in CHARACTERS:
            claimed = routine_claims[c][game_state.current_slot]
            if claimed == chosen_loc and c not in present:
                abs_fact = f"presence:absence:{c}:{chosen_loc}:{game_state.current_slot}:{game_state.current_day}"
                game_state.known_facts.add(abs_fact)

    jump location_action_loop

################################################################################
## Location Action Loop (2 Actions Per Slot)
################################################################################
label location_action_loop:
    # Check if actions remaining for this slot are exhausted
    if game_state.slot_actions_remaining <= 0:
        jump advance_slot

    python:
        present = current_loc_presence[game_state.current_location]
        actions_left = game_state.slot_actions_remaining
        bullet_on = game_state.bullet_available
        cday = game_state.current_day

    call screen action_picker(game_state.current_location, present, actions_left, cday, bullet_on)
    $ action_type, action_target = _return

    if action_type == "talk":
        $ game_state.slot_actions_remaining -= 1
        $ game_state.conversations_this_slot.add(action_target)
        $ active_speaker = action_target
        jump start_conversation

    elif action_type == "search":
        $ game_state.slot_actions_remaining -= 1
        jump execute_search

    elif action_type == "shoot_menu":
        call screen shoot_target_picker(current_loc_presence[game_state.current_location])
        $ chosen_target = _return
        if chosen_target == "cancel":
            jump location_action_loop
        else:
            $ target_name = get_character_display_name(chosen_target)
            call screen shoot_confirm(target_name)
            if _return == "shoot":
                $ game_state.target_shot = chosen_target
                jump execute_shot
            else:
                jump location_action_loop

    elif action_type == "pass":
        $ game_state.slot_actions_remaining = 0
        jump advance_slot

################################################################################
## Search Logic
################################################################################
label execute_search:
    python:
        cur_loc = game_state.current_location
        present = current_loc_presence[cur_loc]
        findings = get_search_findings(cur_loc, game_state.current_slot, game_state.current_day, run_state.positions, all_facts, present)

        # Check watching rule: if a character belongs here and is present
        watching_chars = [c for c in present if BASE_LOCATIONS.get(c) == cur_loc]

    if watching_chars:
        $ watcher_name = get_character_display_name(watching_chars[0])
        "[watcher_name] is present in the room, keeping a watchful eye on you. You cannot search without drawing suspicion."
    elif findings:
        python:
            new_finds = [f for f in findings if f.id not in game_state.known_facts]
            for f in new_finds:
                game_state.known_facts.add(f.id)
                game_state.notebook_entries.append(f.id)

        if new_finds:
            "You search carefully through drawers, cabinets, and hidden recesses..."
            python:
                for f in new_finds:
                    renpy.say(None, "DISCOVERY: " + f.text)
        else:
            "You search the room again, but find nothing beyond what you already cataloged."
    else:
        "You search carefully through the room, but uncover nothing of interest here."

    jump location_action_loop

################################################################################
## Conversation Flow
################################################################################
label start_conversation:
    python:
        speaker_roster = {
            "marika": ("Marika", "#ff69b4"),
            "elise": ("Elise", "#9370db"),
            "vance": ("Nurse Vance", "#20b2aa"),
            "hargrove": ("Hargrove", "#daa520"),
            "odile": ("Odile", "#bc8f8f")
        }
        active_speaker_name, active_speaker_color = speaker_roster[active_speaker]
        convo_turn = 0

    # Show speaker sprite
    if active_speaker == "marika":
        show marika neutral at sprite_standing with dissolve
    elif active_speaker == "elise":
        show elise neutral at sprite_standing with dissolve
    elif active_speaker == "vance":
        show vance neutral at sprite_standing with dissolve
    elif active_speaker == "hargrove":
        show hargrove neutral at sprite_standing with dissolve
    elif active_speaker == "odile":
        show odile neutral at sprite_standing with dissolve

    # Initial greeting line
    $ active_npc_line = f"{active_speaker_name} pauses what they are doing and turns to face you."

label convo_turn_loop:
    python:
        convo_turn += 1
        current_trust = game_state.trust[active_speaker]
        intents = generate_intents(active_speaker, current_trust, game_state.known_facts, all_facts, convo_turn)
        dialogue_pack = generate_dialogue_fallback(
            char=active_speaker,
            intent="small_talk",
            trust=current_trust,
            revealed_facts=[],
            deflected=False,
            choices_spec=intents
        )
        active_choices = dialogue_pack["choices"]

    call screen conversation_ui(active_speaker_name, active_speaker_color, active_npc_line, active_choices)
    $ chosen_intent = _return

    python:
        result = apply_intent(chosen_intent, active_speaker, game_state, run_state, all_facts)
        next_pack = generate_dialogue_fallback(
            char=active_speaker,
            intent=chosen_intent,
            trust=result["new_trust"],
            revealed_facts=result["revealed_facts"],
            deflected=result["deflected"],
            choices_spec=intents
        )
        active_npc_line = next_pack["npc_line"]
        active_mood = next_pack["mood"]

    # Show updated mood sprite for Marika
    if active_speaker == "marika":
        if active_mood == "angry":
            show marika angry at sprite_standing
        elif active_mood == "shy":
            show marika shy at sprite_standing
        elif active_mood == "calm":
            show marika calm at sprite_standing
        elif active_mood == "sly":
            show marika sly at sprite_standing
        elif active_mood == "sad":
            show marika sad at sprite_standing
        elif active_mood == "tearful":
            show marika tearful at sprite_standing
        elif active_mood == "apologetic":
            show marika apologetic at sprite_standing
        else:
            show marika neutral at sprite_standing

    if result["lockout"]:
        "[active_speaker_name] turns away sharply, refusing to speak with you any further this slot."
        hide marika
        hide elise
        hide vance
        hide hargrove
        hide odile
        with dissolve
        jump location_action_loop

    if result["end_conversation"] or convo_turn >= CONVO_MAX_TURNS:
        hide marika
        hide elise
        hide vance
        hide hargrove
        hide odile
        with dissolve
        jump location_action_loop

    jump convo_turn_loop

################################################################################
## Advance Slot & Day Transitions
################################################################################
label advance_slot:
    python:
        game_state.slot_actions_remaining = ACTIONS_PER_SLOT
        game_state.conversations_this_slot.clear()
        game_state.locked_out.clear()

        # Slot progression: morning -> afternoon -> evening
        if game_state.current_slot == "morning":
            game_state.current_slot = "afternoon"
            next_label = "day_slot_start"
        elif game_state.current_slot == "afternoon":
            game_state.current_slot = "evening"
            next_label = "day_slot_start"
        else:
            # Evening ends -> Night!
            if game_state.current_day == 1:
                next_label = "day1_night_transition"
            else:
                next_label = "day2_night_transition"

    jump expression next_label

################################################################################
## Day 1 Safe Night Transition
################################################################################
label day1_night_transition:
    scene black with fade
    "Night falls over the estate. Rain lashes against the leaded panes."
    "Tomorrow is Day 2. Something in this house is shifting, coming closer."
    jump day2_morning_transition

################################################################################
## Day 2 Morning: Revolver Beat
################################################################################
label day2_morning_transition:
    python:
        game_state.current_day = 2
        game_state.current_slot = "morning"
        game_state.slot_actions_remaining = ACTIONS_PER_SLOT
        game_state.bullet_available = True

    scene bg upstairs with fade
    "Day 2. Morning light cuts cold across the wooden floorboards."
    "As you open the nightstand drawer beside your bed, metal catches the light."
    "Your late father's revolver. Heavy, cold, and loaded with exactly ONE bullet."
    "Whoever caused the crash is here. Tonight, they will finish what they started."
    "Unless you stop them first."
    jump day_slot_start

################################################################################
## Day 2 Night: Last Chance & Murder
################################################################################
label day2_night_transition:
    # If bullet is still available, present the last chance prompt
    if game_state.bullet_available:
        scene bg parlor with fade
        "Midnight approaches. The shadows stretch across the walls like grasping fingers."
        "You feel the weight of the revolver in your coat. One bullet remains."

        menu:
            "Draw the revolver now and shoot someone":
                call screen shoot_target_picker(CHARACTERS)
                $ final_target = _return
                if final_target != "cancel":
                    $ tname = get_character_display_name(final_target)
                    call screen shoot_confirm(tname)
                    if _return == "shoot":
                        $ game_state.target_shot = final_target
                        jump execute_shot
            "Hold fire and wait through the darkness":
                pass

    jump night_death

################################################################################
## Shoot Execution
################################################################################
label execute_shot:
    $ game_state.bullet_available = False
    $ shot_target = game_state.target_shot
    $ tname = get_character_display_name(shot_target)

    # Gunshot sound and flash
    scene white with Dissolve(0.1)
    with death_shake
    scene black with Dissolve(0.3)

    "A deafening report tears through the manor hall."
    "[tname] stumbles backward, clutching their chest as blood blooms across fabric."

    if shot_target == run_state.killer:
        $ game_state.killer_shot = True
        $ game_state.game_over = True
        $ game_state.ending = "victory"
        jump ending_victory
    else:
        $ game_state.wrong_kill = True
        "A horrifying silence falls. [tname] collapses to the floor, motionless."
        "You shot the wrong person. The revolver cylinder clicks empty."
        "The real killer is still here."
        jump night_death

################################################################################
## Night Death & Return by Death Loop Reset
################################################################################
label night_death:
    hide screen hud
    scene black with fade
    pause 0.5

    "Footsteps approach in the darkness. Quiet, measured, completely without hurry."
    "A cold hand closes around your throat."

    # Sensory fragment display
    python:
        frag_idx = min(len(run_state.fragment_order) - 1, game_state.loop_no - 1)
        frag_cat = run_state.fragment_order[frag_idx]
        frag_text = DEATH_FRAGMENTS[run_state.killer][frag_cat]
        game_state.fragments_seen.append(frag_text)

    # Screen shake and chromatic flash
    with death_shake
    death_narrator "\"[frag_text]\""
    pause 2.0

    # Strain calculation
    python:
        strain_increase = 2 if game_state.wrong_kill else 1
        game_state.strain += strain_increase

    if game_state.strain > MAX_STRAIN:
        jump ending_swallowed
    else:
        # Return by Death Flash
        scene white with Dissolve(0.2)
        with death_shake
        scene black with Dissolve(0.4)

        python:
            game_state = reset_loop(game_state, run_state)

        # Wake up at Day 2 Morning!
        show screen hud
        "You gasp for air, bolting upright in bed. Sweat soaks your hospital gown."
        "Your hands shake. The hairline cracks across your skin burn like heated wires."
        "Day 2. You remember everything. The loop has returned you to the morning."
        jump day2_morning_transition

################################################################################
## Endings
################################################################################
label ending_victory:
    hide screen hud
    $ k = run_state.killer
    $ ag = run_state.agenda
    python:
        fb_data = get_fallback_data()
        epilogue_line = fb_data.get("epilogues", {}).get(ag, {}).get(k, "The killer collapses.")
        victory_coda_line = fb_data.get("victory_coda", "")

    scene bg parlor with fade
    "The smoke clears in the stillness of the parlor."

    # Show bloodied killer sprite
    if k == "elise":
        show elise bloodied at sprite_standing with dissolve
    elif k == "vance":
        show vance bloodied at sprite_standing with dissolve
    elif k == "hargrove":
        show hargrove bloodied at sprite_standing with dissolve
    elif k == "odile":
        show odile bloodied at sprite_standing with dissolve
    elif k == "marika":
        show marika creepy at sprite_standing with dissolve

    "[epilogue_line]"

    scene black with fade
    pause 1.0

    "[victory_coda_line]"

    pause 2.0
    centered "{size=32}{color=#66c1e0}VICTORY ACHIEVED\nYou broke the time loop and uncovered the truth.{/color}{/size}"
    pause 3.0
    return

label ending_swallowed:
    hide screen hud
    scene white with Dissolve(1.5)
    python:
        fb_data = get_fallback_data()
        swallowed_text = fb_data.get("swallowed_ending", "The loop closes permanently.")

    "[swallowed_text]"
    pause 2.0
    centered "{size=32}{color=#ff3333}LOOP COLLAPSED\nYour mind was swallowed by the manor.{/color}{/size}"
    pause 3.0
    return
