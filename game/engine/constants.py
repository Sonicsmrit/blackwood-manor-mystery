"""Return by Death Manor - Constants"""

PLAYER_NAME = "Adrian"
DAYS = [1, 2]
SLOTS = ["morning", "afternoon", "evening"]
LOCATIONS = ["parlor", "study", "kitchen", "upstairs", "gate"]
ACTIONS_PER_SLOT = 2
CONVO_MAX_TURNS = 5
MAX_STRAIN = 3
TRUST_MIN = 0
TRUST_MAX = 3
CHARACTERS = ["marika", "elise", "vance", "hargrove", "odile"]
TOPICS = ["routine", "house", "adrian", "crash"]

# Base locations for characters (their belongings)
BASE_LOCATIONS = {
    "marika": "gate",
    "elise": "upstairs",
    "vance": "upstairs",
    "hargrove": "kitchen",
    "odile": "parlor"
}

# Agendas specification
#
# `motive` is authored per (agenda, killer) so an agenda's motive can diverge
# per character. Today only `inheritance` needs a per-character entry: its
# generic wording names Elise as a victim, so it cannot be used when Elise is
# the killer -- it would tell her she profits from her own death.
#
# `cause`, `slip_keywords` and `finding` stay shared per agenda.
AGENDAS = {
    "inheritance": {
        "cause": "brakes_cut",
        "slip_keywords": ["brake"],
        "finding": "forged_will",
        "motive": {
            "marika": "They profit if Adrian and Elise die.",
            "elise": "With Adrian dead, the house is theirs alone and nothing is left to disinherit.",
            "vance": "They profit if Adrian and Elise die.",
            "hargrove": "They profit if Adrian and Elise die.",
            "odile": "They profit if Adrian and Elise die.",
        }
    },
    "cover_up": {
        "cause": "drugged_driver",
        "slip_keywords": ["drink", "drug"],
        "finding": "altered_records",
        "motive": {
            "marika": "Adrian's returning memory would expose what they did.",
            "elise": "Adrian's returning memory would expose what they did.",
            "vance": "Adrian's returning memory would expose what they did.",
            "hargrove": "Adrian's returning memory would expose what they did.",
            "odile": "Adrian's returning memory would expose what they did.",
        }
    },
    "obsession": {
        "cause": "forced_off_road",
        "slip_keywords": ["another car", "off the road", "ran them"],
        "finding": "scratched_photos",
        "motive": {
            "marika": "They want Adrian here and will remove anyone who threatens that.",
            "elise": "They want Adrian here and will remove anyone who threatens that.",
            "vance": "They want Adrian here and will remove anyone who threatens that.",
            "hargrove": "They want Adrian here and will remove anyone who threatens that.",
            "odile": "They want Adrian here and will remove anyone who threatens that.",
        }
    }
}


def get_motive(agenda: str, killer: str) -> str:
    """The killer's private motive for this run.

    Falls back to any available entry rather than raising, so an incomplete
    table degrades to bland text instead of breaking a run mid-scene.
    """
    motives = AGENDAS.get(agenda, {}).get("motive", {})
    if isinstance(motives, str):
        return motives
    return motives.get(killer) or next(iter(motives.values()), "")

# Available decoy secrets per character
DECOY_SECRETS = {
    "marika": ["lingering", "unsent_letters"],
    "elise": ["night_visits", "diary"],
    "vance": ["phone_calls", "skimming_pills"],
    "hargrove": ["pawned_watch", "drinking"],
    "odile": ["stolen_silver", "eavesdropping"]
}

# Death fragments specification (grouped: staff = hargrove, vance, odile; kin = elise, marika)
DEATH_FRAGMENTS = {
    "hargrove": {
        "sound": "a slow pocket-watch tick",
        "smell": "starch and beeswax",
        "sight": "a white cuff on a dark sleeve"
    },
    "vance": {
        "sound": "a wristwatch tick and squeaking soles",
        "smell": "iodine and starched linen",
        "sight": "a white cuff on a grey sleeve"
    },
    "elise": {
        "sound": "a lullaby hummed off-key",
        "smell": "lavender soap",
        "sight": "a ribbon trailing in the dark"
    },
    "marika": {
        "sound": "a hymn hummed, faintly bell-like",
        "smell": "lavender and rain",
        "sight": "long pale-gold hair falling across your face"
    },
    "odile": {
        "sound": "a jangle of keys",
        "smell": "lemon polish and starch",
        "sight": "a white lace cap in the dark"
    }
}
