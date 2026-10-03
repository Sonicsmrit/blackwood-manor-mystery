"""Return by Death Manor - Contradiction & Conflict Engine"""

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

    # 2. Presence conflicts: Routine claim vs observed absence / deviation
    # Routine claim: "claim:{char}:routine"
    # Absence fact: "presence:absence:{char}:{claimed_loc}:{slot}:{day}"
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

        # Also if seen somewhere other than their claimed routine on Day 2
        if fid.startswith("presence:deviation:"):
            parts = fid.split(":")
            if len(parts) >= 6:
                char = parts[2]
                routine_fact_id = f"claim:{char}:routine"
                if routine_fact_id in known_fact_ids:
                    pair = tuple(sorted([routine_fact_id, fid]))
                    if pair not in conflicts:
                        conflicts.append(pair)

    return sorted(conflicts)
