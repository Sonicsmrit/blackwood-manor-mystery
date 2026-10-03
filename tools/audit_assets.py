#!/usr/bin/env python3
import os
import json

def audit():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    images_dir = os.path.join(base_dir, "game", "images")
    manifest_path = os.path.join(base_dir, "assets", "manifest.json")
    
    entries = []
    for root, _, files in os.walk(images_dir):
        for f in sorted(files):
            if f.endswith((".png", ".webp", ".jpg")):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, os.path.join(base_dir, "game"))
                size = os.path.getsize(full_path)
                
                kind = "unknown"
                char = None
                mood = None
                
                if "characters" in rel_path:
                    kind = "sprite"
                    parts = rel_path.split(os.sep)
                    if len(parts) >= 3:
                        char = parts[2]
                    if char == "marika":
                        # e.g. Marika_angry.webp
                        mood = f.replace("Marika_", "").replace(".webp", "").replace(".png", "")
                elif "bg" in rel_path:
                    kind = "background"
                elif "props" in rel_path:
                    kind = "prop"
                elif "ui" in rel_path:
                    kind = "ui"
                
                entries.append({
                    "path": rel_path,
                    "filename": f,
                    "kind": kind,
                    "character": char,
                    "mood": mood,
                    "size_bytes": size
                })
    
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as out:
        json.dump({"total_assets": len(entries), "assets": entries}, out, indent=2)
    
    print(f"Audited {len(entries)} assets. Saved to {manifest_path}")

if __name__ == "__main__":
    audit()
