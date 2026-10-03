"""Return by Death Manor - State Models"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional
from .constants import ACTIONS_PER_SLOT, DAYS, SLOTS

@dataclass
class RunState:
    seed: int
    killer: str
    agenda: str
    cause: str
    secrets: Dict[str, str] = field(default_factory=dict)
    start_trust: Dict[str, int] = field(default_factory=dict)
    # positions: char -> day (str '1' or '2') -> slot ('morning'/'afternoon'/'evening') -> location
    positions: Dict[str, Dict[str, Dict[str, str]]] = field(default_factory=dict)
    facts: List[Any] = field(default_factory=list)
    fragment_order: List[str] = field(default_factory=lambda: ["smell", "sound", "sight"])
    hook: str = "Something about this house is wrong, and it already knows you."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "killer": self.killer,
            "agenda": self.agenda,
            "cause": self.cause,
            "secrets": self.secrets,
            "start_trust": self.start_trust,
            "positions": self.positions,
            "facts": [f.to_dict() if hasattr(f, "to_dict") else f for f in self.facts],
            "fragment_order": self.fragment_order,
            "hook": self.hook
        }

@dataclass
class GameState:
    current_day: int = 1
    current_slot: str = "morning"
    current_location: str = "parlor"
    loop_no: int = 1
    strain: int = 0
    wrong_kill: bool = False
    bullet_available: bool = True
    trust: Dict[str, int] = field(default_factory=dict)
    known_facts: Set[str] = field(default_factory=set)
    notebook_entries: List[str] = field(default_factory=list)
    facts_revealed_this_loop: Set[str] = field(default_factory=set)
    conversations_this_slot: Set[str] = field(default_factory=set)
    locked_out: Set[str] = field(default_factory=set)
    slot_actions_remaining: int = ACTIONS_PER_SLOT
    fragments_seen: List[str] = field(default_factory=list)
    target_shot: Optional[str] = None
    killer_shot: bool = False
    game_over: bool = False
    ending: Optional[str] = None  # "victory", "swallowed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_day": self.current_day,
            "current_slot": self.current_slot,
            "current_location": self.current_location,
            "loop_no": self.loop_no,
            "strain": self.strain,
            "wrong_kill": self.wrong_kill,
            "bullet_available": self.bullet_available,
            "trust": dict(self.trust),
            "known_facts": list(self.known_facts),
            "notebook_entries": list(self.notebook_entries),
            "facts_revealed_this_loop": list(self.facts_revealed_this_loop),
            "conversations_this_slot": list(self.conversations_this_slot),
            "locked_out": list(self.locked_out),
            "slot_actions_remaining": self.slot_actions_remaining,
            "fragments_seen": list(self.fragments_seen),
            "target_shot": self.target_shot,
            "killer_shot": self.killer_shot,
            "game_over": self.game_over,
            "ending": self.ending
        }

def new_game_state(run_state: RunState, start_day: int = 1) -> GameState:
    """Create a fresh GameState for a new playthrough."""
    return GameState(
        current_day=start_day,
        current_slot="morning",
        current_location="parlor",
        loop_no=1,
        strain=0,
        wrong_kill=False,
        bullet_available=(start_day == 2),
        trust=dict(run_state.start_trust),
        known_facts=set(),
        notebook_entries=[],
        facts_revealed_this_loop=set(),
        conversations_this_slot=set(),
        locked_out=set(),
        slot_actions_remaining=ACTIONS_PER_SLOT,
        fragments_seen=[]
    )

def reset_loop(game_state: GameState, run_state: RunState) -> GameState:
    """
    Apply Return by Death reset.
    Kept: notebook, all known facts, strain, loop_no (incremented), fragments_seen.
    Reset: day to 2, slot to morning, trust to start_trust, bullet restored,
           wrong_kill cleared, NPC states/lockout cleared.
    """
    new_loop_no = game_state.loop_no + 1
    return GameState(
        current_day=2,
        current_slot="morning",
        current_location="parlor",
        loop_no=new_loop_no,
        strain=game_state.strain,
        wrong_kill=False,
        bullet_available=True,
        trust=dict(run_state.start_trust),
        known_facts=set(game_state.known_facts),
        notebook_entries=list(game_state.notebook_entries),
        facts_revealed_this_loop=set(),
        conversations_this_slot=set(),
        locked_out=set(),
        slot_actions_remaining=ACTIONS_PER_SLOT,
        fragments_seen=list(game_state.fragments_seen),
        target_shot=None,
        killer_shot=False,
        game_over=False,
        ending=None
    )
