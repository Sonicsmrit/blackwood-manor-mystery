## Return by Death Manor - Main Script (Cinematic Edition)
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
        CHARACTERS, TOPICS, BASE_LOCATIONS, AGENDAS, DEATH_FRAGMENTS,
        get_motive
    )
    from engine.state import RunState, GameState, new_game_state, reset_loop, time_of_day_label
    import time
    from engine.generator import generate_run
    from engine.facts import build_all_facts, get_available_facts, get_search_findings
    from engine.dialogue import generate_intents, apply_intent
    from engine.solver import solve
    from bridge import (get_character_display_name, get_location_display_name,
                        parse_presence_fact, presence_absence_text,
                        presence_absence_text_for, evidence_label)
    from llm import generate_dialogue_fallback, get_fallback_data, generate_dialogue
    from engine.audio_manifest import (
        MUSIC, AMBIENCE, AMBIENT_POOL, AMBIENCE_LOOPING,
        VOLUME_MUSIC, VOLUME_AMBIENCE, VOLUME_STINGER,
        IDLE_AMBIENCE_AFTER, AMBIENCE_COOLDOWN,
        FADE_SHORT, FADE_LONG,
    )

    # Register voice blip sound channel
    renpy.music.register_channel("voice_sfx", mixer="sfx", loop=True)

    # Monotonic stamps driving the idle-ambience watcher. Deliberately not the
    # SDK's own time accessor, which is absent here and is what the stale
    # traceback.txt is a record of. Set whenever anything audible plays, so the
    # silences between lines are measured rather than assumed.
    _last_audio_at = time.monotonic()
    _last_pool_at = time.monotonic()

    def voice_bleep_callback(event, interact=True, **kwargs):
        if not interact:
            return
        if event == "show":
            spk = getattr(renpy.store, "current_voice_speaker", "adrian")
            vfile = "audio/voice_" + str(spk) + ".wav"
            if renpy.loadable(vfile):
                renpy.sound.play(vfile, channel="voice_sfx", loop=True)
        elif event in ("slow_done", "end"):
            renpy.sound.stop(channel="voice_sfx")

    def build_conversation_context(char, game_state, run_state, all_facts, present_names):
        """Construct detailed narrative and character context for the LLM."""
        day = game_state.current_day
        slot = game_state.current_slot
        loc = game_state.current_location
        loc_name = get_location_display_name(loc)
        loop_no = game_state.loop_no
        strain = game_state.strain
        is_killer = (char == run_state.killer)
        agenda_info = AGENDAS.get(run_state.agenda, {})

        secret_explanations = {
            "lingering": "You linger in the parlor after sunset when you should be outside, secretly watching the family.",
            "unsent_letters": "You keep a hidden bundle of desperate, unsent love letters expressing painful obsession.",
            "night_visits": "You creep down to the parlor or cellar in the dead of night to check on locked strongboxes.",
            "diary": "You keep a locked diary chronicling the family's crushing debts, ruin, and shame.",
            "phone_calls": "You make clandestine calls from the study to unknown contacts outside the valley.",
            "skimming_pills": "You secretly skim pharmaceutical morphine and sedatives from the clinic supply case.",
            "pawned_watch": "You secretly pawned the late master's gold watch to cover personal debts.",
            "drinking": "You hide bottles of cheap gin in the kitchen pantry to numb your grief and fear.",
            "stolen_silver": "You hid several heavy silver dessert spoons behind a loose pantry wainscot.",
            "eavesdropping": "You listen at heating vents and keyholes to learn the family's dark secrets."
        }

        char_secret_key = run_state.secrets.get(char, "")
        char_secret_desc = secret_explanations.get(char_secret_key, "You harbor a private, shameful secret.")

        # Topics this character has already given up, so they react to being
        # asked twice instead of repeating themselves verbatim.
        discussed = sorted({
            f.topic for f in all_facts
            if f.char == char and f.id in game_state.known_facts and getattr(f, "topic", None)
        })

        # Report the hour to the LLM as "night" only for the genuine midnight sequence.
        # A revolver fired in the afternoon runs the same burial round but is still
        # the afternoon, so the model must not be told otherwise.
        # game_state.current_slot is deliberately left alone -- it feeds the engine's
        # three-slot model, where a fourth value would KeyError.
        if night_sequence:
            slot = "night"

        killed_name = ""
        if game_state.wrong_kill and game_state.target_shot:
            killed_name = get_character_display_name(game_state.target_shot)

        scene_desc = {
            "day": day,
            "slot": slot,
            "location": loc_name,
            "present_characters": present_names,
            "loop_number": loop_no,
            "strain": strain,
            "deaths": len(game_state.fragments_seen),
            "discussed_topics": discussed,
            "bullet_carried": game_state.bullet_available,
            "is_killer": is_killer,
            "wrong_kill": game_state.wrong_kill,
            "after_hours": after_hours_active,
            "at_night": night_sequence,
            "weapon": wrong_kill_weapon,
            "killed_name": killed_name
        }

        if is_killer:
            cause = agenda_info.get("cause", "sabotage")
            motive = get_motive(run_state.agenda, run_state.killer)
            slips = ", ".join(agenda_info.get("slip_keywords", []))
            scene_desc["secret_truth"] = (
                "KILLER: You are the murderer who orchestrated the fatal crash by " + str(cause) + ". "
                "Your hidden motive is: " + str(motive) + ". "
                "If pressed on the crash or motive, you might accidentally slip keywords like: " + slips + ". "
                + (
                    # Stale once the knife has already been used on an innocent:
                    # the night is already violent, so there is no clean kill left.
                    "You still mean to finish Adrian off, and now there is a body in the ground to do it beside. "
                    "Maintain your composure, but show subtle cracks if cornered."
                    if after_hours_active else
                    "Tonight you plan to finish Adrian off. Maintain your composure, but show subtle cracks if cornered."
                )
            )
        else:
            scene_desc["secret_truth"] = (
                "INNOCENT: You did NOT commit the murder or cause the crash. However, you are hiding this shameful secret: '" + str(char_secret_desc) + "'. "
                "You are terrified of this secret being exposed, making you appear defensive or anxious when questioned."
            )

        return scene_desc

# Disable rollback to maintain state consistency across loops
define config.rollback_enabled = False

# Character definitions with rich colors & voice bleep styling
define adrian = Character("Adrian", color=GOTH_C_ADRIAN, callback=voice_bleep_callback)
define marika_char = Character("Marika", color=GOTH_C_MARIKA, callback=voice_bleep_callback)
define elise_char = Character("Elise", color=GOTH_C_ELISE, callback=voice_bleep_callback)
define vance_char = Character("Nurse Vance", color=GOTH_C_VANCE, callback=voice_bleep_callback)
define hargrove_char = Character("Hargrove", color=GOTH_C_HARGROVE, callback=voice_bleep_callback)
define odile_char = Character("Odile", color=GOTH_C_ODILE, callback=voice_bleep_callback)
define unknown = Character("???", color=GOTH_C_UNKNOWN)
define death_narrator = Character(None, what_italic=True, what_size=30, what_color=GOTH_BLOOD_HI)
define thought = Character(None, what_italic=True, what_size=25, what_color=GOTH_TEXT_SOFT)

# ─── Background images using the mansion pack (1920×1080) ────────────────────
# Parlor: Grand entrance hall
image bg parlor = "images/bg/mansion/interior_entrance_day.png"
image bg parlor_evening = "images/bg/mansion/interior_entrance_evening.png"
image bg parlor_night = "images/bg/mansion/interior_entrance_night.png"

# Study: Hallway with windows and curtains
image bg study = "images/bg/mansion/inthallway2_day.png"
image bg study_evening = "images/bg/mansion/inthallway2_evening.png"
image bg study_night = "images/bg/mansion/inthallway2_night.png"

# Kitchen: Basement / servants' working area
image bg kitchen = "images/bg/mansion/basement1.png"
image bg kitchen_evening = Transform("images/bg/mansion/basement1.png", matrixcolor=BrightnessMatrix(-0.15) * TintMatrix("#e8c87a"))
image bg kitchen_night = Transform("images/bg/mansion/basement1.png", matrixcolor=BrightnessMatrix(-0.3) * TintMatrix("#7080a0"))

# Upstairs: Bedroom
image bg upstairs = "images/bg/mansion/bedroom01_day.png"
image bg upstairs_evening = "images/bg/mansion/bedroom01_evening.png"
image bg upstairs_night = Transform("images/bg/mansion/bedroom01_day.png", matrixcolor=BrightnessMatrix(-0.4) * TintMatrix("#5060a0"))

# Gate: Backyard / exterior
image bg gate = "images/bg/mansion/backyard_day1.png"
image bg gate_evening = "images/bg/mansion/backyard_evening.png"
image bg gate_night = "images/bg/mansion/backyard_night1.png"

# Utility colors
image white = "#ffffff"
image black = "#000000"

# ─── Character sprites (normalized sizes with zoom) ──────────────────────────
# Marika (832x1280) — scale to fit screen nicely
image marika neutral = Transform("images/characters/marika/base/Marika_base.webp", zoom=0.55)
image marika calm = Transform("images/characters/marika/base/Marika_okay.webp", zoom=0.55)
image marika angry = Transform("images/characters/marika/base/Marika_angry.webp", zoom=0.55)
image marika sly = Transform("images/characters/marika/base/Marika_smirk.webp", zoom=0.55)
image marika sad = Transform("images/characters/marika/base/Marika_sad.webp", zoom=0.55)
image marika tearful = Transform("images/characters/marika/base/Marika_cry.webp", zoom=0.55)
image marika shy = Transform("images/characters/marika/base/Marika_shy.webp", zoom=0.55)
image marika apologetic = Transform("images/characters/marika/base/Marika_sorry.webp", zoom=0.55)
image marika creepy = Transform("images/characters/marika/base/Marika_creepy.webp", zoom=0.55)

# Elise (712x1208)
image elise neutral = Transform("images/characters/elise/GIRL_FULL1.png", zoom=0.58)
image elise talking = Transform("images/characters/elise/GIRL_FULL2.png", zoom=0.58)
image elise somber = Transform("images/characters/elise/GIRL_FULL5.png", zoom=0.58)
image elise angry = Transform("images/characters/elise/GIRL_FULL9.png", zoom=0.58)
image elise distressed = Transform("images/characters/elise/GIRL_FULL13.png", zoom=0.58)
image elise bloodied = Transform("images/characters/elise/GIRL_FULL3.png", zoom=0.58)

# Vance (690x1531)
image vance neutral = Transform("images/characters/vance/NURSE_FULL1.png", zoom=0.47)
image vance talking = Transform("images/characters/vance/NURSE_FULL2.png", zoom=0.47)
image vance clinical = Transform("images/characters/vance/NURSE_FULL1.png", matrixcolor=BrightnessMatrix(-0.08) * SaturationMatrix(0.85), zoom=0.47)
image vance bloodied = Transform("images/characters/vance/NURSE_FULL3.png", zoom=0.47)

# Hargrove (548x1470)
image hargrove neutral = Transform("images/characters/hargrove/BUTLER_FULL1.png", zoom=0.49)
image hargrove talking = Transform("images/characters/hargrove/BUTLER_FULL2.png", zoom=0.49)
image hargrove grave = Transform("images/characters/hargrove/BUTLER_FULL1.png", matrixcolor=BrightnessMatrix(-0.1) * TintMatrix("#d0d8e8"), zoom=0.49)
image hargrove bloodied = Transform("images/characters/hargrove/BUTLER_FULL3.png", zoom=0.49)

# Odile (590x1389)
image odile neutral = Transform("images/characters/odile/MAID_FULL1.png", zoom=0.51)
image odile talking = Transform("images/characters/odile/MAID_FULL2.png", zoom=0.51)
image odile nervous = Transform("images/characters/odile/MAID_FULL2.png", matrixcolor=BrightnessMatrix(-0.05) * TintMatrix("#f8eae0"), zoom=0.51)
image odile bloodied = Transform("images/characters/odile/MAID_FULL3.png", zoom=0.51)

# ─── Transforms & Transitions ────────────────────────────────────────────────
transform sprite_standing:
    xalign 0.5
    yalign 1.0
    yoffset -20

transform sprite_left:
    xalign 0.25
    yalign 1.0
    yoffset -20

transform sprite_right:
    xalign 0.75
    yalign 1.0
    yoffset -20

transform camera_creep:
    zoom 1.0
    ease 4.0 zoom 1.08 yoffset -30

transform snap_focus:
    easein 0.2 zoom 1.15 yoffset -50

define death_shake = Move((20, 0), (-20, 0), .04, bounce=True, repeat=True, delay=.3)

# ─── Game variables ──────────────────────────────────────────────────────────
default run_state = None
default game_state = None
default all_facts = []
default current_loc_presence = {}
default chosen_loc = "parlor"
default active_speaker = "marika"
default active_speaker_name = "Marika"
default active_speaker_color = GOTH_C_MARIKA
default active_npc_line = ""
default active_choices = []
default active_mood = "neutral"
default active_expression = "neutral"
default convo_history = []
default chosen_choice_text = ""
default current_voice_speaker = "adrian"
default npc_char = marika_char

# Narrative state (not part of the deterministic engine)
default marika_intro_warm = False
default confidant = None
default confided_attempt = False

# Weapons are physical objects, so they reset with the loop. Only Adrian's
# knowledge of where they are carries over, which is the whole point.
default revolver_found = False
default revolver_key_found = False
default drawer_examined = False
default knife_found = False
default knife_taken_back = False
default after_hours_active = False

# True only when the killing came out of the midnight menu. Distinct from
# after_hours_active: the revolver is available in any slot, so a killing can
# start the burial round in the afternoon, when current_slot is still "afternoon"
# and the HUD must keep saying Afternoon.
default night_sequence = False

# Which weapon made the wrong kill: "revolver" or "knife". Drives the burial
# scene's discovery and surrender lines.
default wrong_kill_weapon = ""

# Cover-up speakers are assigned by role at runtime, since any of the five
# may be the one on the floor. Declared here so they always resolve.
default lead_char = elise_char
default medic_char = vance_char
default steady_char = hargrove_char
default taker_char = odile_char

################################################################################
## Helper Functions
################################################################################
init python:
    def get_time_display():
        """Top-left time label. The midnight menu leaves current_slot on
        'evening' because the engine models three slots and no night slot, so
        night_sequence supplies the hour. A daytime killing keeps its real slot.
        See time_of_day_label."""
        return time_of_day_label(game_state.current_slot, night_sequence)

    def get_scene_bg(loc, slot, at_night):
        """Background for a scene that must respect the hour.

        Every location already ships an _evening and a _night variant; morning and
        afternoon share the plain daytime image.
        """
        if at_night:
            return "bg " + loc + "_night"
        return get_bg_image_name(loc, slot)

    def get_bg_image_name(loc, slot):
        """Return the Ren'Py image name for a location at the current time slot."""
        if slot == "evening":
            return "bg " + loc + "_evening"
        else:
            return "bg " + loc

    def update_npc_expression(char, expr):
        """Update the on-screen character sprite to match the chosen facial model."""
        valid = {
            "marika": ["neutral", "calm", "angry", "sly", "sad", "tearful", "shy", "apologetic", "creepy"],
            "elise": ["neutral", "talking", "somber", "angry", "distressed", "bloodied"],
            "vance": ["neutral", "talking", "clinical", "bloodied"],
            "hargrove": ["neutral", "talking", "grave", "bloodied"],
            "odile": ["neutral", "talking", "nervous", "bloodied"]
        }
        char_valid = valid.get(char, ["neutral"])
        tag = expr if expr in char_valid else "neutral"
        renpy.show(char + " " + tag, at_list=[sprite_standing])

    # ── Audio ─────────────────────────────────────────────────────────────────
    #
    # Ren'Py routes the default music and sound channels through the "music" and
    # "sfx" mixers; ambience and stingers need their own channels so volume can be
    # set independently and so the idle watcher can query what is still playing.
    renpy.music.register_channel("ambience", mixer="ambience", loop=False)
    renpy.music.register_channel("stinger", mixer="sfx", loop=False)

    # The voice blip loop already plays on every dialogue line, which means the
    # music genuinely has to sit under it rather than merely be "quieter".
    renpy.music.set_volume(channel="music", volume=VOLUME_MUSIC)
    renpy.music.set_volume(channel="ambience", volume=VOLUME_AMBIENCE)
    renpy.music.set_volume(channel="stinger", volume=VOLUME_STINGER)

    def set_music(key, loop=True, fade=None):
        """Play a track by manifest key. Fades in unless told not to."""
        path = MUSIC.get(key)
        if not path or not renpy.loadable(path):
            return
        renpy.music.play(path, channel="music", loop=loop,
                         fadein=FADE_LONG if fade is None else fade)
        _last_audio_at = time.monotonic()

    def stop_music(fade=None):
        """Silence the music channel. Used at the loop reset and on endings."""
        renpy.music.stop(channel="music",
                         fadeout=FADE_LONG if fade is None else fade)

    def set_ambience(key, loop=False, fade=None):
        """Play a named ambience or stinger. Storm wind loops, nothing else does."""
        path = AMBIENCE.get(key)
        if not path or not renpy.loadable(path):
            return
        if loop is None:
            loop = key in AMBIENCE_LOOPING
        renpy.sound.play(path, channel="ambience", loop=loop,
                         fadein=FADE_SHORT if fade is None else fade)
        _last_audio_at = time.monotonic()

    def sfx_sting(key):
        """One-shot punctuation on its own channel, so it never cuts a bed."""
        path = AMBIENCE.get(key)
        if not path or not renpy.loadable(path):
            return
        renpy.sound.play(path, channel="stinger")
        _last_audio_at = time.monotonic()

    def stop_ambience(fade=None):
        renpy.sound.stop(channel="ambience",
                         fadeout=FADE_SHORT if fade is None else fade)

    def play_ambience_bed(key):
        """An atmosphere bed chosen by scene, looped until something stops it."""
        path = MUSIC.get(key)
        if not path or not renpy.loadable(path):
            return
        renpy.music.play(path, channel="ambience", loop=True, fadein=FADE_LONG)
        _last_audio_at = time.monotonic()

    def idle_ambience_tick():
        """Play something from the pool when the house has been quiet.

        Driven by a timer rather than a wall-clock alarm because the voice blip
        channel plays on every dialogue line and loops for 1.8s: true silence is
        rare mid-conversation, so the pool lands in the gaps and on the
        non-conversation screens instead. Volume is low enough to read as
        texture rather than an event.
        """
        now = time.monotonic()
        if now - _last_audio_at < IDLE_AMBIENCE_AFTER:
            return
        if now - _last_pool_at < AMBIENCE_COOLDOWN:
            return
        renpy.music.play(
            renpy.random.choice(AMBIENT_POOL),
            channel="ambience", loop=False)
        _last_audio_at = now
        _last_pool_at = now

    config.main_menu_music = MUSIC["title"]

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
        _preferences.text_cps = 38

    # 2. Begin cinematic prologue and Day 1 introduction
    jump day1_intro

################################################################################
## Day 1 Scripted Introduction (Cinematic Edition)
################################################################################
label day1_intro:
    show screen cinema_letterbox
    scene black with fade
    set_music("atmos_low")
    pause 1.0

    # ─── Prologue: the crash, remembered wrong ───────────────────────────────
    play sound "audio/thunder.wav"
    sfx_sting("static")
    pause 0.5
    "Rain. Not falling so much as thrown, in fistfuls, against curved sheet metal."
    "Headlights find nothing but pine and fog. The road ends three feet past the bumper and begins again only when you are already on it."

    thought "Father is driving. Mother has her hand flat on the dashboard, the way she does when she will not say she is frightened."

    pause 0.5
    with death_shake
    "Something gives way under the floorboard. A small sound. Almost polite."
    "The brake pedal goes to the floor and stays there, soft as a held breath."
    "Then the gravel lets go of the tyres, and the world tilts, and the headlights swing out into nothing at all."

    play sound "audio/strain_burn.wav"
    scene white with Dissolve(0.15)
    with death_shake
    scene black with Dissolve(0.8)

    "Glass opens around you like something blooming. Then a silence so complete it feels deliberate."
    pause 1.5

    # ─── The hospital ────────────────────────────────────────────────────────
    play sound "audio/heartbeat.wav"
    pause 1.0

    "White ceiling. Antiseptic, old linen, and underneath it the iron smell of yourself."
    "There is a throb behind your eyes keeping time with your pulse, patient and unhurried, as though it intends to go on for years."

    show marika shy at sprite_standing with dissolve
    marika_char "Adrian...?{w=0.4} Oh — oh God. Look at me. You're awake, you're actually—"

    "A young woman. Pale gold hair, slept-in clothes, a chair pulled so close to the bed its legs have scuffed the floor."
    thought "She has been here a long time. Days, maybe. I have never seen her before in my life."

    adrian "Who are you?"

    show marika tearful at sprite_standing
    "She stops as if she has walked into glass. Her hand is already halfway to your arm and it stays there, in the air, going nowhere."
    marika_char "Don't.{w=0.3} Don't look at me like that. Please. It's Marika. Two years, Adrian, we've — "
    show marika sad at sprite_standing
    marika_char "They said your head. They said the memories might not... They said you might not."

    thought "She is saying my name like it is a rope she is trying to throw me."

    menu:
        "I'm sorry. I don't know you.":
            $ marika_intro_warm = False
            adrian "I'm sorry. I'm — I'm looking right at you and there's nothing there."
            show marika tearful at sprite_standing
            marika_char "Then I'll just have to be new to you. That's all. That's all it is."
            thought "She smiled when she said it. That was the worst part."

        "Tell me something only you would know.":
            $ marika_intro_warm = False
            adrian "Then tell me something. Something only you'd know."
            show marika sad at sprite_standing
            marika_char "You sign your name with the 'n' trailing off, like you got bored of it halfway. You've done it since you were nine."
            thought "I don't remember doing it. But my hand already knows she is right, and that is somehow worse than not knowing at all."

        "Stay. Please — just stay where I can see you.":
            $ marika_intro_warm = True
            adrian "Don't go. I don't know you, but — don't go. Not yet."
            show marika calm at sprite_standing
            marika_char "I'm not going anywhere. I haven't, the whole time. Ask the nurses, they've gotten quite sick of me."
            thought "Her shoulders came down about an inch. I did that. I don't know her name well enough to have done that."

    # ─── The road up ─────────────────────────────────────────────────────────
    scene bg gate with fade
    show marika calm at sprite_standing with dissolve
    "The drive takes most of a day. Black pine, iron railings, and a drop on the left that the road pretends not to notice."
    thought "Somewhere on a pass exactly like this one, my parents stopped existing. Nobody in this car mentions it."
    marika_char "Blackwood. Your family's house. Your sister wanted you out of that hospital the hour you opened your eyes."
    marika_char "She didn't ask what the doctors wanted. She doesn't, really."

    "The gates come out of the fog like a row of spears someone has planted and forgotten."

    # ─── Arrival: Elise and Marika, in front of each other ───────────────────
    scene bg parlor with fade
    show elise somber at sprite_right with dissolve
    "The hall swallows sound. Portraits three generations deep look down with the particular disapproval of people who were painted being disappointed."
    "At the foot of the staircase, a young woman in mourning black has been standing long enough that she has stopped pretending not to wait."

    elise_char "You brought him back."
    show elise angry at sprite_right
    elise_char "Eleven days, and you brought him back on the eleventh. I'm sure there's a reason."

    show marika shy at sprite_left with dissolve
    marika_char "He couldn't be moved. The pressure in his skull — Elise, he couldn't sit up without—"
    show elise angry at sprite_right
    elise_char "Don't tell me about my brother's skull."

    "Silence. Somewhere above, a clock works through its mechanism without hurrying."

    show elise talking at sprite_right
    elise_char "You know the arrangement. Not past the foyer after dark. The gate lodge is dry and it is more than you are owed."
    show marika sad at sprite_left
    marika_char "He doesn't remember the crash. He doesn't remember me. And you want me at the end of a drive in November."
    show elise angry at sprite_right
    elise_char "I want you where I can account for you."

    thought "They are doing this in front of me. Neither of them has looked at me since I came through the door."
    thought "Whatever I was to these two, I was something they fought over. That is the first real thing I've learned about myself."

    hide marika with dissolve
    pause 0.4

    show elise somber at sprite_standing with dissolve
    "When the door closes, something in her face comes loose for a moment, and then is put back."
    elise_char "Welcome home, brother."
    elise_char "You'll find it much as you left it. Colder, perhaps. We've been economising."

    adrian "Elise — do I call you Elise?"

    show elise distressed at sprite_standing
    "She looks at you then. Properly, for the first time."
    elise_char "...You called me Lise. When we were small. You were the only one permitted."
    show elise somber at sprite_standing
    elise_char "Call me Elise. It will be less strange for both of us."
    hide elise with dissolve

    thought "She lied. It would not have been less strange for her."

    # ─── Vance, intercepting ─────────────────────────────────────────────────
    show vance clinical at sprite_standing with dissolve
    "A woman in grey is waiting at the turn of the stair with the air of someone who has been timing you."
    vance_char "Nurse Vance. Your sister retained me through the clinic at Ardmore. Sit down before you fall down — no, there. The light's better."
    "Cold fingers at your jaw, turning your face toward the window. She looks at one pupil, then the other, and her mouth tightens by perhaps a millimetre."
    vance_char "Temporal contusion, retrograde amnesia, and a household with the emotional climate of a knife drawer. Two blue capsules after meals."
    vance_char "No stairs alone. No cliffs. No arguments. I can mend the first two."
    hide vance with dissolve

    thought "She did not say 'you'll be fine.' I notice people who don't say that."

    # ─── Hargrove, who knew him ──────────────────────────────────────────────
    show hargrove talking at sprite_standing with dissolve
    "An old man in a tailcoat comes down the corridor far too quickly for his knees and stops himself a respectful distance away, visibly."
    hargrove_char "Young master Adrian.{w=0.4} Forgive me. Forgive me, sir, give an old fool a moment."
    "He gets his face under control the way a man closes a drawer."
    hargrove_char "Forty-one years I've kept this hall. These past weeks it has been a mausoleum with the lamps left on."

    adrian "I'm sorry — I don't..."

    show hargrove grave at sprite_standing
    hargrove_char "No, sir. Of course not. It is no failing of yours."
    hargrove_char "You taught me to use a fountain pen, once. You were nine and insisted I was holding it like a spade. You were quite right."
    show hargrove talking at sprite_standing
    hargrove_char "There is broth in the kitchen. It will be there whether you want it or not. That is how broth works."
    hide hargrove with dissolve

    thought "Forty-one years. He would know everything that happens in this house."
    thought "He would also know how to make certain that nobody found out."

    # ─── Odile, who is not supposed to be noticed ────────────────────────────
    show odile nervous at sprite_standing with dissolve
    "A maid is in the doorway with a tray, and has clearly been there for some while, waiting for a gap in the conversation that never came."
    odile_char "Tea, sir. Chamomile — the late mistress took it so, in the library, in the evenings. I thought..."
    "She does not finish the thought. She sets the tray down and does not quite leave."
    odile_char "The east wing's aired, sir. And if you hear anything in the walls at night, it's only the pipes."
    odile_char "It's only ever the pipes."

    adrian "Has it been the pipes recently?"

    show odile nervous at sprite_standing
    "She looks at the doorway behind her before she answers, which is itself an answer."
    odile_char "...I couldn't say, sir."
    hide odile with dissolve

    # ─── Night one ───────────────────────────────────────────────────────────
    scene bg upstairs_night with fade
    play sound "audio/clock_tick.wav"
    "Night comes down over the ridge like a lid."
    "In the stairwell, the grandfather clock takes midnight apart one stroke at a time."

    play sound "audio/clock_tick.wav"
    thought "Five people under this roof. Every one of them has looked at me today as though checking a sum."
    thought "Somebody cut the brake lines on my father's car."
    thought "And then that somebody came home, and ate dinner, and said goodnight to me in the hall."

    pause 1.0
    hide screen cinema_letterbox

    # Reveal HUD and begin Day 1 investigation
    set_music("clock")
    "Morning comes thin and grey through diamond panes, and the house is already awake."
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

    # Kitchen gets its own bed; it is entered often enough to be worth one.
    # At night the night bed wins, since the kitchen is somewhere you are
    # standing in the dark rather than working in it.
    if night_sequence:
        set_music("night")
    elif chosen_loc == "kitchen":
        set_music("kitchen")
    else:
        set_music("atmos_general")

    # Set background for the location with time-of-day variant
    $ _bg_tag = get_bg_image_name(chosen_loc, game_state.current_slot)

    if chosen_loc == "parlor" and game_state.current_slot == "evening":
        scene bg parlor_evening with dissolve
    elif chosen_loc == "study" and game_state.current_slot == "evening":
        scene bg study_evening with dissolve
    elif chosen_loc == "kitchen" and game_state.current_slot == "evening":
        scene bg kitchen_evening with dissolve
    elif chosen_loc == "upstairs" and game_state.current_slot == "evening":
        scene bg upstairs_evening with dissolve
    elif chosen_loc == "gate" and game_state.current_slot == "evening":
        scene bg gate_evening with dissolve
    elif chosen_loc == "parlor":
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
            pres_fact = "presence:seen:" + c + ":" + chosen_loc + ":" + game_state.current_slot + ":" + str(game_state.current_day)
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
                abs_fact = "presence:absence:" + c + ":" + chosen_loc + ":" + game_state.current_slot + ":" + str(game_state.current_day)
                game_state.known_facts.add(abs_fact)

    jump location_action_loop

################################################################################
## Location Action Loop (2 Actions Per Slot)
################################################################################
label location_action_loop:
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
        watching_chars = [c for c in present if BASE_LOCATIONS.get(c) == cur_loc]

    if watching_chars:
        $ watcher_name = get_character_display_name(watching_chars[0])
        "[watcher_name] has not left, and has not stopped glancing over. Whatever is in this room will stay in it while you are being watched."
        jump location_action_loop

    # ─── Weapons are found, never given ──────────────────────────────────
    # The revolver takes two unobserved searches in two different rooms:
    # the key is in the study, the drawer is upstairs. The knife is easy,
    # which is exactly why it is the wrong weapon.
    if cur_loc == "study" and game_state.current_day == 2 and not revolver_key_found:
        $ revolver_key_found = True
        "Father's desk is a monument to a man who did not trust his own memory: every drawer labelled, every ledger cross-referenced, every key accounted for in a hand you half recognise as your own."
        "Taped under the shallow left-hand drawer, where a man would put a thing he wanted findable but not found, there is a small flat brass key."
        play sound "audio/select.wav"
        thought "Bedside. He always said a locked drawer by the bed was the only honest piece of furniture in a house like this."
        jump location_action_loop

    if cur_loc == "upstairs" and game_state.current_day == 2 and not revolver_found:
        if revolver_key_found:
            $ revolver_found = True
            $ game_state.bullet_available = True
            play sound "audio/revolver_cock.wav"
            "The brass key turns with a small, exact click, as though it has been waiting all year to be useful."
            "Inside, on velvet gone stiff with age, wrapped in oilcloth: your father's service revolver. Cold. Heavier than it looks. Balanced like something designed by people who thought carefully about killing."
            "You swing the cylinder out. One brass cartridge. One."
            thought "One. He left one in it. I have spent all day not thinking about why a man would leave exactly one."
            jump location_action_loop
        else:
            if not drawer_examined:
                $ drawer_examined = True
                "You go at the nightstand drawer with your fingers, then with a letter opener, then with both hands and your whole weight, and it does not give."
                "The lock is small, flat, and older than you are. Forcing it would take a crowbar and a quarter of an hour, and you have neither."
                thought "It needs its key. Father kept keys the way other men keep grudges — catalogued, and close to the thing they opened."
            else:
                "The drawer is exactly as locked as it was an hour ago. You check anyway, because you are the sort of man who checks."
            jump location_action_loop

    if cur_loc == "kitchen" and not knife_found and not knife_taken_back:
        $ knife_found = True
        play sound "audio/select.wav"
        "The block by the range holds six knives and a gap where a seventh should be. The boning knife is in the drying rack, thin, slightly sprung, honed by someone who does it every day without thinking."
        "You put it inside your coat. It sits badly there. It will keep sitting badly there."
        thought "This is not the same as the revolver. A revolver is a decision made at a distance. This is a decision made with your hands."
        jump location_action_loop

    if findings:
        python:
            new_finds = [f for f in findings if f.id not in game_state.known_facts]
            for f in new_finds:
                game_state.known_facts.add(f.id)
                game_state.notebook_entries.append(f.id)

        if new_finds:
            "The room is empty and stays empty. You go through the drawers, the ledgers, the gap behind the mantel clock, with the unhurried thoroughness of a man who has run out of polite options."
            python:
                for f in new_finds:
                    renpy.say(None, "{color=" + GOTH_GOLD + "}You find it.{/color} " + f.text)
        else:
            "You go over it again anyway. It gives up nothing it has not already given up."
    else:
        "Nothing. Dust, old paper, and the particular silence of a room that has no opinion about you."

    jump location_action_loop

################################################################################
## Conversation Flow
################################################################################
label start_conversation:
    python:
        speaker_roster = {
            "marika": ("Marika", GOTH_C_MARIKA),
            "elise": ("Elise", GOTH_C_ELISE),
            "vance": ("Nurse Vance", GOTH_C_VANCE),
            "hargrove": ("Hargrove", GOTH_C_HARGROVE),
            "odile": ("Odile", GOTH_C_ODILE)
        }
        active_speaker_name, active_speaker_color = speaker_roster[active_speaker]
        speaker_char_map = {
            "marika": marika_char,
            "elise": elise_char,
            "vance": vance_char,
            "hargrove": hargrove_char,
            "odile": odile_char
        }
        npc_char = speaker_char_map[active_speaker]
        convo_turn = 0
        convo_history = []
        # A quarter of Elise's Day 2 conversations get the short theme under them.
        if active_speaker == "elise" and game_state.current_day == 2:
            if renpy.random.random() < 0.25:
                set_music("elise_day2")
        _preferences.text_cps = 38

    # Hide HUD during intimate dialogue
    hide screen hud

    # Initial speaker display
    python:
        update_npc_expression(active_speaker, "neutral")

    # Generate greeting + first set of choices via LLM (or fallback)
    python:
        current_trust = game_state.trust[active_speaker]
        intents = generate_intents(active_speaker, current_trust, game_state.known_facts, all_facts, 1)
        present_names = [get_character_display_name(c) for c in current_loc_presence.get(game_state.current_location, []) if c != active_speaker]
        scene_ctx = build_conversation_context(active_speaker, game_state, run_state, all_facts, present_names)
        greeting_pack = generate_dialogue(
            char=active_speaker,
            intent="greeting",
            trust=current_trust,
            revealed_facts=[],
            deflected=False,
            choices_spec=intents,
            context={"scene": scene_ctx, "history": []}
        )
        active_npc_line = greeting_pack.get("dialogue") or greeting_pack.get("npc_line", "")
        active_choices = greeting_pack.get("choices", [])
        active_mood = greeting_pack.get("mood", "neutral")
        active_expression = greeting_pack.get("expression", "neutral")
        update_npc_expression(active_speaker, active_expression)

label convo_turn_loop:
    $ convo_turn += 1

    # Force an interaction boundary so the click that dismissed the previous
    # line cannot carry into the choice screen that follows it.
    pause 0.01

    # Choices stay locked until this moment, so the click that skipped the last
    # line cannot land on one. See CHOICE_ARM_DELAY.
    $ convo_arm_at = time.monotonic() + CHOICE_ARM_DELAY

    # Call conversation UI: character dialogue on top, choice boxes at bottom
    call screen conversation_ui(active_speaker_name, active_speaker_color, active_npc_line, active_choices, convo_arm_at)
    $ chosen_intent, chosen_choice_text = _return

    # Play selection sound
    play sound "audio/select.wav"

    # Adrian delivers his chosen reply aloud with his own voice!
    $ current_voice_speaker = "adrian"
    adrian "[chosen_choice_text]"

    # Track conversation history and calculate outcome
    python:
        convo_history.append({"speaker": active_speaker_name, "text": active_npc_line})
        convo_history.append({"speaker": "Adrian", "text": chosen_choice_text})
        result = apply_intent(chosen_intent, active_speaker, game_state, run_state, all_facts)
        active_mood = result.get("mood", "neutral")

    # Handle lockout
    if result["lockout"]:
        $ current_voice_speaker = active_speaker
        if active_speaker == "elise":
            npc_char "No. I have been patient and I have been civil and I am now finished with both. Go."
        elif active_speaker == "marika":
            npc_char "You're doing it the way they do it. The questions, the order of them. I'd rather you hit me, Adrian."
        elif active_speaker == "vance":
            npc_char "Your pulse is over a hundred and you are shouting at your nurse. We're done. Go and sit down."
        elif active_speaker == "hargrove":
            npc_char "I have given this family forty-one years, sir. I will not stand in this hall and be inventoried."
        else:
            npc_char "Please — please, sir, don't. I'm wanted in the kitchen. I'm wanted in the kitchen, sir."
        hide marika
        hide elise
        hide vance
        hide hargrove
        hide odile
        with dissolve
        show screen hud
        jump location_action_loop

    # Handle end of conversation
    if result["end_conversation"] or convo_turn >= CONVO_MAX_TURNS:
        hide marika
        hide elise
        hide vance
        hide hargrove
        hide odile
        with dissolve
        show screen hud
        jump location_action_loop

    # Generate NPC response + next choices
    python:
        new_trust = result["new_trust"]
        next_intents = generate_intents(active_speaker, new_trust, game_state.known_facts, all_facts, convo_turn + 1)
        present_names = [get_character_display_name(c) for c in current_loc_presence.get(game_state.current_location, []) if c != active_speaker]
        scene_ctx = build_conversation_context(active_speaker, game_state, run_state, all_facts, present_names)
        next_pack = generate_dialogue(
            char=active_speaker,
            intent=chosen_intent,
            trust=new_trust,
            revealed_facts=result["revealed_facts"],
            deflected=result["deflected"],
            choices_spec=next_intents,
            context={"scene": scene_ctx, "history": convo_history}
        )
        active_npc_line = next_pack.get("dialogue") or next_pack.get("npc_line", "")
        active_mood = next_pack.get("mood", "neutral")
        active_expression = next_pack.get("expression", "neutral")
        active_choices = next_pack.get("choices", [])
        update_npc_expression(active_speaker, active_expression)

    jump convo_turn_loop

################################################################################
## Advance Slot & Day Transitions
################################################################################
label advance_slot:
    # After-hours is a bonus round bolted onto the end of the night, so it
    # exits to the killer rather than rolling into the next slot.
    if after_hours_active:
        $ after_hours_active = False
        hide screen hud
        set_music("death")
        "The lamps burn down. One by one they stop talking, and the silence that replaces them is not a restful one."
        jump night_death

    python:
        game_state.slot_actions_remaining = ACTIONS_PER_SLOT
        game_state.conversations_this_slot.clear()
        game_state.locked_out.clear()

        if game_state.current_slot == "morning":
            game_state.current_slot = "afternoon"
            next_label = "day_slot_start"
        elif game_state.current_slot == "afternoon":
            game_state.current_slot = "evening"
            next_label = "day_slot_start"
            sfx_sting("evening_bell")
else:
        if game_state.current_day == 1:
            next_label = "day1_evening_bond"
        else:
            next_label = "day2_night_transition"

    # The last slot of the day gets its own bed. Day 1 evening is still a normal
    # evening; on Day 2 it is the last one before midnight.
    if game_state.current_slot == "evening":
        set_music("evening_final" if (game_state.current_day == 2 and not after_hours_active) else "atmos_general")

    jump expression next_label

################################################################################
## Day 1, last light: whoever you got closest to comes looking for you
################################################################################
##
## This is where the trust integer stops being an integer. Whoever Adrian
## reached furthest sits down with him once, before anyone has died, so that
## Day 2 has something to cost him.

label day1_evening_bond:
    python:
        # Highest trust wins. Ties break toward the people who started closed
        # off, so warming Marika or Elise outranks a butler who liked you anyway.
        _bond_order = ["marika", "elise", "odile", "vance", "hargrove"]
        confidant = max(_bond_order, key=lambda c: (game_state.trust.get(c, 0), -_bond_order.index(c)))
        _bond_trust = game_state.trust.get(confidant, 0)

    show screen cinema_letterbox
    scene bg parlor_evening with fade
    set_music("evening_final")
    play sound "audio/clock_tick.wav"
    pause 0.4

    "The lamps are lit early. Outside, the light goes the colour of weak tea and then goes out entirely."

    if _bond_trust <= 1:
        # Nobody opened up. The house simply closes around him.
        thought "A whole day in my own home, and not one person in it has told me a true thing."
        "You sit in the parlor until the fire is embers, and nobody comes."
        thought "I keep waiting for someone to knock. Somewhere between the ninth and tenth hour I understand that nobody is going to."
        $ confidant = None
        jump day1_night_transition

    # ─── Marika ──────────────────────────────────────────────────────────────
    if confidant == "marika":
        show marika sad at sprite_standing with dissolve
        "There is a sound at the terrace door. Marika is on the wrong side of it, coat soaked through at the shoulders, not knocking — just standing where she can be seen."
        marika_char "I'm not coming in. I know the rule. I just wanted to see the lamps go on from closer than the gate."

        adrian "You've been out there all day."

        show marika calm at sprite_standing
        marika_char "I've been out there for eleven days. Today you were in the house, so today was better."
        marika_char "You keep apologising for not knowing me. Don't. You're the only one here who's honest about it."
        show marika shy at sprite_standing
        marika_char "Everyone else in this place knew exactly who you were and let it happen anyway."

        thought "She said that very quietly, and then looked like she wished she hadn't."

        adrian "Let what happen?"

        show marika sad at sprite_standing
        marika_char "Goodnight, Adrian. Lock the terrace after me. Please actually lock it."
        hide marika with dissolve
        thought "She has never once asked me to let her in. She asks me to lock doors."

    # ─── Elise ───────────────────────────────────────────────────────────────
    elif confidant == "elise":
        show elise somber at sprite_standing with dissolve
        "Elise comes in without announcing herself, which in this house is practically an embrace, and sits down two chairs away."
        elise_char "Don't speak. I've been composing this since four o'clock and if you speak I shall lose it."

        "She looks at the fire rather than at you."
        elise_char "When they telephoned from the hospital, they said you were alive and I was — "
        show elise distressed at sprite_standing
        elise_char "I was relieved before I was grieved. For our parents. I was relieved first."
        elise_char "I have not told anyone that. I am telling it to someone who will not remember it, which I find I can bear."

        adrian "I'll remember this."

        show elise somber at sprite_standing
        elise_char "...Then that was a poor calculation on my part."
        "She stands, smooths her skirt twice, and recovers her face on the way to the door."
        elise_char "The house is cold at the east end. Don't wander. I have lost quite enough of this family for one season."
        hide elise with dissolve
        thought "Lise. I almost said it."

    # ─── Odile ───────────────────────────────────────────────────────────────
    elif confidant == "odile":
        show odile nervous at sprite_standing with dissolve
        "Odile comes to bank the fire and takes considerably longer about it than banking a fire requires."
        odile_char "Sir... may I say a thing that isn't my place?"

        adrian "I'd prefer it, honestly."

        show odile talking at sprite_standing
        odile_char "You thank me. You've done it four times today. Nobody's done that in this house since the mistress."
        show odile nervous at sprite_standing
        odile_char "And — the pipes, sir. What I said about the pipes."
        odile_char "It's footsteps. On the back stair, the one the family doesn't use. Most nights now, after the clock goes twelve."

        adrian "Whose footsteps?"

        odile_char "I don't look, sir."
        "She picks up the coal scuttle and holds it in front of her like a shield."
        odile_char "I've twelve years here and nowhere else to go. I don't look."
        hide odile with dissolve
        thought "She told me anyway. She was frightened the entire time and she told me anyway."

    # ─── Vance ───────────────────────────────────────────────────────────────
    elif confidant == "vance":
        show vance neutral at sprite_standing with dissolve
        "Vance arrives with the evening capsules and, unusually, does not leave once you have taken them."
        vance_char "Sit. Pulse."
        "Two fingers at your wrist. She watches the second hand and says nothing for a quarter of a minute."

        vance_char "Sixty-four. Irritatingly good. You'll outlive this house."
        show vance talking at sprite_standing
        vance_char "I'll tell you something off the record, and if you repeat it I'll deny it with my whole chest."
        vance_char "I've nursed in six houses like this one. They all have a bad room. Usually it's the money."
        show vance clinical at sprite_standing
        vance_char "Here it isn't the money. Here everyone is frightened of a different thing, and none of them will say what."

        adrian "Including you?"

        vance_char "Including me. Take your capsules."
        hide vance with dissolve
        thought "She waited until I asked before she admitted it. But she did admit it."

    # ─── Hargrove ────────────────────────────────────────────────────────────
    else:
        show hargrove talking at sprite_standing with dissolve
        "Hargrove brings the broth, as promised, and a second bowl, which he sets down opposite without comment and does not touch."
        hargrove_char "Your father took his supper in this room every evening of his life. He would not have it anywhere else, even at the end, when the two of you were — "
        show hargrove grave at sprite_standing
        hargrove_char "Even at the end."

        adrian "We argued. Didn't we."

        hargrove_char "You did, sir. Loudly and often, and about money, and I heard rather more of it than a butler ought."
        hargrove_char "I will tell you the part that matters. The last time, in March, you offered to sell what was yours to settle what was his."
        show hargrove talking at sprite_standing
        hargrove_char "He said no, and he was proud of you, and he did not say so. I have thought about that every day since the gorge."

        thought "He is telling me I was good. He is telling me because there is no one left alive who can tell me."

        hargrove_char "Eat, young master. It is a long night and the house is cold."
        hide hargrove with dissolve

    pause 0.6
    hide screen cinema_letterbox
    jump day1_night_transition

################################################################################
## Day 1 Safe Night Transition (Cinematic)
################################################################################
label day1_night_transition:
    hide screen hud
    show screen cinema_letterbox
    scene bg parlor_night with fade
    set_music("night")
    set_ambience("storm_wind", loop=True)
    play sound "audio/thunder.wav"
    pause 0.5

    "A thunderstorm descends upon the Blackwood ridge."
    "Wind screams through the leaded sash windows, rattling the stained glass."
    
    play sound "audio/clock_tick.wav"
    "Midnight. The shadows in the stairwell stretch long and distorted."
    "Tomorrow is Day 2. The air in this house feels charged, like iron before lightning strikes."
    "Someone here is watching you. Waiting for their moment."

    sfx_sting("storm_sting")
    pause 1.0
    hide screen cinema_letterbox
    stop_ambience(fade=2.5)
    jump day2_morning_transition

################################################################################
## Day 2 Morning: Revolver Beat (Cinematic)
################################################################################
label day2_morning_transition:
    python:
        game_state.current_day = 2
        game_state.current_slot = "morning"
        game_state.slot_actions_remaining = ACTIONS_PER_SLOT
        game_state.bullet_available = revolver_found
        night_sequence = False

    show screen cinema_letterbox
    scene bg upstairs with fade
    set_music("clock")
    "Day 2. The morning comes in cold and grey through frosted panes."
    "Getting up, your hand catches the brass pull of the nightstand's bottom drawer, and the drawer does not move."

    play sound "audio/clock_tick.wav"
    pause 0.4

    "Locked. Not stuck — locked, with the small flat kind of lock that takes the small flat kind of key."
    "You put your eye to the gap. Something inside is wrapped in oilcloth, and the shape of it is not a shape you can mistake for anything else."

    thought "Father's service revolver. It is eight inches away and it may as well be in the gorge with him."
    thought "He kept the key somewhere. He kept everything somewhere, and he wrote down where, because he never trusted his own memory either."

    if game_state.loop_no == 1:
        thought "Whoever cut those brake lines is going to come for me tonight. I need to be holding that before they do."
    else:
        thought "Same drawer. Same lock. Somewhere in this house is the key, and I have until midnight to be quicker about it than last time."

    pause 1.0
    hide screen cinema_letterbox
    show screen hud
    jump day_slot_start

################################################################################
## Day 2 Night: Last Chance & Murder (Cinematic)
################################################################################
label day2_night_transition:
    hide screen hud
    show screen cinema_letterbox
    scene bg parlor_night with fade
    $ night_sequence = True
    set_music("atmos_low")

    play sound "audio/clock_tick.wav"
    pause 0.5
    "Midnight arrives."
    "The grandfather clock tolls twelve deliberate, hollow beats through the silence."
    if game_state.bullet_available and knife_found:
        "The revolver is a cold weight under your coat. The kitchen knife is a colder one, flat against your forearm, and you are not sure when you started carrying both."
    elif game_state.bullet_available:
        "The revolver sits under your coat with its one cartridge, and every few minutes you check that it is still there."
    elif knife_found:
        "You have a boning knife from the kitchen block and nothing else, and the handle has gone slick in your hand."
    else:
        "You have nothing in your hands and nothing in your pockets, and the hallway is very long."

    if game_state.bullet_available or knife_found:
        menu:
            "Draw the revolver and go looking for them" if game_state.bullet_available:
                set_music("suspense")
                call screen shoot_target_picker(CHARACTERS, "revolver")
                $ final_target = _return
                if final_target != "cancel":
                    $ tname = get_character_display_name(final_target)
                    call screen shoot_confirm(tname, "revolver")
                    if _return == "shoot":
                        $ game_state.target_shot = final_target
                        jump execute_shot

            "Take the knife and go looking for them" if knife_found:
                set_music("suspense")
                call screen shoot_target_picker(CHARACTERS, "knife")
                $ final_target = _return
                if final_target != "cancel":
                    $ tname = get_character_display_name(final_target)
                    call screen shoot_confirm(tname, "knife")
                    if _return == "shoot":
                        $ game_state.target_shot = final_target
                        jump execute_stab

            "Stay where you are and let them come to you":
                pass

    jump night_death

################################################################################
## Shoot Execution (Cinematic)
################################################################################
label execute_shot:
    $ game_state.bullet_available = False
    $ wrong_kill_weapon = "revolver"
    $ shot_target = game_state.target_shot
    $ tname = get_character_display_name(shot_target)

    # Gunshot sound, flash, kickback
    play sound "audio/gunshot.wav"
    scene white with Dissolve(0.08)
    with death_shake
    scene black with Dissolve(0.4)

    "A thunderous report shatters the silence of the manor!"
    "The muzzle flash scorches your retinas. The bitter stink of cordite fills your lungs."
    "[tname] gasps, stumbling backward as blood blossoms across their clothes."

    if shot_target == run_state.killer:
        $ game_state.killer_shot = True
        $ game_state.game_over = True
        $ game_state.ending = "victory"
        jump ending_victory
    else:
        $ game_state.wrong_kill = True
        "A horrifying silence collapses over the hall."
        "[tname] crumples to the floorboards, lifeless."
        play sound "audio/revolver_cock.wav"
        set_music("suspense")
        "You pull the trigger again in blind panic—*CLICK*."
        "Empty. You shot the wrong person."
        # No footsteps here: the coverup opens with them arriving, so the old
        # "calm footsteps begin to approach" line would land the same beat twice.
        jump wrong_kill_coverup

################################################################################
## Knife Execution
################################################################################
##
## The knife is the cheap weapon: easy to find, close range, and it leaves a
## body the household has to do something about. Getting it wrong does not
## simply end the night -- it makes you complicit with four other people, and
## complicity is the most talkative state a person can be in.

label execute_stab:
    $ knife_found = False
    $ knife_taken_back = True
    $ wrong_kill_weapon = "knife"
    $ stab_target = game_state.target_shot
    $ tname = get_character_display_name(stab_target)

    play sound "audio/strain_burn.wav"
    set_music("suspense")
    scene black with Dissolve(0.25)
    with death_shake

    "It is nothing like you imagined, because you imagined a decision and this is a scuffle."
    "There is a half-second where [tname] is looking at you with ordinary irritation, and then there is a sound like a boot pulled out of mud, and then there is no half-second left anywhere."
    "They hold onto your sleeve. Not fighting — holding. They go down slowly and take your balance with them, and the two of you end up on the boards together in the dark."

    pause 1.0

    if stab_target == run_state.killer:
        $ game_state.killer_shot = True
        $ game_state.game_over = True
        $ game_state.ending = "victory"
        scene bg parlor_night with Dissolve(0.8)
        "And in the last of it, quite clearly, with your ear six inches from their mouth, they tell you."
        jump ending_victory

    $ game_state.wrong_kill = True
    jump wrong_kill_coverup


################################################################################
## The Cover-Up
################################################################################

label wrong_kill_coverup:
    # The wrong sound first, then the quieter bed under the scene.
    sfx_sting("wrong")
    set_music("death_atmos")
    python:
        survivors = [c for c in CHARACTERS if c != game_state.target_shot]

        # The hour. True when the killing came out of the midnight menu; false
        # when the revolver was fired in a normal slot, where current_slot is
        # still "morning"/"afternoon"/"evening" and must not be talked about as
        # though it were the small hours.
        _at_night = night_sequence
        _shot = wrong_kill_weapon == "revolver"
        _slot = game_state.current_slot

        def _pick(order):
            for c in order:
                if c in survivors:
                    return c
            return survivors[0]

        # Roles, not names -- any of the five can be the one on the floor.
        _lead = _pick(["elise", "vance", "hargrove", "marika", "odile"])
        _medic = _pick(["vance", "hargrove", "elise", "odile", "marika"])
        _steady = _pick([c for c in ["hargrove", "vance", "elise", "marika", "odile"] if c != _lead])
        _taker = _pick([c for c in ["odile", "hargrove", "marika", "vance", "elise"] if c not in (_lead,)])

        _char_objs = {
            "marika": marika_char,
            "elise": elise_char,
            "vance": vance_char,
            "hargrove": hargrove_char,
            "odile": odile_char,
        }
        lead_char = _char_objs[_lead]
        medic_char = _char_objs[_medic]
        steady_char = _char_objs[_steady]
        taker_char = _char_objs[_taker]

        lead_name = get_character_display_name(_lead)
        steady_name = get_character_display_name(_steady)
        taker_name = get_character_display_name(_taker)

        def _show_at(cid, pos):
            renpy.show(cid + " neutral", at_list=[pos])

    scene expression get_scene_bg("parlor", _slot, _at_night) with fade
    play sound "audio/clock_tick.wav"

    # How the house finds out. A revolver is heard by everybody in the valley; a
    # boning knife in a dark hallway is heard by nobody.
    if _shot:
        "The report goes out flat across the valley and comes back off the far slope, and for a second the whole house is listening."
        "They come down in the order they come down, and nobody has to be woken, because everybody is already awake and pretending not to be."
    elif _at_night:
        "Lamps come on along the corridor, one after another, in the order of who sleeps lightest."
    else:
        "The corridor fills up faster than a house that size should fill. Nobody has to be woken. Everybody was already in the way."

    "They find you sitting on the floor beside it with your hands open on your knees, because you cannot think what else to do with your hands."

    $ _show_at(_lead, sprite_left)
    $ _show_at(_steady, sprite_right)
    with dissolve

    lead_char "...Adrian."
    lead_char "Adrian, what have you — what is — "
    "Nobody screams. That is the part you will remember. A house with a body in it, and not one person in it screams."

    adrian "I thought it was them. I was certain it was them."

    lead_char "Certain of what? Say the whole sentence. Say the whole sentence out loud."

    if _at_night:
        "You open your mouth to say it — that tonight you are going to be killed, that you have already been killed, that you were only trying to get there first —"
    else:
        "You open your mouth to say it — that you are going to be killed before this day is out, that you have already been killed, that you were only trying to get there first —"
    play sound "audio/strain_burn.wav"
    with death_shake
    "— and the hand closes on the inside of your throat again, patient as ever, and nothing comes out but air."

    lead_char "He can't breathe. He can't breathe, help me with him — "
    steady_char "I have him. Slowly, sir. Slowly."

    "You come back to yourself with somebody's hand flat between your shoulderblades and the taste of pennies in your mouth."

    $ renpy.hide(_lead)
    $ renpy.hide(_steady)
    with dissolve

    $ _show_at(_medic, sprite_standing)
    with dissolve
    medic_char "Everyone stop talking."
    medic_char "He has a head injury, a pulse I can hear from here, and no reliable idea what day it is. That is my statement and I will put my name to it."
    if _at_night:
        medic_char "If the constabulary come up that road tonight, they take him. And he does not come back from where they take him."
    else:
        medic_char "If the constabulary come up that road today, they take him. And he does not come back from where they take him."
    $ renpy.hide(_medic)
    with dissolve

    $ _show_at(_lead, sprite_left)
    $ _show_at(_steady, sprite_right)
    with dissolve
    lead_char "The ground by the east wall is soft. The gardeners turned it over in October and nobody has been near it since."
    steady_char "...You cannot be saying what you are saying."
    lead_char "Then say a better idea. I am listening, and I would genuinely love one."
    "[steady_name] does not say a better idea."

    $ renpy.hide(_lead)
    $ renpy.hide(_steady)
    with dissolve

    scene expression get_scene_bg("gate", _slot, _at_night) with fade
    set_music("atmos_low")
    if _at_night:
        set_ambience("storm_wind", loop=True)
    play sound "audio/thunder.wav"

    # How long the dig takes, and what it costs, both read off the hour.
    if _at_night:
        "It takes until nearly three. The rain helps, in the way that rain helps."
        "Somebody holds the lamp. Somebody else does most of the digging. You are not permitted to do any of it, which is somehow the worst thing that has happened all night."
    elif _slot == "evening":
        "It takes until the light goes entirely. The rain helps, in the way that rain helps."
        "Somebody holds the lamp. Somebody else does most of the digging. You are not permitted to do any of it, which is somehow the worst thing that has happened today."
    else:
        "It takes the rest of the afternoon. There is no lamp needed and no rain to hide in, and every hour of it is spent in full daylight in front of the house."
        "Somebody else does all of the digging. You are not permitted to help, which is somehow the worst thing that has happened today."

    $ _show_at(_taker, sprite_standing)
    with dissolve
    taker_char "Your coat, sir. And the — and the thing."
    "A hand held out, palm up, that will not look at what it is asking for."
    if _shot:
        taker_char "You're not to have the gun. That's what's been decided. I'm sorry."
    else:
        taker_char "You're not to have anything sharp. That's what's been decided. I'm sorry."
    adrian "You're right to take it."
    taker_char "I wasn't right about anything. I only did as I was told, same as always."
    $ renpy.hide(_taker)
    with dissolve

    # The weapon goes into the hole with the body: it is the evidence, and the
    # evidence is four feet under the east wall.
    if _shot:
        "The revolver goes into the hole with the rest of it, and the soil goes back over it. Someone tamps it flat with the back of a spade and then stands there a long moment afterwards, hat in hand, saying nothing at all."
    else:
        "The knife goes into the hole with the rest of it. The soil goes back. Someone tamps it flat with the back of a spade and then stands there a long moment afterwards, hat in hand, saying nothing at all."

    if _at_night:
        thought "Four people came out here tonight and buried a body for me, and three of them have never hurt anyone in their lives."
    else:
        thought "Four people came out here in daylight and buried a body for me, and three of them have never hurt anyone in their lives."
    thought "And one of them helped me dig, and smiled about it where the lamp could not reach."

    pause 0.8
    jump after_hours


################################################################################
## After Hours
################################################################################
##
## The reward for the worst night of Adrian's life: four people who are now
## inside the secret with him, awake, shaken, and far more honest than they
## were at dinner. This is the knife's actual payoff -- information, bought
## with a loop.

label after_hours:
    python:
        after_hours_active = True
        survivors = [c for c in CHARACTERS if c != game_state.target_shot]
        game_state.current_location = "parlor"
        game_state.slot_actions_remaining = 2
        game_state.conversations_this_slot.clear()
        game_state.locked_out.clear()
        current_loc_presence = {loc: [] for loc in LOCATIONS}
        current_loc_presence["parlor"] = list(survivors)
        # Shared guilt opens people up in a way nothing else in this house does.
        for c in survivors:
            game_state.trust[c] = min(TRUST_MAX, game_state.trust.get(c, 0) + 1)
            # Keyed by the real slot: this round can now start in the afternoon,
            # and a fact filed under "evening" would be a false one.
            pres_fact = "presence:seen:" + c + ":parlor:" + game_state.current_slot + ":" + str(game_state.current_day)
            game_state.known_facts.add(pres_fact)

    scene expression get_scene_bg("parlor", game_state.current_slot, night_sequence) with fade

    # The storm only follows a midnight burial. A revolver fired at four in the
    # afternoon has no weather with it.
    if night_sequence:
        stop_ambience(fade=2.5)
    sfx_sting("body_thud")
    set_music("atmos_general")

    # The round does not advance the clock. A midnight burial is a small-hours
    # scene; a revolver fired at four in the afternoon stays one.
    if night_sequence:
        "Afterwards, nobody goes to bed."
        "They sit in the parlor with the lamps turned down and their boots still wet, and the house is more awake at four in the morning than it has been all week."

        thought "They are frightened, and they are in it with me now, and frightened people who are already in it will say things they would never say at breakfast."
        thought "I have until whoever it is decides the night is not finished. Use it."
    elif game_state.current_slot == "evening":
        "Afterwards nobody goes up. Nobody suggests it."
        "They sit in the parlor with the lamps turned down and their sleeves still stiff, and the house is more awake at the end of this day than it has been all week."

        thought "They are frightened, and they are in it with me now, and frightened people who are already in it will say things they would never say at breakfast."
        thought "I have until whoever it is decides this evening is not finished. Use it."
    else:
        "Afterwards nobody leaves the room, and nobody can say why not."
        "They sit in the parlor in broad daylight with the curtains open, and the house is more awake in the middle of the afternoon than it has been all week."

        thought "They are frightened, and they are in it with me now, and frightened people who are already in it will say things they would never say at breakfast."
        thought "I have until whoever it is decides this is not finished. Use it."

    show screen hud
    jump location_action_loop


################################################################################
## Night Death & Return by Death Loop Reset (Cinematic Horror)
################################################################################
label night_death:
    hide screen hud
    show screen cinema_letterbox
    scene black with fade
    stop_ambience(fade=1.0)
    set_music("death")
    pause 0.6

    play sound "audio/clock_tick.wav"
    "Darkness. Absolute, suffocating darkness."
    "Footsteps approach. Slow, deliberate, entirely without hurry."
    "The floorboards barely creak beneath their weight."

    # Sensory fragment delivery
    python:
        frag_idx = min(len(run_state.fragment_order) - 1, game_state.loop_no - 1)
        frag_cat = run_state.fragment_order[frag_idx]
        frag_text = DEATH_FRAGMENTS[run_state.killer][frag_cat]
        game_state.fragments_seen.append(frag_text)

    # Sensory horror reveal
    play sound "audio/strain_burn.wav"
    show screen heartbeat_flash
    with death_shake
    "Cold hands close around your throat."
    death_narrator "\"[frag_text]\""
    hide screen heartbeat_flash
    pause 1.5

    # Strain calculation
    python:
        strain_increase = 2 if game_state.wrong_kill else 1
        game_state.strain += strain_increase

    if game_state.strain > MAX_STRAIN:
        jump ending_swallowed

    # ─── Return by Death Reality Tear ────────────────────────────────────────
    sfx_sting("return_by_death")
    play sound "audio/loop_snap.wav"
    # Silence over the white flash, then back to whatever the morning is.
    stop_music(fade=0.6)
    scene white with Dissolve(0.15)
    with death_shake
    scene black with Dissolve(0.8)

    python:
        game_state = reset_loop(game_state, run_state)
        # The house resets with him: the drawer is locked again, the knife is
        # back in the rack. Only what he learned comes back with him.
        revolver_found = False
        revolver_key_found = False
        drawer_examined = False
        knife_found = False
        knife_taken_back = False
        night_sequence = False
        wrong_kill_weapon = ""
        after_hours_active = False

    # ─── Awakening ───────────────────────────────────────────────────────────
    play sound "audio/heartbeat.wav"
    pause 0.5

    # Fullscreen loop title card. Strain 3 is the last loop before the ending
    # closes, and its track is ten seconds long -- played once, not looped.
    if game_state.strain >= MAX_STRAIN:
        set_music("strain3", loop=False)
    else:
        set_music("clock")
    call screen loop_splash_screen(game_state.loop_no, game_state.strain)

    scene bg upstairs with fade
    play sound "audio/heartbeat.wav"

    "You come up out of it the way a drowning man comes up — all at once, too loud, hands already fighting something that is no longer there."
    "The sheets are soaked. The room is warm. Nothing in it has been disturbed."

    if game_state.strain == 1:
        "On the inside of your left wrist there is a mark like a crack in glaze, thin and black, warm to the touch."
        thought "That was not there yesterday. There is no yesterday. It was not there an hour ago, and an hour ago I was dead."
    elif game_state.strain == 2:
        "The cracks have spread past your elbow, fine and dark and branching, and they ache the way a struck bone aches."
        thought "It is further up than last time. It is going to keep being further up than last time."
    elif game_state.strain >= 3:
        "You cannot look at your own arm for very long. Something underneath the skin is not keeping its shape."

    "Day 2. Seven in the morning. The light comes in cold and square across the floorboards, exactly as it did before."
    "Downstairs the clock begins its seven strokes, and you know, with absolute certainty, that the fifth one will be slightly flat."
    "It is."

    # The psychological cost scales with how many times he has been through it.
    if game_state.loop_no == 2:
        thought "I died. Someone put their hands around my throat in the dark and I died, and now I am warm and dry and it is morning."
        thought "I can feel where the fingers were. There is nothing on my neck. I checked twice."
        "You sit on the edge of the bed for a long time, waiting to stop believing it. You do not stop believing it."
    elif game_state.loop_no == 3:
        thought "Twice now. The second one was worse, because I knew what the footsteps meant before they arrived."
        thought "I am starting to think of the people downstairs in the past tense. They are going to come down to breakfast and be perfectly alive, and I am going to have to be surprised by it."
        "You practise your face in the dark glass of the window until it looks like a man who has slept."
    elif game_state.loop_no >= 4:
        thought "I have stopped counting out loud. Counting out loud made it worse."
        thought "There is a version of this morning where I simply stay in this room until it ends. I have thought about it more than once. It does not end. I checked that too."
        "You get up, because the alternative is to find out what happens to a man who doesn't."

    "The bedside drawer is open an inch, the way it was. Inside, on the velvet, the revolver is exactly where you left it, with exactly one round."

    hide screen cinema_letterbox

    # The thing that makes the loop lonely: he cannot hand it to anyone.
    if confidant is not None and not confided_attempt and game_state.loop_no >= 2:
        jump loop_confession_attempt

    jump day2_morning_transition


################################################################################
## The Unspeakable Thing
################################################################################
##
## Fires once, the first time Adrian wakes from a death with someone he
## actually trusts. He tries to hand it to them. He cannot. That failure is
## the whole emotional engine of a Return by Death story, and without it the
## loop is just a retry button.

label loop_confession_attempt:
    $ confided_attempt = True
    $ _cname = get_character_display_name(confidant)

    show screen cinema_letterbox
    scene bg parlor with fade
    set_music("atmos_short")
    pause 0.4

    "You find [_cname] before you have decided what you are going to say, which is how you know you are going to say it."

    if confidant == "marika":
        show marika neutral at sprite_standing with dissolve
    elif confidant == "elise":
        show elise neutral at sprite_standing with dissolve
    elif confidant == "vance":
        show vance neutral at sprite_standing with dissolve
    elif confidant == "hargrove":
        show hargrove neutral at sprite_standing with dissolve
    else:
        show odile neutral at sprite_standing with dissolve

    adrian "I need you to listen to me and not decide anything until I've finished."
    adrian "Tonight, after midnight, I am going to be killed in this house. I know because it has already happened."

    "You get that far."
    "You get exactly that far, and then your throat closes."

    play sound "audio/strain_burn.wav"
    set_music("death")
    with death_shake
    "It is not fear. Fear you could push through. This is a hand, cold and unhurried, closing on the inside of your windpipe — the same hand, the same patience, the one from the dark."
    death_narrator "\"Not that.\""
    "The cracks on your arm go white-hot. The room tilts. Somewhere very far away, someone is saying your name."

    pause 0.8
    scene black with Dissolve(0.5)
    pause 0.5
    scene bg parlor with Dissolve(0.5)

    "You are on one knee on the carpet with no memory of getting there."

    if confidant == "marika":
        show marika tearful at sprite_standing
        marika_char "Adrian — Adrian, breathe, you're grey, you're actually grey —"
        marika_char "What did you just try to tell me? You said you were going to be — "
        show marika sad at sprite_standing
        marika_char "...You've stopped. Why have you stopped?"
        adrian "...Nothing. It was nothing. I didn't sleep."
        show marika tearful at sprite_standing
        marika_char "Don't. Don't do the thing where you look after me instead of answering."
    elif confidant == "elise":
        show elise distressed at sprite_standing
        elise_char "Adrian. Adrian, look at me. Get up off the floor — Hargrove! "
        adrian "Don't call him. I'm all right. I'm all right, it's passing."
        show elise angry at sprite_standing
        elise_char "You said you were going to be killed. In my house. Tonight."
        show elise distressed at sprite_standing
        elise_char "That is the head injury talking and I will have Vance double your dose, and you will let me, because I cannot do this twice in one year."
    elif confidant == "vance":
        show vance clinical at sprite_standing
        vance_char "Down. All the way down, on your side. Don't argue with me."
        "Her fingers are at your throat, then your pulse, and her face does something it has not done before."
        vance_char "Your airway closed. There is nothing in your airway."
        show vance talking at sprite_standing
        vance_char "Adrian, people with temporal injuries get convictions. Certainties. They feel exactly like memories and they are not."
        vance_char "Whatever you were about to tell me — I need you to hold it very loosely."
    elif confidant == "hargrove":
        show hargrove grave at sprite_standing
        hargrove_char "Sir — young master — here, my arm, take my arm."
        "The old man is on the floor beside you before you can stop him, and his hands are shaking worse than yours."
        hargrove_char "You said you were to be killed tonight."
        show hargrove talking at sprite_standing
        hargrove_char "I have served this family through two wars and a great deal of shouting, and I have never once heard a Blackwood say a thing like that and be wrong."
        hargrove_char "But look at the state of you. Whatever it is, sir, it will not have you tonight. I shall be awake."
    else:
        show odile nervous at sprite_standing
        odile_char "Sir! Oh — oh sir, your hands, let me — "
        "She has her apron under your head before she has thought about whether she is allowed to."
        odile_char "You said someone's going to — "
        show odile talking at sprite_standing
        odile_char "I'll not repeat it. I'll not say a word of it to anyone, I swear it on my mother."
        odile_char "But I'll be listening tonight, sir. I'll be on the back stair and I will be listening."

    thought "They cannot be told. Something in this house will not permit it, and it will take my throat out through the front to make the point."
    thought "Whatever is left to do tonight, I do it on my own."

    pause 0.6
    hide screen cinema_letterbox
    jump day2_morning_transition

################################################################################
## Endings (Cinematic)
################################################################################
label ending_victory:
    hide screen hud
    show screen cinema_letterbox
    set_music("ending")
    $ k = run_state.killer
    $ ag = run_state.agenda
    $ kname = get_character_display_name(k)
    python:
        fb_data = get_fallback_data()
        epilogue_line = fb_data.get("epilogues", {}).get(ag, {}).get(k, "The killer goes down, and the truth comes up out of them like water out of a broken pipe.")
        victory_coda_line = fb_data.get("victory_coda", "The knot in the night comes untied. Morning arrives, and keeps arriving.")

    scene bg parlor with fade
    "The report is still ringing off the panelling. Gunsmoke drifts up through the lamplight, unhurried, as though it has all night."

    # The killer, bloodied
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

    thought "There it is. Said out loud, in this room, by that mouth."
    thought "I have wanted it for so many nights that I forgot to work out what I would feel when I had it."

    "[kname] goes down slowly, with the terrible dignity of someone who has run out of reasons to keep standing."

    pause 0.8
    scene black with fade
    pause 1.0

    # The loop lets go.
    play sound "audio/loop_snap.wav"
    "And then — nothing happens."
    "No lurch. No white. No bed, no seven o'clock, no fifth stroke of the clock coming in slightly flat."
    "The night simply goes on being the same night."

    scene bg parlor_night with Dissolve(1.2)
    "You stand in the quiet with the revolver getting cold in your hand and let the minutes do what minutes are supposed to do."

    "The marks on your arm fade while you are watching them. Not quickly. Like frost going off a window."

    # The person who got closest, if anyone did.
    if confidant is not None:
        $ cname2 = get_character_display_name(confidant)
        "Someone is in the doorway. [cname2] has been standing there long enough to have seen most of it."
        if confidant == k:
            thought "Of course. Of course it was."
            thought "I shot the only person in this house who ever told me the truth, and they told me the truth because they had already decided I would not live to repeat it."
            "You do not look at the doorway again. There is nobody in it."
        else:
            if confidant == "marika":
                show marika tearful at sprite_right with dissolve
                marika_char "You knew. All day you knew, and you couldn't — that's what you were trying to say to me."
                adrian "Yes."
                show marika calm at sprite_right
                marika_char "Then I'm going to spend a very long time being angry with you, and I'd like to start tomorrow, if that's all right."
            elif confidant == "elise":
                show elise distressed at sprite_right with dissolve
                elise_char "I had Vance double your dose. I told you it was the injury."
                adrian "You were being kind."
                show elise somber at sprite_right
                elise_char "I was being comfortable."
                elise_char "...Come away from there, Adrian. Please. Come away."
                thought "She has not called me brother. She has called me Adrian, and she has said please."
            elif confidant == "vance":
                show vance neutral at sprite_right with dissolve
                vance_char "Sit down before you fall down. No — there. The light's better."
                "She takes your pulse with the gun still in your other hand, which is either enormous professionalism or shock, and you decide not to ask which."
                vance_char "A hundred and forty. Under the circumstances, I'll allow it."
            elif confidant == "hargrove":
                show hargrove grave at sprite_right with dissolve
                hargrove_char "I said I should be awake, sir. I was awake. I was simply on the wrong stair."
                adrian "You couldn't have known."
                show hargrove talking at sprite_right
                hargrove_char "Forty-one years in this hall, young master, and the one night it mattered I was on the wrong stair."
                hargrove_char "Give me the revolver. There's a good lad. Give it here and come and sit down."
            else:
                show odile nervous at sprite_right with dissolve
                odile_char "I was listening, sir. Like I said I would. I was on the back stair the whole night."
                adrian "You heard it."
                show odile talking at sprite_right
                odile_char "I heard you say their name, sir. And then I heard the shot, and then I heard you breathing."
                odile_char "That last part was the good part."
    else:
        thought "Nobody comes. The house takes a long time to notice anything."
        thought "I did this alone, and I will have to be the one who explains it, and there is no one here who would have believed me beforehand."

    pause 0.8
    scene black with fade
    pause 1.0

    "[victory_coda_line]"
    pause 1.5

    centered "{size=40}{color=#f2c98a}THE LOOP ENDS{/color}{/size}\n\n{size=23}{color=#c9b9a2}You named the killer, you lived to see the morning,\nand the clock in the stairwell struck seven only once.{/color}{/size}"
    pause 4.5
    hide screen cinema_letterbox
    return


label ending_swallowed:
    hide screen hud
    show screen cinema_letterbox
    stop_ambience(fade=1.0)
    set_music("game_over")
    play sound "audio/loop_snap.wav"
    scene white with Dissolve(2.0)
    python:
        fb_data = get_fallback_data()
        swallowed_text = fb_data.get("swallowed_ending", "The loop closes over the place where you were and does not leave a mark.")

    "The cracks finish what they have been doing since the first night."
    "They do not hurt. That is the part nobody warns you about — at the end it does not hurt at all."

    "The hallway goes first, then the stairs, then the particular flatness of the fifth stroke of seven o'clock."
    "Then Marika at the gate in the rain. Then an old man insisting on a second bowl of broth. Then a girl on the back stair, listening."
    "Then your mother's hand flat against a dashboard."
    "Then the shape of your own name."

    "[swallowed_text]"
    pause 1.5

    scene black with Dissolve(2.0)
    # The clock bed under the last few lines, after the white-out.
    set_music("clock")
    sfx_sting("static")
    "Somewhere below, a clock strikes seven."
    "In an upstairs room, a bed is made, and has been for some time, and nobody in the house can quite remember who it was for."

    pause 2.0
    centered "{size=40}{color=#b02a2a}THE LOOP CLOSES{/color}{/size}\n\n{size=23}{color=#8c7a69}You died more times than you had left.\nBlackwood Manor keeps what it is given.{/color}{/size}"
    pause 4.5
    hide screen cinema_letterbox
    return
