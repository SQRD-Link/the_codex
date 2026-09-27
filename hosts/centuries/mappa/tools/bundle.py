#!/usr/bin/env python3
"""Bundle site/ into one self-contained HTML file (data, CSS and JS inlined).

Useful for sharing, printing, or opening from file:// where fetch() of the
JSON files is blocked.

    python3 tools/bundle.py            -> dist/pianta-della-rete.html
    python3 tools/bundle.py out.html
"""
import base64
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def main() -> None:
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "pianta-della-rete.html"
    html = (SITE / "index.html").read_text()
    css = (SITE / "mappa.css").read_text()
    # inline the self-hosted fonts so the single file works offline
    css = re.sub(
        r"url\((fonts/[^)]+\.woff2)\)",
        lambda m: "url(data:font/woff2;base64,"
        + base64.b64encode((SITE / m.group(1)).read_bytes()).decode()
        + ")",
        css,
    )
    js = (SITE / "mappa.js").read_text()
    data = {
        "policy": json.loads((SITE / "data" / "policy.json").read_text()),
        "inventory": json.loads((SITE / "data" / "inventory.json").read_text()),
    }
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace('<link rel="stylesheet" href="mappa.css">', f"<style>\n{css}\n</style>")
    html = html.replace(
        '<script src="mappa.js"></script>',
        f"<script>window.MAPPA_DATA={blob};</script>\n<script>\n{js}\n</script>",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
