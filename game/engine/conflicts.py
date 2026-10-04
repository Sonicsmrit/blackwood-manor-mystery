"""Return by Death Manor - Contradiction & Conflict Engine

Note on current use: nothing in the UI calls this any more. The notebook used to
paint a red "CONTRADICTS THEMSELF" badge off these pairs, which was worthless --
every character deviates from their routine exactly once, killer and innocent
alike, so the badge could fire on all five people at once and narrowed nothing.
The observed absence is now shown as a plain sentence on the Timeline tab, and
the conclusion is left to the player.

find_conflicts stays as engine API (and is spec'd in game_logic_spec.md 5.8), but
a test asserts that no .rpy screen references it, so the verdict cannot quietly
come back.
"""

from typing import Set, List, Tuple, Dict
from .facts import Fact

def find_conflicts(known_fact_ids: Set[str], all_facts: List[Fact]) -> List[Tuple[str, str]]:
    """
    Given the set of known fact IDs, identify all active contradictions.
    Returns list of (fact_id_A, fact_id_B) pairs.
    """
    conflicts: List[Tuple[str, str]] = []
    facts_by_id: Dict[str, Fact] = {f.id: f for f in all_facts}

    # 1. Explicit conflicts_with defined on facts
    for fid in known_fact_ids:
        fact = facts_by_id.get(fid)
        if fact and fact.conflicts_with:
            for conflict_id in fact.conflicts_with:
                if conflict_id in known_fact_ids:
                    pair = tuple(sorted([fid, conflict_id]))
                    if pair not in conflicts:
                        conflicts.append(pair)

    # 2. Presence conflicts: routine claim vs observed absence.
    #
    # Only the absence half of this ever fires. There was also a branch here for
    # "presence:deviation:" facts, but nothing has ever written one -- the
    # generator keeps deviations in its own position map rather than emitting a
    # fact ID, so that branch was dead. It is removed rather than left to imply
    # that a deviation is something the notebook could catch someone on, because
    # a deviation is not evidence: it is the fairness structure that guarantees
    # every innocent has an alibi-shaped excuse.
    for fid in known_fact_ids:
        if fid.startswith("presence:absence:"):
            parts = fid.split(":")
            if len(parts) >= 6:
                char = parts[2]
                routine_fact_id = f"claim:{char}:routine"
                if routine_fact_id in known_fact_ids:
                    pair = tuple(sorted([routine_fact_id, fid]))
                    if pair not in conflicts:
                        conflicts.append(pair)

    return sorted(conflicts)
