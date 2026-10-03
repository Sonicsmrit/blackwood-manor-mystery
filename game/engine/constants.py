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
AGENDAS = {
    "inheritance": {
        "cause": "brakes_cut",
        "slip_keywords": ["brake"],
        "finding": "forged_will",
        "motive": "They profit if Adrian and Elise die."
    },
    "cover_up": {
        "cause": "drugged_driver",
        "slip_keywords": ["drink", "drug"],
        "finding": "altered_records",
        "motive": "Adrian's returning memory would expose what they did."
    },
    "obsession": {
        "cause": "forced_off_road",
        "slip_keywords": ["another car", "off the road", "ran them"],
        "finding": "scratched_photos",
        "motive": "They want Adrian here and will remove anyone who threatens that."
    }
}

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
