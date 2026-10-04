"""Extract the bundled audio archives and build a contact sheet for auditioning.

The four shdemo-*.zip archives at the project root hold 811 Vorbis tracks with no
metadata of any kind -- no mood, no genre, no track title, just a number. They
cannot be told apart programmatically, so picking them is a listening job.

This tool does the mechanical half:

  1. extracts each archive into audio_inbox/ (gitignored, ~200MB)
  2. probes every track for real duration, sample rate and channels
  3. writes audio_inbox/contact_sheet.html -- every track in one page with an
     inline player, a duration filter, a search box, and checkboxes whose
     selections survive a page refresh

You open the sheet, listen, tick what fits, and press "Copy picks". Paste the
result back and that list drives which tracks get copied into the game.

Nothing here decides what music the game should use. It only makes the
listening tractable.

Usage:
    python3 tools/extract_audio.py            # extract + rebuild the sheet
    python3 tools/extract_audio.py --no-extract   # rebuild the sheet only
"""

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(BASE_DIR, "audio_inbox")
SHEET = os.path.join(INBOX, "contact_sheet.html")
PROBE_JSON = os.path.join(INBOX, "tracks.json")
NOTES_JSON = os.path.join(INBOX, "notes.json")

# (archive, category). "loop" is the short-ambience set, "music" the long beds.
ARCHIVES = [
    ("shdemo-loop.zip", "loop"),
    ("shdemo-music-001-100.zip", "music"),
    ("shdemo-music-101-200.zip", "music"),
    ("shdemo-music-601-690.zip", "music"),
]

# Slots in the game that a picked track has to cover. Shown in the sheet so the
# brief travels with the listening rather than living in a chat message.
BRIEF = [
    ("title", "Opening title. Slow, unresolved, a house settling."),
    ("day1", "Day 1 bed. Long-lived; you will sit in it for a whole day."),
    ("evening", "Day 1 evening. Warmer than day1, but uneasy."),
    ("night_transition", "Rooftops. The wrong car. Rising dread, no climax yet."),
    ("day2", "Day 2 bed. Colder and thinner than day1 -- you know more now."),
    ("night_menu", "The midnight menu. Tense, sparse, nowhere to hide."),
    ("burial", "wrong_kill_coverup / after_hours. Quiet. Something has just happened."),
    ("confession", "loop_confession_attempt. The closest thing to hope in the game."),
    ("victory", "ending_victory. Resolution without triumph."),
    ("swallowed", "ending_swallowed. Dread, final."),
]

AMBIENCE_BRIEF = [
    ("ambience", "Longest quiet loops only -- ideally 30s+, seamless. Note that a "
                 "hard cut or a lead melody will fight the voice blips, so skip "
                 "anything with an obvious front."),
]

SFX_BRIEF = [
    ("clock", "A real clock tick, not a beep. ~1s."),
    ("heartbeat", "Heartbeat at strain. ~1s, will be looped in code."),
    ("strain", "Creak, scrape, strain. ~1-3s."),
    ("loop_snap", "The reality tear. ~1s, sharp."),
    ("thunder", "Thunder, replacing audio/thunder.wav (3 uses)."),
    ("gunshot", "Gunshot, replacing audio/gunshot.wav (1 use)."),
    ("revolver_cock", "Revolver cock, replacing audio/revolver_cock.wav (2 uses)."),
]


def have_ffprobe():
    return shutil.which("ffprobe") is not None


def probe(path):
    """Return {duration, sample_rate, channels} for a file, or duration None."""
    if not have_ffprobe():
        return {"duration": None, "sample_rate": None, "channels": None}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate,channels:format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60, check=True).stdout
        data = json.loads(out)
        streams = data.get("streams") or [{}]
        stream = streams[0]
        dur = (data.get("format") or {}).get("duration")
        return {
            "duration": round(float(dur), 2) if dur else None,
            "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
            "channels": int(stream["channels"]) if stream.get("channels") else None,
        }
    except Exception as exc:  # noqa: BLE001 - a bad track must not stop the build
        print(f"    probe failed: {exc}", file=sys.stderr)
        return {"duration": None, "sample_rate": None, "channels": None}


def extract():
    os.makedirs(INBOX, exist_ok=True)
    for archive, category in ARCHIVES:
        src = os.path.join(BASE_DIR, archive)
        if not os.path.exists(src):
            print(f"  missing {archive} -- skipped")
            continue
        with zipfile.ZipFile(src) as zf:
            members = [m for m in zf.namelist() if m.lower().endswith(".ogg")]
            print(f"  {archive}: {len(members)} track(s)")
            for member in members:
                # Flatten, but never overwrite: ids collide across the music zips.
                flat = os.path.basename(member)
                dest = os.path.join(INBOX, flat)
                if os.path.exists(dest) and os.path.getsize(dest) == zf.getinfo(member).file_size:
                    continue
                with zf.open(member) as src_f, open(dest, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)
        # Record which archive each id came from, for grouping in the sheet.
        if not os.path.exists(PROBE_JSON):
            with open(PROBE_JSON, "w", encoding="utf-8") as fh:
                json.dump({}, fh)
        with open(PROBE_JSON, "r", encoding="utf-8") as fh:
            index = json.load(fh)
        with zipfile.ZipFile(src) as zf:
            for member in zf.namelist():
                if member.lower().endswith(".ogg"):
                    index[os.path.basename(member)] = {
                        "category": category,
                        "archive": archive,
                    }
        with open(PROBE_JSON, "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=1, sort_keys=True)


def collect():
    if not os.path.exists(PROBE_JSON):
        with open(PROBE_JSON, "w", encoding="utf-8") as fh:
            json.dump({}, fh)
    with open(PROBE_JSON, "r", encoding="utf-8") as fh:
        index = json.load(fh)

    tracks = []
    for name in sorted(os.listdir(INBOX)):
        if not name.lower().endswith(".ogg"):
            continue
        path = os.path.join(INBOX, name)
        info = index.get(name, {})
        meta = probe(path)
        tracks.append({
            "name": name,
            "category": info.get("category", "loop" if "loop" in name else "music"),
            "archive": info.get("archive", ""),
            "bytes": os.path.getsize(path),
            **meta,
        })

    with open(PROBE_JSON, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1, sort_keys=True)
    return tracks


def fmt_dur(seconds):
    if not seconds:
        return "--:--"
    seconds = int(round(seconds))
    if seconds >= 3600:
        return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60}:{seconds % 60:02d}"


def load_notes():
    """Curation notes from a previous session, so refreshes don't lose decisions."""
    if not os.path.exists(NOTES_JSON):
        return {}
    try:
        with open(NOTES_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("notes", {}) if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        print(f"    notes unreadable, starting blank: {exc}", file=sys.stderr)
        return {}


def save_notes(notes):
    with open(NOTES_JSON, "w", encoding="utf-8") as fh:
        json.dump({"notes": notes}, fh, indent=1, sort_keys=True)


def build_sheet(tracks, notes):
    rows = []
    for t in tracks:
        dur = t["duration"]
        rows.append(
            '<tr data-cat="{cat}" data-dur="{dur}" data-name="{name}">'
            '<td class="dest">'
            '<input class="note" type="text" placeholder="use it for&hellip;" '
            'value="{note}" data-note-for="{name}"></td>'
            '<td class="pick"><input type="checkbox" value="{name}"></td>'
            '<td class="play"><audio controls preload="none" src="{name}"></audio></td>'
            '<td class="file">{name}</td>'
            '<td class="num">{dur_s}</td>'
            '<td class="num">{kb} KB</td>'
            "</tr>".format(
                cat=html.escape(t["category"]),
                dur=dur if dur is not None else 99999,
                dur_s=html.escape(fmt_dur(dur)),
                name=html.escape(t["name"]),
                kb=html.escape(f"{t['bytes'] // 1024}"),
                note=html.escape(notes.get(t["name"], "")),
            )
        )

    def brief(items):
        return "".join(f"<li><b>{html.escape(k)}</b> &mdash; {html.escape(v)}</li>"
                       for k, v in items)

    music_n = sum(1 for t in tracks if t["category"] == "music")
    loop_n = len(tracks) - music_n

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Audio contact sheet</title>
<style>
 body {{ background:#14100e; color:#e8e0d0; font:14px/1.5 ui-monospace,Menlo,monospace; margin:0; padding:24px; }}
 h1 {{ font-size:20px; letter-spacing:2px; margin:0 0 4px; }}
 h2 {{ font-size:15px; letter-spacing:1px; margin:28px 0 8px; color:#c9a227;
      border-bottom:1px solid #3a3128; padding-bottom:6px; }}
 .sub {{ color:#9a8f7d; margin-bottom:18px; }}
 .brief {{ background:#1d1815; border-left:3px solid #b02a2a; padding:12px 16px; margin:0 0 18px; }}
 .brief ul {{ margin:6px 0; padding-left:18px; }}
 .bar {{ position:sticky; top:0; background:#14100e; padding:12px 0; border-bottom:1px solid #3a3128; z-index:5; }}
 input[type=search], input[type=range] {{ background:#1d1815; color:#e8e0d0;
      border:1px solid #3a3128; padding:6px 8px; border-radius:3px; }}
 button {{ background:#b02a2a; color:#f5efe0; border:0; padding:8px 16px;
      border-radius:3px; cursor:pointer; font:inherit; font-weight:700; }}
 button.sec {{ background:#3a3128; }}
 table {{ border-collapse:collapse; width:100%; margin-top:10px; }}
 th,td {{ padding:5px 8px; border-bottom:1px solid #241f1b; text-align:left; vertical-align:middle; }}
 th {{ position:sticky; top:56px; background:#14100e; color:#c9a227; font-size:12px;
       letter-spacing:1px; text-transform:uppercase; }}
 td.num {{ text-align:right; color:#9a8f7d; white-space:nowrap; }}
 td.pick {{ width:28px; }}
 td.play audio {{ height:28px; width:170px; }}
 td.dest {{ width:34%; min-width:220px; }}
 td.dest input {{ background:#241f1b; color:#e8e0d0; border:1px solid #3a3128;
       padding:5px 8px; border-radius:3px; width:100%; font:inherit; }}
 td.dest input:focus {{ outline:none; border-color:#c9a227; }}
 input.note {{ font-size:12px; }}
 tr.hide {{ display:none; }}
 tr.sel td {{ background:#2a1f16; }}
 .count {{ color:#c9a227; }}
 .note {{ color:#9a8f7d; font-size:12px; }}
 code {{ background:#241f1b; padding:1px 5px; border-radius:3px; }}
</style>
</head>
<body>

<h1>AUDIO CONTACT SHEET</h1>
<div class="sub">{len(tracks)} tracks &mdash; {music_n} music (median 1:30, good looping beds),
{loop_n} loop (median 0:03 &mdash; mostly one-shot SFX and stingers, not beds).
Pick about 20-25 music, 4-6 long loops for ambience, and 7 single-shot effects.
Selections survive a refresh.</div>

<div class="brief">
 <b>Music slots to cover</b>
 <ul>{brief(BRIEF)}</ul>
</div>
<div class="brief">
 <b>Ambience, under speech</b>
 <ul>{brief(AMBIENCE_BRIEF)}</ul>
</div>
<div class="brief">
 <b>Sound effects to replace</b>
 <ul>{brief(SFX_BRIEF)}</ul>
</div>

<div class="bar">
 <input type="search" id="q" placeholder="filter by name&hellip;" size="22">
 <label>max duration <span id="dv">10:00</span>
 <input type="range" id="dur" min="5" max="2000" value="600" step="5" style="width:220px">
 </label>
 <label><input type="checkbox" id="onlyloop"> loops only</label>
 <label><input type="checkbox" id="onlymusic"> music only</label>
 <span class="count">showing <span id="shown">0</span></span>
 &nbsp;
 <button id="copy">Copy picks</button>
 <button class="sec" id="clear">Clear</button>
</div>

<div class="note" id="out" style="margin-top:10px"></div>

<table>
 <thead><tr><th>use it for</th><th></th><th>play</th><th>file</th><th>length</th><th>size</th></tr></thead>
 <tbody>{''.join(rows)}</tbody>
</table>

<div class="bar" id="drop" style="top:auto;margin-top:18px;position:static;display:none">
 <b>Your notes &mdash; copy this whole block and paste it to me</b>
 <p class="note">One line per track: <code>filename.ogg &rarr; where it goes</code>.
 Anything you leave blank or untick is ignored. Re-tick to revise later.</p>
 <button id="copy2" class="sec">Copy notes</button>
 <button id="dl2" class="sec">Download notes</button>
 <span class="count" id="saved" style="display:none">notes saved</span>
</div>

<script>
const KEY = "audio_picks_v1";
let picks = new Set(JSON.parse(localStorage.getItem(KEY) || "[]"));
let notes = {{}};
const rows = [...document.querySelectorAll("tbody tr")];
const noteInputs = [...document.querySelectorAll("input[data-note-for]")];
const drop = document.getElementById("drop");
const q = document.getElementById("q");
const dur = document.getElementById("dur");
const dv = document.getElementById("dv");
const onlyLoop = document.getElementById("onlyloop");
const onlyMusic = document.getElementById("onlymusic");
const out = document.getElementById("out");

function fmt(s) {{
  s = Math.round(s);
  return s >= 3600 ? `${{s/3600|0}}:${{(s%3600)/60|0}}`.replace(/\\d(?=:)/,"$&") + ":" + String(s%60).padStart(2,"0")
                   : `${{s/60|0}}:${{String(s%60).padStart(2,"0")}}`;
}}

function save() {{ localStorage.setItem(KEY, JSON.stringify([...picks])); }}
function saveNotes() {{ localStorage.setItem(KEY + "_notes", JSON.stringify(notes)); }}
function readNotes() {{ try {{ return JSON.parse(localStorage.getItem(KEY + "_notes") || "{{}}"); }} catch (e) {{ return {{}}; }} }}

function noteLines() {{
  // Only ticked rows, in track order, so the block reads like a shopping list.
  const lines = [];
  rows.forEach(tr => {{
    const cb = tr.querySelector("input[type=checkbox]");
    if (!cb.checked) return;
    const name = cb.value;
    const n = (notes[name] || "").trim();
    lines.push(n ? `${{name}}  ->  ${{n}}` : `${{name}}  ->  (no note -- where does this go?)`);
  }});
  return lines;
}}

function showDrop() {{ drop.style.display = "block"; }}

function apply() {{
  const term = q.value.toLowerCase().trim();
  const max = parseFloat(dur.value);
  let shown = 0;
  rows.forEach(tr => {{
    const cat = tr.dataset.cat;
    const d = parseFloat(tr.dataset.dur);
    const okName = !term || tr.dataset.name.toLowerCase().includes(term);
    const okDur = d <= max;
    const okCat = (!onlyLoop.checked && !onlyMusic.checked)
                  || (onlyLoop.checked && cat === "loop")
                  || (onlyMusic.checked && cat === "music");
    const show = okName && okDur && okCat;
    tr.classList.toggle("hide", !show);
    if (show) shown++;
  }});
  document.getElementById("shown").textContent = shown;
  dv.textContent = fmt(max);
}}

function syncChecks() {{
  rows.forEach(tr => {{
    const cb = tr.querySelector("input[type=checkbox]");
    const on = picks.has(cb.value);
    cb.checked = on;
    tr.classList.toggle("sel", on);
  }});
}}

document.querySelectorAll("tbody input[type=checkbox]").forEach(cb => {{
  cb.addEventListener("change", () => {{
    if (cb.checked) picks.add(cb.value); else picks.delete(cb.value);
    save(); syncChecks(); showDrop();
  }});
}});

noteInputs.forEach(inp => {{
  inp.value = notes[inp.dataset.noteFor] || "";
  inp.addEventListener("input", () => {{
    notes[inp.dataset.noteFor] = inp.value;
    saveNotes();
  }});
  inp.addEventListener("change", () => {{ showDrop(); }});
}});

document.getElementById("copy2").addEventListener("click", async () => {{
  const lines = noteLines();
  const text = lines.join("\\n") || "(nothing ticked yet)";
  out.textContent = text;
  try {{ await navigator.clipboard.writeText(text); out.textContent += "\\n[copied]"; }}
  catch (e) {{ out.textContent += "\\n[clipboard blocked - select and copy above]"; }}
}});

document.getElementById("dl2").addEventListener("click", () => {{
  const text = noteLines().join("\\n") || "(nothing ticked yet)";
  const blob = new Blob([text], {{ type: "text/plain" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "audio_picks.txt";
  a.click();
  URL.revokeObjectURL(a.href);
}});

document.getElementById("copy").addEventListener("click", async () => {{
  const list = [...picks].sort().join("\\n");
  out.textContent = picks.size + " picked:" + (picks.size ? "\\n" + list : "");
  try {{ await navigator.clipboard.writeText(list); out.textContent += "\\n[copied]"; }}
  catch (e) {{ out.textContent += "\\n[clipboard blocked - select and copy above]"; }}
}});

document.getElementById("clear").addEventListener("click", () => {{
  picks.clear(); save(); syncChecks(); out.textContent = "cleared";
}});

q.addEventListener("input", apply);
dur.addEventListener("input", apply);
onlyLoop.addEventListener("change", apply);
onlyMusic.addEventListener("change", apply);

notes = readNotes();
syncChecks(); apply();
if (picks.size) showDrop();
</script>
</body>
</html>
"""
    with open(SHEET, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    return SHEET


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-extract", action="store_true",
                    help="rebuild the sheet from an existing audio_inbox/")
    args = ap.parse_args()

    os.makedirs(INBOX, exist_ok=True)
    if not args.no_extract:
        print(f"Extracting to {INBOX}")
        extract()
    else:
        print("Skipping extraction")

    if not have_ffprobe():
        print("WARNING: ffprobe not found, durations will show as --:--",
              file=sys.stderr)

    print("Probing tracks...")
    tracks = collect()
    music_n = sum(1 for t in tracks if t["category"] == "music")
    print(f"  {len(tracks)} track(s): {music_n} music, {len(tracks) - music_n} loop")

    known = [t for t in tracks if t["duration"]]
    if known:
        ds = sorted(t["duration"] for t in known)
        print(f"  duration {ds[0]:.0f}s - {ds[-1]:.0f}s, median {ds[len(ds)//2]:.0f}s")

    sheet = build_sheet(tracks, load_notes())
    print(f"\nOpen: file://{sheet}")


if __name__ == "__main__":
    main()