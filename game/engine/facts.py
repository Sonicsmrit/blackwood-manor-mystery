"""Return by Death Manor - Fact Definitions and Fact Generation"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional
from .constants import CHARACTERS, BASE_LOCATIONS, AGENDAS, DECOY_SECRETS, DEATH_FRAGMENTS

@dataclass
class Fact:
    id: str
    kind: str  # "claim" | "finding" | "presence" | "fragment" | "world"
    char: Optional[str]
    topic: Optional[str]
    text_key: str
    text: str
    gate: Dict[str, Any]  # {"via": "talk"|"search"|"observe"|"death", "loc": str|None, "slot": str|None, "day": int|None, "min_trust": int}
    exclusive: bool = False
    conflicts_with: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "char": self.char,
            "topic": self.topic,
            "text_key": self.text_key,
            "text": self.text,
            "gate": self.gate,
            "exclusive": self.exclusive,
            "conflicts_with": self.conflicts_with
        }

def build_all_facts(run_state) -> List[Fact]:
    """Deterministically build all facts for the given RunState."""
    facts: List[Fact] = []
    killer = run_state.killer
    agenda = run_state.agenda
    cause = run_state.cause
    secrets = run_state.secrets

    # 1. World Facts (Search in study)
    facts.append(Fact(
        id="world:official_report",
        kind="world",
        char=None,
        topic=None,
        text_key="world.official_report",
        text="Coroner's report: Vehicle wreckage unexamined; cause of crash undetermined.",
        gate={"via": "search", "loc": "study", "slot": None, "day": None, "min_trust": 0},
        exclusive=False,
        conflicts_with=[]
    ))

    facts.append(Fact(
        id="world:hospital_letter",
        kind="world",
        char=None,
        topic=None,
        text_key="world.hospital_letter",
        text="St. Jude Hospital discharge note: Adrian admitted with cranial trauma following a road collision.",
        gate={"via": "search", "loc": "study", "slot": None, "day": None, "min_trust": 0},
        exclusive=False,
        conflicts_with=[]
    ))

    # 2. Character Claims (Routine, House, Adrian, Crash)
    routine_claims_text = {
        "marika": "Marika claims she waits by the gate mornings/evenings and rests in the parlor afternoons.",
        "elise": "Elise claims she remains upstairs mornings/evenings and works in the study afternoons.",
        "vance": "Vance claims she tends patients upstairs mornings/afternoons and dines in the kitchen evenings.",
        "hargrove": "Hargrove claims he oversees the kitchen mornings/evenings and attends the parlor afternoons.",
        "odile": "Odile claims she dusts the parlor mornings/evenings and prepares linens in the kitchen afternoons."
    }

    for char in CHARACTERS:
        # Routine claim (min_trust: 0)
        facts.append(Fact(
            id=f"claim:{char}:routine",
            kind="claim",
            char=char,
            topic="routine",
            text_key=f"routine.{char}",
            text=routine_claims_text[char],
            gate={"via": "talk", "loc": None, "slot": None, "day": None, "min_trust": 0},
            exclusive=False,
            conflicts_with=[]  # Absences that deviate will be checked in conflict engine
        ))

        # House lore claim (min_trust: 1)
        facts.append(Fact(
            id=f"claim:{char}:house",
            kind="claim",
            char=char,
            topic="house",
            text_key=f"house.{char}",
            text=f"{char.capitalize()} shared observations about the manor's layout and family history.",
            gate={"via": "talk", "loc": None, "slot": None, "day": None, "min_trust": 1},
            exclusive=False,
            conflicts_with=[]
        ))

        # Adrian backstory claim (min_trust: 1)
        facts.append(Fact(
            id=f"claim:{char}:adrian",
            kind="claim",
            char=char,
            topic="adrian",
            text_key=f"adrian.{char}",
            text=f"{char.capitalize()} described what Adrian was like before the accident.",
            gate={"via": "talk", "loc": None, "slot": None, "day": None, "min_trust": 1},
            exclusive=False,
            conflicts_with=[]
        ))

        # Crash claim:
        if char == killer:
            # Killer Slip (exclusive, min_trust: 2)
            slip_texts = {
                "brakes_cut": "States matter-of-factly that the car's brake lines were cut before the descent.",
                "drugged_driver": "States casually that father's drink had been drugged with a sedative before driving.",
                "forced_off_road": "Mentions as common knowledge that another car ran them off the road into the ravine."
            }
            facts.append(Fact(
                id=f"claim:{char}:crash",
                kind="claim",
                char=char,
                topic="crash",
                text_key=f"slip.{cause}",
                text=f"{char.capitalize()} let slip: {slip_texts[cause]}",
                gate={"via": "talk", "loc": None, "slot": None, "day": None, "min_trust": 2},
                exclusive=True,
                conflicts_with=["world:official_report"]
            ))
        else:
            # Innocent vague claim (min_trust: 2, matching the killer's slip).
            # Gating this at 1 instead of 2 made the crash topic reachable one
            # trust point earlier for innocents than for the killer, which the
            # choice generator would have surfaced as a tell. Same gate for
            # everyone means asking about the crash proves nothing on its own.
            facts.append(Fact(
                id=f"claim:{char}:crash",
                kind="claim",
                char=char,
                topic="crash",
                text_key=f"crash_vague.{char}",
                text=f"{char.capitalize()} recalled only that the crash was a terrible, tragic accident in the fog.",
                gate={"via": "talk", "loc": None, "slot": None, "day": None, "min_trust": 2},
                exclusive=False,
                conflicts_with=[]
            ))

    # 3. Findings at Base Locations
    # Killer Finding (exclusive)
    killer_base_loc = BASE_LOCATIONS[killer]
    killer_finding_desc = {
        "inheritance": "A forged will naming the killer as sole heir of the manor estate.",
        "cover_up": "Altered clinic records and a hidden vial of chloral hydrate sedative.",
        "obsession": "A box of personal photographs of Adrian, with other faces scratched away."
    }
    facts.append(Fact(
        id=f"finding:{killer}:{agenda}",
        kind="finding",
        char=killer,
        topic="finding",
        text_key=f"finding.killer.{agenda}",
        text=killer_finding_desc[agenda],
        gate={"via": "search", "loc": killer_base_loc, "slot": None, "day": None, "min_trust": 0},
        exclusive=True,
        conflicts_with=[]
    ))

    # Decoy Findings for Innocents (non-exclusive)
    decoy_finding_desc = {
        "lingering": "Muddy footprints and a folded blanket hidden by the stone gate post.",
        "unsent_letters": "A packet of unsent letters to Adrian's late parents in Marika's hand.",
        "night_visits": "Embroidered slippers by Adrian's door with a note: 'is he breathing?'.",
        "diary": "A torn diary page expressing a desperate urge to run away from the manor.",
        "phone_calls": "A secret call log with repeated calls to an unknown city number.",
        "skimming_pills": "Concealed blister packs of prescription sleeping pills.",
        "pawned_watch": "A pawn ticket for the family gold pocket watch.",
        "drinking": "A bottle of rye whiskey hidden behind sacks in the pantry.",
        "stolen_silver": "A silver heirloom ladle wrapped secretly in an apron.",
        "eavesdropping": "A drinking tumbler left against a floorboard outside the study."
    }

    for char, secret in secrets.items():
        if char != killer:
            base_loc = BASE_LOCATIONS[char]
            facts.append(Fact(
                id=f"finding:{char}:{secret}",
                kind="finding",
                char=char,
                topic="finding",
                text_key=f"finding.decoy.{secret}",
                text=decoy_finding_desc[secret],
                gate={"via": "search", "loc": base_loc, "slot": None, "day": None, "min_trust": 0},
                exclusive=False,
                conflicts_with=[]
            ))

    # 4. Death Fragments for the Killer
    # Group-shared clues pointing to the killer
    for cat in ["sound", "smell", "sight"]:
        fragment_text = DEATH_FRAGMENTS[killer][cat]
        facts.append(Fact(
            id=f"fragment:{cat}:{killer}",
            kind="fragment",
            char=killer,
            topic="fragment",
            text_key=f"fragment.{cat}.{killer}",
            text=fragment_text,
            gate={"via": "death", "loc": None, "slot": None, "day": None, "min_trust": 0},
            exclusive=True,
            conflicts_with=[]
        ))

    return facts

def get_available_facts(char: str, topic: str, trust: int, known_facts: Set[str], all_facts: List[Fact]) -> List[Fact]:
    """Find facts for char and topic that can be revealed at the current trust level."""
    available = []
    for fact in all_facts:
        if fact.char == char and fact.topic == topic and fact.gate.get("via") == "talk":
            if trust >= fact.gate.get("min_trust", 0):
                available.append(fact)
    return available

def get_search_findings(location: str, slot: str, day: int, positions: Dict[str, Dict[str, Dict[str, str]]], all_facts: List[Fact], present_chars: List[str]) -> List[Fact]:
    """
    Search findings at a location.
    Owner must NOT be present (watching rule).
    World facts in study can be found if no one is blocking or freely.
    """
    findings = []
    day_str = str(day)
    
    for fact in all_facts:
        if fact.kind in ("finding", "world"):
            if fact.gate.get("via") == "search" and fact.gate.get("loc") == location:
                # If fact belongs to a character, character must NOT be present
                if fact.char:
                    if fact.char not in present_chars:
                        findings.append(fact)
                else:
                    # World facts (e.g. study)
                    findings.append(fact)
    return findings
