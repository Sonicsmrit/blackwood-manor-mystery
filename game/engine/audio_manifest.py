"""Audio asset manifest.

The game ships 31 curated tracks, copied out of the shdemo-*.zip archives that
sat at the project root and named for what they do rather than for the archive
id they arrived as. `tools/extract_audio.py` built a contact sheet to audition
them; these are the ones that were picked.

Paths are relative to the game directory, which is what Ren'Py's renpy.sound /
renpy.music expect. Kept in a .py rather than a .rpy so tests/test_engine.py can
import and assert against it without booting the engine -- the same reasoning as
bridge.py, which exists so the notebook's claim formatting is testable.

Nothing here decides *when* anything plays. That lives in script.rpy.
"""

# ── Music beds. Loop for anything that outlives a scene; the long beds
#    (clock, death, ending) are the ones that will repeat within a session.
MUSIC = {
    # Title menu. config.main_menu_music picks `title`; `title_alt` is held
    # back as the lead-in to the victory ending.
    "title": "audio/music/title.ogg",
    "title_alt": "audio/music/title_alt.ogg",

    # Day 1 and Day 2, by time of day.
    "atmos_general": "audio/music/atmos_general.ogg",
    "atmos_low": "audio/music/atmos_low.ogg",
    "atmos_short": "audio/music/atmos_short.ogg",
    "night": "audio/music/night.ogg",

    # Kitchen, entered often enough to want its own bed.
    "kitchen": "audio/music/kitchen.ogg",
    "kitchen_alt": "audio/music/kitchen_alt.ogg",

    # Strain 3 is ten seconds and is played once, never looped.
    "strain3": "audio/music/strain3.ogg",

    # Fail states and the moment of being killed.
    "game_over": "audio/music/game_over.ogg",
    "death": "audio/music/death.ogg",
    "death_atmos": "audio/music/death_atmos.ogg",

    # Suspense while aiming, and the last evening.
    "suspense": "audio/music/suspense.ogg",
    "evening_final": "audio/music/evening_final.ogg",

    # A long clock bed for the seven o'clock scenes, and the ending song.
    "clock": "audio/music/clock.ogg",
    "ending": "audio/music/ending.ogg",

    # Fires on roughly a quarter of Elise's Day 2 lines.
    "elise_day2": "audio/music/elise_day2.ogg",
}

# ── Ambience and stingers. One-shot unless listed in loop_forever.
AMBIENCE = {
    # The only real bed in the set: 26s of wind for the thunderstorm scenes.
    "storm_wind": "audio/ambience/storm_wind.ogg",
    "storm_sting": "audio/ambience/storm_sting.ogg",

    # Narrative punctuation.
    "return_by_death": "audio/ambience/return_by_death.ogg",
    "body_thud": "audio/ambience/body_thud.ogg",
    "wrong": "audio/ambience/wrong.ogg",
    "evening_bell": "audio/ambience/evening_bell.ogg",
    "static": "audio/ambience/static.ogg",
    "piano": "audio/ambience/piano.ogg",
}

# ── The silence pool.
#
# These six are near-identical in role: atmospheric texture, no fixed home. They
# are played at random when the house has been quiet for IDLE_AMBIENCE_AFTER
# seconds, so the silence between lines is never quite empty. They are never
# pinned to a scene.
AMBIENT_POOL = [
    "audio/ambience/atm_01.ogg",
    "audio/ambience/atm_02.ogg",
    "audio/ambience/atm_03.ogg",
    "audio/ambience/atm_04.ogg",
    "audio/ambience/atm_05.ogg",
    "audio/ambience/atm_06.ogg",
]

# ── The eight original synthesized effects stay. They are procedural, they
#    always load, and nothing in the curated set is unambiguously better for a
#    UI click. Indexed here only so tests can prove every name resolves.
LEGACY_SFX = {
    "clock_tick": "audio/clock_tick.wav",
    "gunshot": "audio/gunshot.wav",
    "heartbeat": "audio/heartbeat.wav",
    "loop_snap": "audio/loop_snap.wav",
    "revolver_cock": "audio/revolver_cock.wav",
    "select": "audio/select.wav",
    "strain_burn": "audio/strain_burn.wav",
    "thunder": "audio/thunder.wav",
}

# ── Tuning. These were guesses; adjust after a playthrough.
#
# Music has to sit under the voice blips, which play on every single line, so it
# runs well below them. Ambience is quieter still -- it is texture, not content.
VOLUME_MUSIC = 0.55
VOLUME_AMBIENCE = 0.35
VOLUME_STINGER = 1.0

# How long the house must be quiet before the pool gets a turn, and how long
# after a pool track before another is allowed. The voice blip channel plays on
# every line and loops for 1.8s, so silence is rare during conversation -- the
# pool lands in the gaps and on the non-conversation screens instead.
IDLE_AMBIENCE_AFTER = 12.0
AMBIENCE_COOLDOWN = 45.0

# Crossfades, in seconds.
FADE_SHORT = 1.0
FADE_LONG = 2.5

# `storm_wind` is 26s of weather and the only ambience that loops; everything
# else in AMBIENCE is a single hit.
AMBIENCE_LOOPING = {"storm_wind"}


def all_tracks():
    """Every path the manifest claims, for existence checks."""
    paths = list(MUSIC.values())
    paths += list(AMBIENCE.values())
    paths += list(AMBIENT_POOL)
    paths += list(LEGACY_SFX.values())
    return paths


def music_volume_track():
    return MUSIC["title"]