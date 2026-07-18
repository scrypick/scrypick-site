"""Refresh scout.html's numbers from the pro-stats export, IN PLACE.

The scout tier list carries curated judgment (tier letters + champion blurbs)
we deliberately preserve. This only rewrites the DATA fields per row — Prio
(pick+ban presence), WR (wins/picks), and games (pick count) — from
data/pro_stats.json (exported by poly-trading from the deduped competitive
DB, so folding a new event like EWC in is automatic). Tiers, blurbs, badges,
counter panels and page structure are left exactly as they are.

    python scripts/refresh_scout.py            # writes scout.html
    python scripts/refresh_scout.py --check     # writes scout.new.html only
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLE_MAP = {"top": "Top", "jungle": "Jungle", "mid": "Mid",
            "bot": "Bot", "support": "Support"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stats", type=Path, default=ROOT / "data" / "pro_stats.json")
    ap.add_argument("--scout", type=Path, default=ROOT / "scout.html")
    ap.add_argument("--check", action="store_true",
                    help="write scout.new.html instead of overwriting")
    args = ap.parse_args(argv)

    view = json.loads(args.stats.read_text(encoding="utf-8"))["views"]["all_pro"]
    total = view["games"]
    # (champion_lower, role_lower) -> stats
    stat: dict[tuple[str, str], dict] = {}
    for c in view["champions"]:
        key = (c["champion"].lower(), c["role"].lower())
        stat[key] = c

    html = args.scout.read_text(encoding="utf-8")
    updated = [0]
    missed: list[str] = []

    def _row(m: re.Match) -> str:
        block = m.group(0)
        raw = (re.search(r'data-name="([^"]+)"', block) or [None, ""])[1]
        name = _html.unescape(raw)  # data-name stores &#x27; etc; JSON has literal '
        role = (re.search(r'data-role="([^"]+)"', block) or [None, ""])[1]
        role_full = ROLE_MAP.get(role, "").lower()
        s = stat.get((name.lower(), role_full))
        if not s:
            missed.append(f"{name}/{role}")
            return block  # champ-role not in fresh data — keep curated row as-is
        prio = f"{round(s['presence'] * 100)}%"
        wr = f"{round((s['wr'] or 0) * 100)}%"
        games = f"{s['picks']}g"
        block = re.sub(r'(<span class="pnum">)[^<]*(</span>)', rf'\g<1>{prio}\g<2>', block)
        block = re.sub(r'(<span class="wr">)[^<]*(</span>)', rf'\g<1>{wr}\g<2>', block)
        block = re.sub(r'(<span class="picks">)[^<]*(</span>)', rf'\g<1>{games}\g<2>', block)
        updated[0] += 1
        return block

    # Each srow is a self-contained div; match non-greedily up to its close.
    html = re.sub(r'<div class="srow"[^>]*>.*?</div>\s*(?=<div class="srow"|<section)',
                  _row, html, flags=re.DOTALL)

    # Provenance: bump the game count everywhere it's quoted (match any prior
    # number so re-runs keep working, not just the launch value).
    html = re.sub(r'[\d,]+ pro games', f"{total:,} pro games", html)

    out = args.scout.with_suffix(".new.html") if args.check else args.scout
    out.write_text(html, encoding="utf-8")
    print(json.dumps({"rows_updated": updated[0], "total_games": total,
                      "rows_kept_as_is": missed, "out": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
