## Return by Death Manor - Custom Screens and UI
##
## All colour, type, and chrome comes from theme.rpy. Nothing here should
## hardcode a hex value -- if a new shade is needed, add it to the palette.

init offset = 1

## How long conversation choices ignore input after they appear.
##
## These buttons are drawn inside the say textbox, so the click that dismisses
## Adrian's line lands on them the instant the next choice set appears. Without
## a short arming window that click silently picks a choice.
define CHOICE_ARM_DELAY = 0.18

init python:
    import time

    def character_has_conflict(char_id, conflicts, facts):
        facts_by_id = {}
        for f in facts:
            facts_by_id[f.id] = f
        for pair in conflicts:
            f1 = facts_by_id.get(pair[0], None)
            f2 = facts_by_id.get(pair[1], None)
            if (f1 and f1.char == char_id) or (f2 and f2.char == char_id):
                return True
        return False

    def char_tint(char_id):
        """Speech colour for a character, for tinting names in menus and lists."""
        return {
            "adrian": GOTH_C_ADRIAN,
            "marika": GOTH_C_MARIKA,
            "elise": GOTH_C_ELISE,
            "vance": GOTH_C_VANCE,
            "hargrove": GOTH_C_HARGROVE,
            "odile": GOTH_C_ODILE,
        }.get(char_id, GOTH_TEXT_SOFT)

    def trust_phrase(level):
        """Trust as a human read rather than a bare integer."""
        return {
            0: "Closed to you",
            1: "Wary",
            2: "Thawing",
            3: "Open",
        }.get(level, "Unknown")


################################################################################
## Shared Furniture
################################################################################

## Radial darkening that sits over backgrounds. Keeps the eye centred and
## makes the candlelit palette read as candlelit.
screen manor_vignette():
    zorder 10
    add "goth_vignette"

################################################################################
## HUD (always visible during investigation)
################################################################################
screen hud():
    zorder 100

    frame:
        xalign 0.5
        yalign 0.015
        background GOTH_HUDBAR
        xpadding 30
        ypadding 14

        hbox:
            spacing 34
            align (0.5, 0.5)

            # ─── Loop counter ───
            vbox:
                spacing 2
                text "LOOP" style "goth_label"
                text "[game_state.loop_no]" style "goth_value" color GOTH_GOLD size 26

            add Solid(GOTH_RAIL) xysize (1, 42) yalign 0.5

            # ─── Day and time of day ───
            vbox:
                spacing 2
                text "DAY [game_state.current_day]" style "goth_label"
                text "[game_state.current_slot.capitalize()]" style "goth_value"

            add Solid(GOTH_RAIL) xysize (1, 42) yalign 0.5

            # ─── Actions left in this slot ───
            vbox:
                spacing 2
                text "ACTIONS" style "goth_label"
                hbox:
                    spacing 6
                    text "[game_state.slot_actions_remaining]" style "goth_value" size 21
                    text "remaining" style "goth_value" size 19 color GOTH_TEXT_SOFT yalign 1.0

            add Solid(GOTH_RAIL) xysize (1, 42) yalign 0.5

            # ─── Strain, drawn as filling fractures rather than glyphs ───
            vbox:
                spacing 5
                text "STRAIN" style "goth_label"
                hbox:
                    spacing 5
                    yalign 0.5
                    for i in range(1, MAX_STRAIN + 1):
                        if i <= game_state.strain:
                            add Solid(GOTH_BLOOD_HI) xysize (28, 7)
                        else:
                            add Solid(GOTH_RAIL_DK) xysize (28, 7)

            add Solid(GOTH_RAIL) xysize (1, 42) yalign 0.5

            # ─── The one bullet ───
            vbox:
                spacing 4
                text "REVOLVER" style "goth_label"
                if game_state.bullet_available:
                    hbox:
                        spacing 7
                        yalign 0.5
                        add Solid(GOTH_GOLD) xysize (11, 11) yalign 0.5
                        text "One round" style "goth_value" size 19 color GOTH_GOLD
                else:
                    hbox:
                        spacing 7
                        yalign 0.5
                        add Solid(GOTH_RAIL_DK) xysize (11, 11) yalign 0.5
                        text "Spent" style "goth_value" size 19 color GOTH_TEXT_OFF

            add Solid(GOTH_RAIL) xysize (1, 42) yalign 0.5

            # ─── Notebook ───
            button:
                background GOTH_BTN_FLAT
                hover_background GOTH_BTN_HOVER
                xpadding 20
                ypadding 10
                action Show("notebook")
                text "Notebook" style "goth_button_text" size 20


################################################################################
## Location Selection
################################################################################
screen location_picker(locations_data):
    modal True
    zorder 90

    add GOTH_SCRIM

    frame:
        xalign 0.5
        yalign 0.5
        xsize 1020
        background GOTH_PANEL_FRAME
        xpadding 48
        ypadding 38

        vbox:
            spacing 6
            xfill True

            text "Where will you go?" style "goth_title" xalign 0.5
            text "Day [game_state.current_day] — [game_state.current_slot]" style "goth_subtitle" xalign 0.5

            add "goth_divider" xalign 0.5 yoffset 14 xsize 520

            null height 26

            vbox:
                spacing 12
                xfill True
                for loc_id, present in locations_data.items():
                    $ loc_name = get_location_display_name(loc_id)
                    button:
                        xfill True
                        ypadding 16
                        xpadding 24
                        background GOTH_BTN
                        hover_background GOTH_BTN_HOVER
                        action Return(loc_id)

                        hbox:
                            xfill True
                            spacing 20

                            text "[loc_name]":
                                font GOTH_FONT_DISPLAY_B
                                size 25
                                color GOTH_TEXT
                                hover_color GOTH_GOLD
                                yalign 0.5
                                xsize 320

                            # Who is here, each name in their own colour.
                            if present:
                                hbox:
                                    spacing 0
                                    yalign 0.5
                                    xalign 1.0
                                    for idx, c in enumerate(present):
                                        if idx > 0:
                                            text "  ·  " style "goth_body_soft" size 18 color GOTH_TEXT_OFF yalign 0.5
                                        text "[get_character_display_name(c)]":
                                            font GOTH_FONT_BODY_M
                                            size 19
                                            color char_tint(c)
                                            yalign 0.5
                            else:
                                text "empty — you would be alone":
                                    font GOTH_FONT_BODY_I
                                    size 19
                                    color GOTH_TEXT_OFF
                                    yalign 0.5
                                    xalign 1.0


################################################################################
## Action Picker (at the chosen location)
################################################################################
screen action_picker(current_loc, present_chars, actions_left, current_day, bullet_avail):
    modal True
    zorder 90
    $ loc_title = get_location_display_name(current_loc)

    add GOTH_SCRIM

    frame:
        xalign 0.5
        yalign 0.5
        xsize 1020
        background GOTH_PANEL_FRAME
        xpadding 48
        ypadding 38

        vbox:
            spacing 6
            xfill True

            text "[loc_title]" style "goth_title" xalign 0.5
            text "[actions_left] of [ACTIONS_PER_SLOT] actions left this hour" style "goth_subtitle" xalign 0.5

            add "goth_divider" xalign 0.5 yoffset 14 xsize 520

            null height 26

            vbox:
                spacing 11
                xfill True

                # ─── Talk to whoever is present ───
                for char in present_chars:
                    $ cname = get_character_display_name(char)
                    $ is_locked = char in game_state.locked_out
                    $ already_talked = char in game_state.conversations_this_slot

                    if is_locked or already_talked:
                        frame:
                            xfill True
                            ypadding 14
                            xpadding 24
                            background GOTH_BTN_OFF
                            hbox:
                                xfill True
                                text "Speak with [cname]":
                                    font GOTH_FONT_BODY_M
                                    size 22
                                    color GOTH_TEXT_OFF
                                if is_locked:
                                    text "will not look at you":
                                        font GOTH_FONT_BODY_I
                                        size 18
                                        color GOTH_TEXT_OFF
                                        xalign 1.0
                                else:
                                    text "already spoken to":
                                        font GOTH_FONT_BODY_I
                                        size 18
                                        color GOTH_TEXT_OFF
                                        xalign 1.0
                    else:
                        button:
                            xfill True
                            ypadding 14
                            xpadding 24
                            background GOTH_BTN
                            hover_background GOTH_BTN_HOVER
                            action Return(("talk", char))
                            hbox:
                                xfill True
                                text "Speak with ":
                                    font GOTH_FONT_BODY_M
                                    size 22
                                    color GOTH_TEXT_SOFT
                                text "[cname]":
                                    font GOTH_FONT_BODY_B
                                    size 22
                                    color char_tint(char)
                                $ ctrust = game_state.trust.get(char, 0)
                                text "[trust_phrase(ctrust)]":
                                    font GOTH_FONT_BODY_I
                                    size 18
                                    color GOTH_TEXT_MUTE
                                    xalign 1.0

                null height 6

                # ─── Search ───
                button:
                    xfill True
                    ypadding 14
                    xpadding 24
                    background GOTH_BTN
                    hover_background GOTH_BTN_HOVER
                    action Return(("search", current_loc))
                    hbox:
                        xfill True
                        text "Search [loc_title]":
                            font GOTH_FONT_BODY_M
                            size 22
                            color GOTH_BRASS
                            hover_color GOTH_GOLD
                        text "only works unobserved":
                            font GOTH_FONT_BODY_I
                            size 18
                            color GOTH_TEXT_MUTE
                            xalign 1.0

                # ─── The revolver ───
                if bullet_avail and present_chars:
                    button:
                        xfill True
                        ypadding 14
                        xpadding 24
                        background GOTH_BTN_BLOOD
                        hover_background GOTH_BTN_BLOOD_HI
                        action Return(("shoot_menu", current_loc))
                        hbox:
                            xfill True
                            text "Draw your father's revolver":
                                font GOTH_FONT_BODY_B
                                size 22
                                color GOTH_BLOOD_HI
                                hover_color GOTH_CREAM
                            text "one round, no second chance":
                                font GOTH_FONT_BODY_I
                                size 18
                                color GOTH_BLOOD_HI
                                xalign 1.0

                # ─── Pass ───
                button:
                    xfill True
                    ypadding 12
                    xpadding 24
                    background GOTH_BTN_FLAT
                    hover_background GOTH_BTN_HOVER
                    action Return(("pass", None))
                    text "Let the hour pass":
                        font GOTH_FONT_BODY_I
                        size 20
                        color GOTH_TEXT_MUTE
                        hover_color GOTH_TEXT_SOFT


################################################################################
## Revolver: Target Selection
################################################################################
screen shoot_target_picker(present_chars, weapon="revolver"):
    modal True
    zorder 95

    add GOTH_SCRIM

    frame:
        xalign 0.5
        yalign 0.5
        xsize 820
        background GOTH_PANEL_BLOOD
        xpadding 44
        ypadding 38

        vbox:
            spacing 6
            xfill True

            if weapon == "knife":
                text "The Knife" style "goth_title" color GOTH_BLOOD_HI xalign 0.5
                text "Close enough to feel them stop. Whoever you choose, you cannot choose again." style "goth_subtitle" color GOTH_TEXT_SOFT xalign 0.5
            else:
                text "One Bullet" style "goth_title" color GOTH_BLOOD_HI xalign 0.5
                text "Whoever you choose, you cannot choose again." style "goth_subtitle" color GOTH_TEXT_SOFT xalign 0.5

            add "goth_divider" xalign 0.5 yoffset 14 xsize 420

            null height 26

            vbox:
                spacing 11
                xfill True
                for char in present_chars:
                    $ cname = get_character_display_name(char)
                    button:
                        xfill True
                        ypadding 15
                        xpadding 24
                        background GOTH_BTN_BLOOD
                        hover_background GOTH_BTN_BLOOD_HI
                        action Return(char)
                        text ("Go for [cname]" if weapon == "knife" else "Take aim at [cname]"):
                            font GOTH_FONT_BODY_B
                            size 23
                            color char_tint(char)
                            hover_color GOTH_CREAM

                null height 8

                button:
                    xfill True
                    ypadding 13
                    xpadding 24
                    background GOTH_BTN_FLAT
                    hover_background GOTH_BTN_HOVER
                    action Return("cancel")
                    text ("Put the knife away" if weapon == "knife" else "Lower the gun"):
                        font GOTH_FONT_BODY_I
                        size 20
                        color GOTH_TEXT_MUTE
                        hover_color GOTH_TEXT_SOFT


################################################################################
## Revolver: Confirmation
################################################################################
screen shoot_confirm(target_name, weapon="revolver"):
    modal True
    zorder 100

    add GOTH_SCRIM

    frame:
        xalign 0.5
        yalign 0.5
        xsize 760
        background GOTH_PANEL_BLOOD
        xpadding 46
        ypadding 40

        vbox:
            spacing 18
            xfill True

            text ("You are close enough now." if weapon == "knife" else "The hammer is back."):
                style "goth_title"
                size 30
                color GOTH_BLOOD_HI
                xalign 0.5

            add "goth_divider" xalign 0.5 xsize 380

            text "[target_name] is in your sights.":
                style "goth_body"
                size 24
                xalign 0.5
                text_align 0.5

            text ("If you are wrong, you will have done it with your hands, from arm's length, and the house will hear it." if weapon == "knife" else "If you are wrong, they die for nothing, the house goes dark, and whoever is really waiting for you tonight will take their time."):
                font GOTH_FONT_BODY_I
                size 19
                color GOTH_TEXT_SOFT
                xalign 0.5
                text_align 0.5
                xmaximum 600
                line_spacing 5

            null height 14

            hbox:
                spacing 22
                xalign 0.5

                button:
                    xsize 260
                    ypadding 15
                    background GOTH_BTN_BLOOD
                    hover_background GOTH_BTN_BLOOD_HI
                    action Return("shoot")
                    text ("Do it" if weapon == "knife" else "Pull the trigger"):
                        font GOTH_FONT_BODY_B
                        size 21
                        color GOTH_CREAM
                        xalign 0.5

                button:
                    xsize 260
                    ypadding 15
                    background GOTH_BTN_FLAT
                    hover_background GOTH_BTN_HOVER
                    action Return("cancel")
                    text "Hesitate":
                        font GOTH_FONT_BODY_M
                        size 21
                        color GOTH_TEXT_MUTE
                        hover_color GOTH_TEXT_SOFT
                        xalign 0.5


################################################################################
## Conversation: NPC line on the painted plate, Adrian's options beneath
################################################################################
screen conversation_ui(char_name, char_color, npc_line, choices, arm_at=0):
    zorder 90
    modal True

    # Choices ignore input until arm_at so the click that dismissed the
    # previous line cannot carry over and select one. arm_at arrives as a
    # screen parameter: screen bodies are re-evaluated on every interaction,
    # so a deadline computed here would slide forward each time.
    #
    # `sensitive` is also only re-evaluated when an interaction restarts, so
    # force one as the window closes. Without this the buttons can sit locked
    # until the player clicks, which is the very click we are trying to catch.
    timer CHOICE_ARM_DELAY action Function(lambda: None)

    # Voice blips while the typewriter runs.
    on "show" action Play("voice_sfx", "audio/voice_" + str(active_speaker) + ".wav", loop=True)
    timer 1.8 action Stop("voice_sfx")
    on "hide" action Stop("voice_sfx")

    # ─── Speaker's line, laid into the painted candle plate ───
    fixed:
        xsize 1620
        ysize 226
        xalign 0.5
        ypos 596

        add GOTH_CONVOBOX_ART

        vbox:
            xpos 266
            ypos 42
            xmaximum 1306
            spacing 7

            text "[char_name]":
                font GOTH_FONT_DISPLAY_B
                size 25
                color char_color
                kerning 1.4
                outlines [(2, GOTH_VOID, 0, 0)]

            text "[npc_line]":
                font GOTH_FONT_BODY
                size 23
                color GOTH_TEXT
                line_spacing 6
                slow_cps 38
                xmaximum 1296
                outlines [(2, "#0d080999", 0, 1)]

    # ─── Adrian's four replies ───
    vbox:
        xalign 0.5
        ypos 846
        xsize 1620
        spacing 11

        for row in (0, 2):
            hbox:
                spacing 14
                xfill True
                for choice in choices[row:row + 2]:
                    $ intent_label = choice.get("intent", "")
                    $ choice_text = choice.get("text", "")
                    button:
                        xsize 803
                        ypadding 15
                        xpadding 26
                        background GOTH_BTN
                        hover_background GOTH_BTN_HOVER
                        insensitive_background GOTH_BTN_OFF
                        # Armed briefly after the screen appears. See
                        # CHOICE_ARM_DELAY for why.
                        #
                        # Ren'Py already ignores a release that did not begin on
                        # the same button, so press-and-release is handled.
                        sensitive (time.monotonic() >= arm_at)
                        action [Stop("voice_sfx"), Return((intent_label, choice_text))]
                        text "[choice_text]":
                            font GOTH_FONT_BODY
                            size 20
                            color GOTH_TEXT_SOFT
                            hover_color GOTH_GOLD
                            insensitive_color GOTH_TEXT_OFF
                            yalign 0.5
                            line_spacing 3


# Backward compatibility alias
screen conversation_choices(choices):
    use conversation_ui(active_speaker_name, active_speaker_color, active_npc_line, choices, time.monotonic() + CHOICE_ARM_DELAY)


################################################################################
## Notebook
################################################################################
default notebook_tab = "characters"

screen notebook():
    modal True
    zorder 150

    add GOTH_SCRIM

    frame:
        xalign 0.5
        yalign 0.5
        xsize 1540
        ysize 920
        background GOTH_PANEL_FRAME
        xpadding 44
        ypadding 34

        vbox:
            spacing 14
            xfill True

            # ─── Header ───
            hbox:
                xfill True
                yalign 0.5

                vbox:
                    spacing 1
                    text "The Notebook" style "goth_title" size 31
                    text "Everything you carry back through the loop" style "goth_subtitle" size 17

                textbutton "Close":
                    action Hide("notebook")
                    xalign 1.0
                    yalign 0.5
                    background GOTH_BTN_FLAT
                    hover_background GOTH_BTN_HOVER
                    xpadding 24
                    ypadding 10
                    text_style "goth_button_text"
                    text_size 20

            add "goth_divider" xalign 0.5 xsize 1400

            # ─── Tabs ───
            hbox:
                spacing 9
                xalign 0.0
                for tab_id, tab_name in [("characters", "People"), ("timeline", "Timeline"), ("findings", "Evidence"), ("deaths", "Deaths")]:
                    button:
                        xpadding 30
                        ypadding 11
                        background (GOTH_TAB_ON if notebook_tab == tab_id else GOTH_TAB_OFF)
                        hover_background GOTH_TAB_ON
                        action SetScreenVariable("notebook_tab", tab_id)
                        text "[tab_name]":
                            font GOTH_FONT_DISPLAY_B
                            size 21
                            color (GOTH_GOLD if notebook_tab == tab_id else GOTH_TEXT_MUTE)
                            hover_color GOTH_CREAM
                            kerning 1.0

            null height 4

            # ─── Active tab ───
            if notebook_tab == "characters":
                use notebook_characters_tab()
            elif notebook_tab == "timeline":
                use notebook_timeline_tab()
            elif notebook_tab == "findings":
                use notebook_findings_tab()
            elif notebook_tab == "deaths":
                use notebook_deaths_tab()


## Notebook Tab: People
screen notebook_characters_tab():
    $ conflicts_list = find_conflicts(game_state.known_facts, all_facts)
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 14
            xfill True

            for char in CHARACTERS:
                $ cname = get_character_display_name(char)
                $ ctrust = game_state.trust.get(char, 0)
                $ char_facts = [f for f in all_facts if f.char == char and f.id in game_state.known_facts]
                $ has_conflict = character_has_conflict(char, conflicts_list, all_facts)

                frame:
                    xfill True
                    background (GOTH_PANEL_BLOOD if has_conflict else GOTH_LEAF)
                    xpadding 26
                    ypadding 20

                    vbox:
                        spacing 10

                        hbox:
                            xfill True
                            spacing 16
                            yalign 0.5

                            text "[cname]":
                                font GOTH_FONT_DISPLAY_B
                                size 25
                                color char_tint(char)
                                kerning 0.8

                            if has_conflict:
                                frame:
                                    background Solid(GOTH_BLOOD)
                                    xpadding 11
                                    ypadding 4
                                    yalign 0.5
                                    text "CONTRADICTS THEMSELF":
                                        font GOTH_FONT_BODY_B
                                        size 14
                                        color GOTH_CREAM
                                        kerning 1.4

                            vbox:
                                xalign 1.0
                                spacing 3
                                text "[trust_phrase(ctrust)]":
                                    font GOTH_FONT_BODY_I
                                    size 18
                                    color GOTH_TEXT_SOFT
                                    xalign 1.0
                                hbox:
                                    spacing 4
                                    xalign 1.0
                                    for i in range(1, TRUST_MAX + 1):
                                        if i <= ctrust:
                                            add Solid(GOTH_GOLD) xysize (22, 5)
                                        else:
                                            add Solid(GOTH_RAIL_DK) xysize (22, 5)

                        if char_facts:
                            vbox:
                                spacing 6
                                for f in char_facts:
                                    hbox:
                                        spacing 12
                                        add Solid(GOTH_GOLD_DIM) xysize (4, 4) yoffset 9
                                        text "[f.text]":
                                            font GOTH_FONT_BODY
                                            size 19
                                            color GOTH_TEXT_SOFT
                                            line_spacing 4
                        else:
                            text "Nothing recorded. You have not made them talk yet.":
                                font GOTH_FONT_BODY_I
                                size 18
                                color GOTH_TEXT_OFF


## Notebook Tab: Timeline
screen notebook_timeline_tab():
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 14
            xfill True

            text "Where you actually saw them — not where they claim to be.":
                font GOTH_FONT_BODY_I
                size 19
                color GOTH_TEXT_MUTE

            for d in [1, 2]:
                frame:
                    xfill True
                    background GOTH_LEAF
                    xpadding 24
                    ypadding 18
                    vbox:
                        spacing 11
                        text "DAY [d]":
                            font GOTH_FONT_DISPLAY_B
                            size 22
                            color GOTH_GOLD
                            kerning 2.0

                        for s in SLOTS:
                            $ slot_obs = []
                            for c in CHARACTERS:
                                $ pres_key = "presence:seen:" + c + ":" + run_state.positions[c][str(d)][s] + ":" + s + ":" + str(d)
                                if pres_key in game_state.known_facts:
                                    $ slot_obs.append((c, get_location_display_name(run_state.positions[c][str(d)][s])))
                            hbox:
                                spacing 16
                                text "[s.capitalize()]":
                                    font GOTH_FONT_BODY_B
                                    size 19
                                    color GOTH_TEXT_MUTE
                                    xsize 150
                                if slot_obs:
                                    vbox:
                                        spacing 3
                                        for c, where in slot_obs:
                                            hbox:
                                                spacing 8
                                                text "[get_character_display_name(c)]":
                                                    font GOTH_FONT_BODY_M
                                                    size 19
                                                    color char_tint(c)
                                                text "in the [where]":
                                                    font GOTH_FONT_BODY
                                                    size 19
                                                    color GOTH_TEXT_SOFT
                                else:
                                    text "you were not there":
                                        font GOTH_FONT_BODY_I
                                        size 18
                                        color GOTH_TEXT_OFF


## Notebook Tab: Evidence
screen notebook_findings_tab():
    $ found_items = [f for f in all_facts if f.kind in ("finding", "world") and f.id in game_state.known_facts]
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 13
            xfill True

            if found_items:
                for item in found_items:
                    frame:
                        xfill True
                        background (GOTH_PANEL_PLUM if item.exclusive else GOTH_LEAF)
                        xpadding 24
                        ypadding 17
                        vbox:
                            spacing 7
                            hbox:
                                spacing 14
                                yalign 0.5
                                text "[item.id]":
                                    font GOTH_FONT_DISPLAY_B
                                    size 21
                                    color (GOTH_GOLD if item.exclusive else GOTH_TEXT_SOFT)
                                    kerning 0.8
                                if item.exclusive:
                                    frame:
                                        background Solid(GOTH_BLOOD)
                                        xpadding 11
                                        ypadding 4
                                        yalign 0.5
                                        text "DAMNING":
                                            font GOTH_FONT_BODY_B
                                            size 14
                                            color GOTH_CREAM
                                            kerning 1.6
                            text "[item.text]":
                                font GOTH_FONT_BODY
                                size 20
                                color GOTH_TEXT
                                line_spacing 5
            else:
                frame:
                    xfill True
                    background GOTH_LEAF
                    xpadding 26
                    ypadding 24
                    text "Nothing yet. Rooms only give up their secrets when nobody is standing in them — go where the others are not.":
                        font GOTH_FONT_BODY_I
                        size 20
                        color GOTH_TEXT_MUTE
                        line_spacing 5


## Notebook Tab: Deaths
screen notebook_deaths_tab():
    viewport:
        scrollbars "vertical"
        mousewheel True
        draggable True
        vbox:
            spacing 13
            xfill True

            text "What you felt in the dark. Each death gives up one more detail.":
                font GOTH_FONT_BODY_I
                size 19
                color GOTH_TEXT_MUTE

            if game_state.fragments_seen:
                for idx, frag in enumerate(game_state.fragments_seen, 1):
                    frame:
                        xfill True
                        background GOTH_PANEL_BLOOD
                        xpadding 26
                        ypadding 20
                        vbox:
                            spacing 9
                            text "DEATH [idx]":
                                font GOTH_FONT_DISPLAY_B
                                size 18
                                color GOTH_BLOOD_HI
                                kerning 2.4
                            text "“[frag]”":
                                font GOTH_FONT_DISPLAY_I
                                size 23
                                color GOTH_TEXT
                                line_spacing 6
            else:
                frame:
                    xfill True
                    background GOTH_LEAF
                    xpadding 26
                    ypadding 24
                    text "You have not died yet.":
                        font GOTH_FONT_BODY_I
                        size 20
                        color GOTH_TEXT_MUTE


################################################################################
## Cinematic Overlays
################################################################################

screen cinema_letterbox():
    zorder 95
    add Solid(GOTH_VOID) xysize (1920, 78) xalign 0.5 yalign 0.0
    add Solid(GOTH_VOID) xysize (1920, 78) xalign 0.5 yalign 1.0


screen heartbeat_flash():
    zorder 90
    add Solid("#b02a2a2e") xysize (1920, 1080)


screen loop_splash_screen(loop_num, strain_val):
    zorder 120
    modal True

    add Solid(GOTH_VOID) xysize (1920, 1080)
    add "goth_vignette"

    vbox:
        align (0.5, 0.5)
        spacing 0

        text "RETURN BY DEATH":
            font GOTH_FONT_DISPLAY_B
            size 23
            color GOTH_BLOOD_HI
            kerning 11
            xalign 0.5

        null height 10
        add "goth_divider" xalign 0.5 xsize 560
        null height 16

        text "LOOP [loop_num]":
            font GOTH_FONT_DISPLAY_B
            size 92
            color GOTH_CREAM
            kerning 10
            xalign 0.5
            outlines [(3, GOTH_VOID, 0, 0)]

        null height 10

        text "Day Two — seven in the morning":
            font GOTH_FONT_DISPLAY_I
            size 23
            color GOTH_TEXT_MUTE
            xalign 0.5

        null height 44

        # ─── Strain ───
        frame:
            xalign 0.5
            background GOTH_PANEL_BLOOD
            xpadding 44
            ypadding 26
            xsize 860

            vbox:
                spacing 14
                xfill True

                hbox:
                    xfill True
                    text "HAIRLINE FRACTURES":
                        font GOTH_FONT_BODY_B
                        size 15
                        color GOTH_BLOOD_HI
                        kerning 3.0
                        yalign 0.5
                    hbox:
                        spacing 7
                        xalign 1.0
                        yalign 0.5
                        for i in range(1, MAX_STRAIN + 1):
                            if i <= strain_val:
                                add Solid(GOTH_BLOOD_HI) xysize (54, 8)
                            else:
                                add Solid(GOTH_RAIL_DK) xysize (54, 8)

                if strain_val <= 0:
                    text "Your skin is still your own. The first thread has only just been cut.":
                        font GOTH_FONT_DISPLAY_I
                        size 21
                        color GOTH_TEXT_SOFT
                        line_spacing 5
                elif strain_val == 1:
                    text "Black fissures pulse under the skin of your left wrist, warm as a struck match.":
                        font GOTH_FONT_DISPLAY_I
                        size 21
                        color GOTH_TEXT_SOFT
                        line_spacing 5
                elif strain_val == 2:
                    text "The cracks have reached your elbow and they are climbing toward your throat. One more death ends you.":
                        font GOTH_FONT_DISPLAY_I
                        size 21
                        color GOTH_TEXT
                        line_spacing 5
                else:
                    text "You are coming apart. There is almost nothing left to bring back.":
                        font GOTH_FONT_DISPLAY_I
                        size 21
                        color GOTH_BLOOD_HI
                        line_spacing 5

        null height 40

        text "click to wake":
            font GOTH_FONT_BODY_I
            size 18
            color GOTH_TEXT_OFF
            kerning 2.0
            xalign 0.5

    button:
        xfill True
        yfill True
        background None
        action Return()
