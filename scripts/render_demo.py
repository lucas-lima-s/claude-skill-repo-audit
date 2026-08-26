from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import json


def _card_svg(report: dict, *, background: str, foreground: str, accent: str, muted: str) -> str:
    target = report.get("target_name") or report.get("kind", "repo")
    gate = report.get("gate", "?")
    scorecard = report.get("scorecard") or report.get("totals") or {}
    fail = scorecard.get("fail", 0)
    warn = scorecard.get("warn", 0)
    info = scorecard.get("info", 0)
    ok = scorecard.get("ok", 0)
    gate_color = "#e5484d" if gate == "BLOCK" else "#30a46c"

    rows = [("FAIL", fail, "#e5484d"), ("WARN", warn, "#f5a623"), ("INFO", info, muted), ("OK", ok, "#30a46c")]
    max_count = max(1, fail, warn, info, ok)

    bars = []
    y = 96
    for label, count, color in rows:
        width = max(2, int(240 * count / max_count)) if count else 0
        bars.append(
            f'<text x="24" y="{y + 14}" font-family="Consolas, monospace" font-size="13" '
            f'fill="{foreground}">{label}</text>'
            f'<rect x="90" y="{y}" width="{width}" height="16" rx="3" fill="{color}"/>'
            f'<text x="{90 + width + 8}" y="{y + 13}" font-family="Consolas, monospace" font-size="12" '
            f'fill="{muted}">{count}</text>'
        )
        y += 28

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="230" viewBox="0 0 420 230">
  <rect width="420" height="230" rx="12" fill="{background}"/>
  <text x="24" y="34" font-family="Consolas, monospace" font-size="16" font-weight="bold" \
fill="{foreground}">repo-audit</text>
  <text x="24" y="56" font-family="Consolas, monospace" font-size="12" fill="{muted}">target: {target}</text>
  <rect x="320" y="20" width="76" height="26" rx="6" fill="{gate_color}"/>
  <text x="358" y="37" font-family="Consolas, monospace" font-size="13" fill="#ffffff" \
text-anchor="middle">{gate}</text>
  <line x1="24" y1="72" x2="396" y2="72" stroke="{accent}" stroke-width="1"/>
  {"".join(bars)}
</svg>
"""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="render_demo.py", description="Render a report as light/dark demo SVGs.")
    parser.add_argument("--json", dest="json_path", required=True)
    parser.add_argument("--out-dir", default="docs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    report = json.loads(Path(args.json_path).read_text(encoding="utf-8"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    light = _card_svg(report, background="#ffffff", foreground="#1a1a1a", accent="#e2e2e2", muted="#666666")
    dark = _card_svg(report, background="#1a1a1a", foreground="#f5f5f5", accent="#333333", muted="#a0a0a0")

    (out_dir / "demo-light.svg").write_text(light, encoding="utf-8")
    (out_dir / "demo-dark.svg").write_text(dark, encoding="utf-8")

    print(f"wrote {out_dir / 'demo-light.svg'} and {out_dir / 'demo-dark.svg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
