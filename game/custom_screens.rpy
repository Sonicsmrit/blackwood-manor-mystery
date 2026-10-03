## Return by Death Manor - Custom Screens and UI
init offset = 1

init python:
    def character_has_conflict(char_id, conflicts, facts):
        for pair in conflicts:
            f1 = next((f for f in facts if f.id == pair[0]), None)
            f2 = next((f for f in facts if f.id == pair[1]), None)
            if (f1 and f1.char == char_id) or (f2 and f2.char == char_id):
                return True
        return False

################################################################################
## HUD Screen (Always visible during investigation)
################################################################################
screen hud():
    zorder 100
    frame:
        xalign 0.5
        yalign 0.02
        background "#11141acc"
        xpadding 25
        ypadding 12
        has hbox:
            spacing 30
            align (0.5, 0.5)

            # Loop indicator
            hbox:
                spacing 5
                text "LOOP [game_state.loop_no]" size 22 bold True color "#e0e0e0"

            # Time indicator
            hbox:
                spacing 5
                text "Day [game_state.current_day] • [game_state.current_slot.upper()]" size 22 color "#66c1e0"

            # Actions left
            hbox:
                spacing 5
                text "Actions Left:" size 20 color "#aaaaaa"
                text "[game_state.slot_actions_remaining]" size 22 bold True color "#ffffff"

            # Strain arm indicator (Pips)
            hbox:
                spacing 6
                text "Strain:" size 20 color "#aaaaaa"
                $ strain_val = game_state.strain
                hbox:
                    spacing 4
                    for i in range(1, 4):
                        if i <= strain_val:
                            text "●" size 24 color "#ff3333"
                        else:
                            text "○" size 24 color "#555555"

            # Revolver bullet indicator
            hbox:
                spacing 6
                text "Revolver:" size 20 color "#aaaaaa"
                if game_state.bullet_available:
                    text "● Loaded" size 20 bold True color "#ffd700"
                else:
                    text "○ Spent" size 20 color "#777777"

            # Notebook button
            textbutton "📓 Notebook" action Show("notebook") text_size 20 text_color "#ffffff" text_hover_color "#66c1e0"

################################################################################
## Location Selection Screen
################################################################################
screen location_picker(locations_data):
    modal True
    zorder 90
    frame:
        xalign 0.5
        yalign 0.5
        xsize 900
        ysize 580
        background "#181c24fa"
        xpadding 40
        ypadding 30

        vbox:
            spacing 20
            xfill True

            text "CHOOSE LOCATION" size 30 bold True color "#ffffff" xalign 0.5
            text "Slot: Day [game_state.current_day] - [game_state.current_slot.upper()]" size 20 color "#888888" xalign 0.5

            null height 10

            vbox:
                spacing 14
                xfill True
                for loc_id, present in locations_data.items():
                    $ loc_name = get_location_display_name(loc_id)
                    $ names_str = ", ".join([get_character_display_name(c) for c in present]) if present else "Quiet (empty)"
                    button:
                        xfill True
                        ypadding 12
                        xpadding 20
                        background "#252b38"
                        hover_background "#354054"
                        action Return(loc_id)
                        hbox:
                            xfill True
                            text "[loc_name]" size 24 bold True color "#66c1e0"
                            text "Present: [names_str]" size 20 color "#cccccc" xalign 1.0

################################################################################
## Action Picker Screen (At current location)
################################################################################
screen action_picker(current_loc, present_chars, actions_left, current_day, bullet_avail):
    modal True
    zorder 90
    $ loc_title = get_location_display_name(current_loc)
    frame:
        xalign 0.5
        yalign 0.5
        xsize 900
        ysize 580
        background "#181c24fa"
        xpadding 40
        ypadding 30

        vbox:
            spacing 20
            xfill True

            text "[loc_title]" size 32 bold True color "#ffffff" xalign 0.5
            text "Actions remaining this slot: [actions_left]" size 20 color "#888888" xalign 0.5

            null height 10

            vbox:
                spacing 14
                xfill True

                # Talk actions for present characters
                for char in present_chars:
                    $ cname = get_character_display_name(char)
                    $ is_locked = char in game_state.locked_out
                    $ already_talked = char in game_state.conversations_this_slot
                    if is_locked:
                        button:
                            xfill True
                            ypadding 10
                            xpadding 20
                            background "#222222"
                            action NullAction()
                            text "Talk to [cname] (Refuses to speak right now)" size 22 color "#666666"
                    elif already_talked:
                        button:
                            xfill True
                            ypadding 10
                            xpadding 20
                            background "#222222"
                            action NullAction()
                            text "Talk to [cname] (Already spoke this slot)" size 22 color "#666666"
                    else:
                        button:
                            xfill True
                            ypadding 10
                            xpadding 20
                            background "#252b38"
                            hover_background "#354054"
                            action Return(("talk", char))
                            text "Talk to [cname]" size 22 color "#ffffff"

                # Search action
                button:
                    xfill True
                    ypadding 10
                    xpadding 20
                    background "#252b38"
                    hover_background "#354054"
                    action Return(("search", current_loc))
                    text "🔍 Search [loc_title]" size 22 color "#e0d080"

                # Shoot action (Day 2 only, bullet available, people present)
                if current_day == 2 and bullet_avail and present_chars:
                    button:
                        xfill True
                        ypadding 10
                        xpadding 20
                        background "#4a1c1c"
                        hover_background "#6e2525"
                        action Return(("shoot_menu", current_loc))
                        text "⚡ Draw Revolver (One Bullet)" size 22 color "#ff6666"

                # Leave / Pass action
                button:
                    xfill True
                    ypadding 10
                    xpadding 20
                    background "#1a1f29"
                    hover_background "#28303f"
                    action Return(("pass", None))
                    text "Wait / Pass Time" size 20 color "#888888"

################################################################################
## Shoot Target Picker
################################################################################
screen shoot_target_picker(present_chars):
    modal True
    zorder 95
    frame:
        xalign 0.5
        yalign 0.5
        xsize 700
        ysize 450
        background "#241010fa"
        xpadding 35
        ypadding 25

        vbox:
            spacing 20
            xfill True

            text "DRAW REVOLVER" size 30 bold True color "#ff4444" xalign 0.5
            text "Aim at whom? You have only ONE bullet." size 20 color "#dddddd" xalign 0.5

            null height 10

            vbox:
                spacing 12
                xfill True
                for char in present_chars:
                    $ cname = get_character_display_name(char)
                    button:
                        xfill True
                        ypadding 10
                        xpadding 20
                        background "#3d1818"
                        hover_background "#5c2020"
                        action Return(char)
                        text "Fire at [cname]" size 22 bold True color "#ff9999"

                button:
                    xfill True
                    ypadding 10
                    xpadding 20
                    background "#1a1a1a"
                    hover_background "#2c2c2c"
                    action Return("cancel")
                    text "Lower the Gun (Cancel)" size 20 color "#aaaaaa"

################################################################################
## Shoot Confirmation Modal
################################################################################
screen shoot_confirm(target_name):
    modal True
    zorder 100
    frame:
        xalign 0.5
        yalign 0.5
        xsize 650
        ysize 380
        background "#1a0808fa"
        xpadding 35
        ypadding 30

        vbox:
            spacing 20
            xfill True

            text "CONFIRM SHOT" size 28 bold True color "#ff3333" xalign 0.5
            text "Are you certain you wish to shoot [target_name]?" size 22 color "#ffffff" xalign 0.5
            text "If you shoot an innocent person, night will fall with the real killer still walking these halls." size 18 color "#ffaaaa" xalign 0.5

            null height 15

            hbox:
                spacing 25
                xalign 0.5
                button:
                    xsize 220
                    ypadding 12
                    background "#661818"
                    hover_background "#992020"
                    action Return("shoot")
                    text "PULL TRIGGER" size 20 bold True color "#ffffff" xalign 0.5

                button:
                    xsize 220
                    ypadding 12
                    background "#2a2a2a"
                    hover_background "#444444"
                    action Return("cancel")
                    text "HESITATE" size 20 color "#cccccc" xalign 0.5

################################################################################
## Custom Conversation UI Screen
################################################################################
screen conversation_ui(char_name, char_color, npc_line, choices):
    zorder 80

    # NPC Line Box (Styled like gothic horror dialogue)
    frame:
        xalign 0.5
        yalign 0.68
        xsize 1300
        ysize 150
        background "#10141ce0"
        xpadding 30
        ypadding 20

        vbox:
            spacing 6
            text "[char_name]" size 24 bold True color "[char_color]"
            text "[npc_line]" size 22 color "#ffffff"

    # 4 Choice Buttons
    frame:
        xalign 0.5
        yalign 0.95
        xsize 1300
        ysize 170
        background "#0a0c12ee"
        xpadding 25
        ypadding 15

        grid 2 2:
            xfill True
            yfill True
            spacing 15

            for choice in choices:
                $ intent_label = choice["intent"]
                $ choice_text = choice["text"]
                button:
                    xfill True
                    yfill True
                    xpadding 15
                    ypadding 8
                    background "#1c2230"
                    hover_background "#2f3a52"
                    action Return(choice["intent"])
                    text "[choice_text]" size 20 color "#e0e8f0" hover_color "#66c1e0" yalign 0.5

################################################################################
## Notebook Screen (Tabs: Characters, Timeline, Findings, Deaths)
################################################################################
default notebook_tab = "characters"

screen notebook():
    modal True
    zorder 150
    frame:
        xalign 0.5
        yalign 0.5
        xsize 1500
        ysize 900
        background "#12151deb"
        xpadding 40
        ypadding 30

        vbox:
            spacing 15
            xfill True

            # Header with Tabs and Close Button
            hbox:
                xfill True
                text "ADRIAN'S NOTEBOOK" size 32 bold True color "#ffffff"

                hbox:
                    spacing 15
                    textbutton "Characters" action SetScreenVariable("notebook_tab", "characters") text_size 22 text_color ("#66c1e0" if notebook_tab == "characters" else "#888888")
                    textbutton "Timeline" action SetScreenVariable("notebook_tab", "timeline") text_size 22 text_color ("#66c1e0" if notebook_tab == "timeline" else "#888888")
                    textbutton "Findings" action SetScreenVariable("notebook_tab", "findings") text_size 22 text_color ("#66c1e0" if notebook_tab == "findings" else "#888888")
                    textbutton "Deaths" action SetScreenVariable("notebook_tab", "deaths") text_size 22 text_color ("#66c1e0" if notebook_tab == "deaths" else "#888888")

                textbutton "✕ Close" action Hide("notebook") text_size 24 text_color "#ff6666" xalign 1.0

            null height 5

            # Active Tab Content
            if notebook_tab == "characters":
                use notebook_characters_tab()
            elif notebook_tab == "timeline":
                use notebook_timeline_tab()
            elif notebook_tab == "findings":
                use notebook_findings_tab()
            elif notebook_tab == "deaths":
                use notebook_deaths_tab()

## Notebook Tab: Characters
screen notebook_characters_tab():
    $ conflicts_list = find_conflicts(game_state.known_facts, all_facts)
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 20
            xfill True

            for char in CHARACTERS:
                $ cname = get_character_display_name(char)
                $ ctrust = game_state.trust.get(char, 0)
                $ char_facts = [f for f in all_facts if f.char == char and f.id in game_state.known_facts]
                # Check if this character has active conflicts
                $ has_conflict = character_has_conflict(char, conflicts_list, all_facts)

                frame:
                    xfill True
                    background ("#241515" if has_conflict else "#1a202c")
                    xpadding 25
                    ypadding 18
                    vbox:
                        spacing 8
                        hbox:
                            xfill True
                            text "[cname]" size 24 bold True color ("#ff8888" if has_conflict else "#66c1e0")
                            text "Current Trust: [ctrust] / 3" size 20 color "#aaaaaa" xalign 1.0
                            if has_conflict:
                                text "  ⚠️ [CONTRADICTION DETECTED]" size 20 bold True color "#ff3333"

                        if char_facts:
                            vbox:
                                spacing 4
                                for f in char_facts:
                                    text "• [f.text]" size 18 color "#dddddd"
                        else:
                            text "• No statements recorded yet." size 18 italic True color "#777777"

## Notebook Tab: Timeline
screen notebook_timeline_tab():
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 15
            xfill True

            text "Observed Character Positions" size 24 bold True color "#66c1e0"

            # Table for Day 1 and Day 2
            for d in [1, 2]:
                frame:
                    xfill True
                    background "#1a202c"
                    xpadding 20
                    ypadding 15
                    vbox:
                        spacing 10
                        text "DAY [d]" size 22 bold True color "#ffffff"
                        for s in SLOTS:
                            $ s_upper = s.upper()
                            $ slot_obs = []
                            for c in CHARACTERS:
                                $ pres_key = f"presence:seen:{c}:{run_state.positions[c][str(d)][s]}:{s}:{d}"
                                if pres_key in game_state.known_facts:
                                    $ slot_obs.append(f"{get_character_display_name(c)} at {get_location_display_name(run_state.positions[c][str(d)][s])}")
                            $ obs_str = "; ".join(slot_obs) if slot_obs else "Unvisited or no records."
                            hbox:
                                xfill True
                                text "[s_upper]:" size 20 bold True color "#aaaaaa" xsize 180
                                text "[obs_str]" size 19 color "#dddddd"

## Notebook Tab: Findings
screen notebook_findings_tab():
    $ found_items = [f for f in all_facts if f.kind in ("finding", "world") and f.id in game_state.known_facts]
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 15
            xfill True

            text "Discovered Items & Documents" size 24 bold True color "#66c1e0"

            if found_items:
                for item in found_items:
                    frame:
                        xfill True
                        background "#1a202c"
                        xpadding 20
                        ypadding 12
                        vbox:
                            spacing 5
                            hbox:
                                text "📄 [item.id]" size 20 bold True color ("#ffd700" if item.exclusive else "#66c1e0")
                                if item.exclusive:
                                    text "  [CRUCIAL EVIDENCE]" size 18 bold True color "#ff4444"
                            text "[item.text]" size 19 color "#e0e0e0"
            else:
                text "No items discovered yet. Search locations while occupants are elsewhere." size 20 italic True color "#777777"

## Notebook Tab: Deaths
screen notebook_deaths_tab():
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 15
            xfill True

            text "Death Memories & Sensory Fragments" size 24 bold True color "#66c1e0"

            if game_state.fragments_seen:
                for idx, frag in enumerate(game_state.fragments_seen, 1):
                    frame:
                        xfill True
                        background "#241515"
                        xpadding 20
                        ypadding 14
                        vbox:
                            spacing 6
                            text "DEATH #[idx]" size 20 bold True color "#ff5555"
                            text "\"[frag]\"" size 20 italic True color "#ffffff"
            else:
                text "You have not died... yet." size 20 italic True color "#777777"
