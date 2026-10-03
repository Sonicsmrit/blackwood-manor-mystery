"""Return by Death Manor - Trust & Conversation Mechanics"""

import random
from typing import List, Set, Dict, Any, Optional
from .constants import TRUST_MIN, TRUST_MAX, TOPICS, CONVO_MAX_TURNS
from .facts import Fact, get_available_facts
from .state import GameState, RunState

def generate_intents(char: str, trust: int, known_facts: Set[str], all_facts: List[Fact], turn_number: int, max_turns: int = CONVO_MAX_TURNS, rng: Optional[random.Random] = None) -> List[str]:
    """
    Generate exactly 4 choice intents for a conversation turn.
    Rules:
    - 1-2 probe:<topic> for topics with unrevealed facts (prioritize exclusive facts)
    - 1 comfort
    - 1 press (if gated topic exists and trust < gate) else small_talk
    - From turn 3 onward: always include leave (replaces small_talk/press)
    """
    if rng is None:
        rng = random.Random()

    intents: List[str] = []
    
    # 1. Determine unrevealed topics for this character
    unrevealed_topics = []
    exclusive_topics = []
    
    for topic in TOPICS:
        # Check facts for this char and topic
        topic_facts = [f for f in all_facts if f.char == char and f.topic == topic and f.gate.get("via") == "talk"]
        unlearned = [f for f in topic_facts if f.id not in known_facts]
        if unlearned:
            unrevealed_topics.append(topic)
            if any(f.exclusive for f in unlearned):
                exclusive_topics.append(topic)

    # Pick 1 or 2 probe intents
    probe_picks = []
    # Always include exclusive topic first if available
    for et in exclusive_topics:
        probe_picks.append(f"probe:{et}")
        
    for ut in unrevealed_topics:
        probe_intent = f"probe:{ut}"
        if probe_intent not in probe_picks and len(probe_picks) < 2:
            probe_picks.append(probe_intent)
            
    # If no unrevealed topics remain, pick from general topics
    if not probe_picks:
        probe_picks.append(f"probe:{rng.choice(TOPICS)}")
        
    intents.extend(probe_picks)
    
    # 2. Comfort (always 1)
    intents.append("comfort")
    
    # 3. Press or Small Talk
    # Check if there is a gated fact where trust < min_trust
    gated_facts = [f for f in all_facts if f.char == char and f.gate.get("via") == "talk" and f.gate.get("min_trust", 0) > trust and f.id not in known_facts]
    if gated_facts and trust > 0:
        intents.append("press")
    else:
        intents.append("small_talk")
        
    # 4. Leave button (turn 3 and later)
    if turn_number >= 3:
        if "leave" not in intents:
            if "small_talk" in intents:
                intents[intents.index("small_talk")] = "leave"
            elif "press" in intents:
                intents[intents.index("press")] = "leave"
            elif len(intents) >= 4:
                intents[3] = "leave"
            else:
                intents.append("leave")

    # Pad to exactly 4 if needed
    fallbacks = ["small_talk", "comfort", f"probe:{TOPICS[0]}", "leave"]
    idx = 0
    while len(intents) < 4:
        cand = fallbacks[idx % len(fallbacks)]
        if cand not in intents:
            intents.append(cand)
        idx += 1

    # Truncate if somehow > 4
    intents = intents[:4]
    
    # Shuffle so order isn't static
    rng.shuffle(intents)
    return intents

def apply_intent(intent: str, char: str, game_state: GameState, run_state: RunState, all_facts: List[Fact]) -> Dict[str, Any]:
    """
    Process chosen intent against character trust and fact gates.
    Updates game_state accordingly.
    """
    current_trust = game_state.trust.get(char, 0)
    revealed_facts: List[Fact] = []
    trust_delta = 0
    deflected = False
    lockout = False
    end_conversation = False
    mood = "calm"

    if intent == "leave":
        end_conversation = True
        return {
            "intent": intent,
            "trust_delta": 0,
            "new_trust": current_trust,
            "revealed_facts": [],
            "deflected": False,
            "lockout": False,
            "end_conversation": True,
            "mood": "neutral"
        }

    elif intent == "comfort":
        trust_delta = +1
        new_trust = min(TRUST_MAX, current_trust + 1)
        game_state.trust[char] = new_trust
        mood = "shy" if char == "marika" else "calm"

    elif intent == "small_talk":
        trust_delta = 0
        new_trust = current_trust
        mood = "neutral"

    elif intent == "press":
        if current_trust <= 0:
            # Lockout! Character refuses to speak for the rest of the slot
            lockout = True
            end_conversation = True
            game_state.locked_out.add(char)
            trust_delta = 0
            new_trust = 0
            mood = "angry"
        else:
            # Reveal gated facts if trust >= min_trust - 1
            trust_delta = -1
            new_trust = max(TRUST_MIN, current_trust - 1)
            game_state.trust[char] = new_trust
            
            # Find eligible gated facts
            gated = [f for f in all_facts if f.char == char and f.gate.get("via") == "talk" and f.id not in game_state.known_facts]
            for f in gated:
                if current_trust >= f.gate.get("min_trust", 0) - 1:
                    revealed_facts.append(f)
                    game_state.known_facts.add(f.id)
                    game_state.notebook_entries.append(f.id)
                    game_state.facts_revealed_this_loop.add(f.id)
                    break
            mood = "angry"

    elif intent.startswith("probe:"):
        topic = intent.split(":", 1)[1]
        available = get_available_facts(char, topic, current_trust, game_state.known_facts, all_facts)
        new_facts = [f for f in available if f.id not in game_state.known_facts]
        
        if new_facts:
            # Prioritize exclusive facts
            exclusive = [f for f in new_facts if f.exclusive]
            to_reveal = exclusive[0] if exclusive else new_facts[0]
            revealed_facts.append(to_reveal)
            game_state.known_facts.add(to_reveal.id)
            game_state.notebook_entries.append(to_reveal.id)
            game_state.facts_revealed_this_loop.add(to_reveal.id)
            mood = "sly" if to_reveal.exclusive else "neutral"
        else:
            # Deflection
            deflected = True
            mood = "apologetic"
        new_trust = current_trust

    else:
        new_trust = current_trust

    return {
        "intent": intent,
        "trust_delta": trust_delta,
        "new_trust": new_trust,
        "revealed_facts": revealed_facts,
        "deflected": deflected,
        "lockout": lockout,
        "end_conversation": end_conversation,
        "mood": mood
    }
