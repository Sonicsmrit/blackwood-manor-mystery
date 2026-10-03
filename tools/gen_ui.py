#!/usr/bin/env python3
"""Generate the gothic 9-slice UI chrome for Return by Death Manor.

The manor's art pack (game/images/ui/textbox*.png) is a warm candle-lit
palette: cream rim, brown rail, dusty plum fill. Everything this script
emits is built from that same vocabulary so the code-drawn panels sit
flush against the painted textboxes.

No third-party deps -- Ren'Py's bundled Python has no PIL, so PNGs are
written by hand.  Output lands in game/images/ui/gen/.
"""

import os
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game", "images", "ui", "gen")

# ─── Palette (sampled from the textbox art pack) ────────────────────────────
CREAM = (232, 217, 184)
CREAM_DIM = (190, 172, 140)
RAIL = (74, 42, 32)
RAIL_DK = (46, 25, 19)
GOLD = (217, 168, 92)
PLUM = (107, 82, 96)
PLUM_DK = (58, 42, 52)
INK = (30, 21, 24)
INK_DEEP = (18, 12, 14)
BLOOD = (118, 30, 32)
BLOOD_DK = (62, 16, 18)


def write_png(path, width, height, rows):
    """rows: list of height lists, each of width (r,g,b,a) tuples."""
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter type 0
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def bordered_panel(name, fill, bands, size=28):
    """A 9-slice panel: concentric border `bands` wrapping a flat `fill`.

    `bands` is an outside-in list of (color, alpha, thickness).
    """
    layers = []
    for color, alpha, thickness in bands:
        layers.extend([(color, alpha)] * thickness)

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            depth = min(x, y, size - 1 - x, size - 1 - y)
            if depth < len(layers):
                color, alpha = layers[depth]
            else:
                color, alpha = fill
            row.append((color[0], color[1], color[2], alpha))
        rows.append(row)
    write_png(os.path.join(OUT_DIR, name), size, size, rows)


def vignette(name, width=640, height=360, strength=235, inner=0.42):
    """Radial darkening overlay -- scales smoothly to any resolution."""
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    rows = []
    for y in range(height):
        row = []
        dy = (y - cy) / cy
        for x in range(width):
            dx = (x - cx) / cx
            d = (dx * dx + dy * dy) ** 0.5
            t = (d - inner) / (1.0 - inner)
            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
            row.append((0, 0, 0, int(strength * (t * t))))
        rows.append(row)
    write_png(os.path.join(OUT_DIR, name), width, height, rows)


def divider(name, width=400, height=13):
    """Hairline rule with a centred gold lozenge -- a section break."""
    mid = height // 2
    cx = width // 2
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            px = (0, 0, 0, 0)
            # the rule itself, fading out toward both ends
            if y == mid:
                edge = min(x, width - 1 - x) / float(width * 0.45)
                fade = 1.0 if edge > 1 else edge
                gap = abs(x - cx)
                if gap > 9:
                    px = (CREAM_DIM[0], CREAM_DIM[1], CREAM_DIM[2], int(150 * fade))
            # centred lozenge
            gap = abs(x - cx)
            span = abs(y - mid)
            if gap + span * 2 <= 9:
                px = (GOLD[0], GOLD[1], GOLD[2], 235) if gap + span * 2 >= 6 else (GOLD[0], GOLD[1], GOLD[2], 120)
            row.append(px)
        rows.append(row)
    write_png(os.path.join(OUT_DIR, name), width, height, rows)


def scrim(name, alpha=205):
    """Flat modal dimmer, warm-tinted rather than neutral black."""
    rows = [[(10, 6, 7, alpha) for _ in range(8)] for _ in range(8)]
    write_png(os.path.join(OUT_DIR, name), 8, 8, rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Outside-in band stacks, echoing the painted textbox edge treatment:
    # cream rim -> brown rail -> dark relief -> thin gold inlay.
    ornate = [(CREAM, 225, 2), (RAIL, 255, 4), (RAIL_DK, 255, 2), (GOLD, 90, 1)]
    plain = [(CREAM_DIM, 120, 1), (RAIL, 235, 3), (RAIL_DK, 255, 2)]
    hairline = [(GOLD, 70, 1), (RAIL_DK, 200, 2)]

    # Modal / section panels
    bordered_panel("panel.png", (INK, 248), ornate)
    bordered_panel("panel_deep.png", (INK_DEEP, 250), ornate)
    bordered_panel("panel_plum.png", (PLUM_DK, 242), ornate)

    # List buttons
    bordered_panel("button.png", (INK, 225), plain)
    bordered_panel("button_hover.png", (PLUM_DK, 245), [(GOLD, 200, 1), (RAIL, 235, 3), (RAIL_DK, 255, 2)])
    bordered_panel("button_flat.png", (INK_DEEP, 200), hairline)
    bordered_panel("button_off.png", (INK_DEEP, 150), [(RAIL_DK, 120, 2)])

    # Violence: the revolver screens run hot
    bordered_panel("panel_blood.png", (BLOOD_DK, 248), [(CREAM, 170, 1), (BLOOD, 255, 4), (RAIL_DK, 255, 2)])
    bordered_panel("button_blood.png", (BLOOD_DK, 235), [(BLOOD, 220, 2), (RAIL_DK, 255, 2)])
    bordered_panel("button_blood_hover.png", (BLOOD, 245), [(CREAM, 190, 1), (BLOOD, 255, 3)])

    # HUD bar -- wider rails, no cream rim so it reads as furniture not a modal
    bordered_panel("hudbar.png", (INK_DEEP, 232), [(GOLD, 110, 1), (RAIL, 230, 3), (RAIL_DK, 245, 2)])

    # Notebook: parchment-ish leaf against the dark chrome
    bordered_panel("leaf.png", (PLUM_DK, 170), [(RAIL_DK, 180, 2)])
    bordered_panel("tab_on.png", (PLUM, 235), [(GOLD, 190, 1), (RAIL, 240, 3)])
    bordered_panel("tab_off.png", (INK_DEEP, 190), [(RAIL_DK, 200, 2)])

    vignette("vignette.png")
    divider("divider.png")
    scrim("scrim.png")

    print("Wrote UI chrome to", os.path.normpath(OUT_DIR))
    for f in sorted(os.listdir(OUT_DIR)):
        print("  ", f)


if __name__ == "__main__":
    main()
