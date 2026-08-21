#!/usr/bin/env python3
"""Enforce the FlexAID∆S v2 palette contract on the crayon piano.

Two things this makes structurally impossible rather than remembered:

  1. Off-palette chrome. Every colour literal in the page's CSS must be a
     canonical v2 key, an allow-listed functional colour, or a neutral
     (CIELAB C* <= 20). The forbidden triad -- teal 40.8, salmon 60.8,
     gold 77.8 -- cannot pass that test.

  2. Crayon-coloured text below 12px. LP's rule is stated for Cherry, but
     the measured worst case on this page was A/Blueberry at 1.70:1, so
     the check covers every chromatic paint, not just Cherry.

The twelve pitch crayons are exempt from (1) by an explicit allow-list in
piano/palette_allowlist.json -- D# Lemon is hue 60.0 deg, pure yellow, and
the highest-contrast colour in the set. They are NOT exempt from (2).

Usage:  python3 scripts/check_palette.py [--json]
Exit 0 clean, 1 on any violation.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "piano" / "palette_allowlist.json"
ROOT_FONT_PX = 16.0


# ── colour maths ────────────────────────────────────────────────────────────
def parse_hex(text: str) -> tuple[int, int, int] | None:
    s = text.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def parse_rgb_fn(text: str) -> tuple[tuple[int, int, int], float] | None:
    m = re.match(r"rgba?\(([^)]*)\)", text, re.I)
    if not m:
        return None
    parts = [p.strip() for p in re.split(r"[,\s/]+", m.group(1)) if p.strip()]
    if len(parts) < 3:
        return None
    try:
        chan = []
        for p in parts[:3]:
            chan.append(round(float(p[:-1]) * 2.55) if p.endswith("%") else round(float(p)))
        alpha = 1.0
        if len(parts) > 3:
            a = parts[3]
            alpha = float(a[:-1]) / 100 if a.endswith("%") else float(a)
    except ValueError:
        return None
    return (chan[0], chan[1], chan[2]), alpha


def lab_chroma(rgb: tuple[int, int, int]) -> float:
    def lin(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in rgb)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(x / 0.95047), f(y / 1.0), f(z / 1.08883)
    return math.hypot(500 * (fx - fy), 200 * (fy - fz))


def hue_deg(rgb: tuple[int, int, int]) -> float:
    r, g, b = (v / 255 for v in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return 0.0
    d = mx - mn
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60.0


# ── CSS extraction ──────────────────────────────────────────────────────────
def strip_comments(css: str) -> str:
    """Comments document the violations we fixed; they must not be scanned."""
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def style_blocks(html: str) -> str:
    return strip_comments("\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)))


COLOUR_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\([^)]*\)")
FONT_SIZE_RE = re.compile(r"font-size:\s*([0-9.]+)(rem|px|em)")
FONT_SHORTHAND_RE = re.compile(r"\bfont:\s*[^;]*?([0-9.]+)(rem|px|em)\s*[/;]")


def declaration_blocks(css: str):
    """Yield (selector, body) for each rule. Nested at-rules are flattened;
    good enough because we only ask 'does this body pair a small font-size
    with a chromatic paint'."""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel, body = m.group(1).strip(), m.group(2)
        if ":" not in body:
            continue
        yield sel.splitlines()[-1].strip() if sel else "?", body


def font_px(body: str) -> float | None:
    m = FONT_SIZE_RE.search(body) or FONT_SHORTHAND_RE.search(body)
    if not m:
        return None
    val, unit = float(m.group(1)), m.group(2)
    return val * ROOT_FONT_PX if unit in ("rem", "em") else val


# ── the checks ──────────────────────────────────────────────────────────────
def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    rules = contract["rules"]
    max_chroma = float(rules["neutral_max_lab_chroma"])
    text_floor = float(rules["crayon_text_min_font_px"])

    allowed = {v["hex"].lower() for v in contract["canonical_chrome"].values()}
    allowed |= {e["hex"].lower() for e in contract["functional_exceptions"]}
    crayon_rgbs = {
        tuple(v["rgb"]) for k, v in contract["pitch_crayons"].items() if not k.startswith("$")
    }

    violations: list[str] = []
    checked: list[str] = []

    for rel in contract["files_checked"]:
        path = ROOT / rel
        if not path.is_file():
            violations.append(f"{rel}: listed in the contract but missing from the tree")
            continue
        raw = path.read_text(encoding="utf-8")
        css = style_blocks(raw) if rel.endswith(".html") else strip_comments(raw)
        checked.append(rel)
        violations += scan_css(css, rel, contract, text_rules=rel.endswith(".html"))

    violations += scan_pitch_encoding(contract)

    if "--json" in sys.argv:
        print(json.dumps({"checked": checked, "violations": violations}, indent=2))
    else:
        for v in violations:
            print(f"  ✗ {v}")
        print(
            f"\npalette contract: {len(checked)} file(s) checked, "
            f"{len(violations)} violation(s)"
        )
        if not violations:
            print("  ✓ chrome is canonical v2 or neutral")
            print("  ✓ no crayon painted as text below the 12px floor")
            print("  ✓ 12 pitch crayons match the pinned encoding")
    return 1 if violations else 0


def scan_css(css: str, rel: str, contract: dict, text_rules: bool = True) -> list[str]:
    """All colour rules for one stylesheet. Pure, so --self-test can drive it."""
    rules = contract["rules"]
    max_chroma = float(rules["neutral_max_lab_chroma"])
    text_floor = float(rules["crayon_text_min_font_px"])
    allowed = {v["hex"].lower() for v in contract["canonical_chrome"].values()}
    allowed |= {e["hex"].lower() for e in contract["functional_exceptions"]}
    crayon_rgbs = {
        tuple(v["rgb"]) for k, v in contract["pitch_crayons"].items() if not k.startswith("$")
    }
    violations: list[str] = []

    if True:
        # ── 1. chrome palette ────────────────────────────────────────────
        for lit in COLOUR_RE.findall(css):
            low = lit.lower()
            if low in allowed:
                continue
            rgb, alpha = None, 1.0
            if low.startswith("#"):
                rgb = parse_hex(low)
            else:
                got = parse_rgb_fn(low)
                if got:
                    rgb, alpha = got
            if rgb is None:
                continue
            if alpha == 0:
                continue
            if rgb in crayon_rgbs:
                violations.append(
                    f"{rel}: pitch crayon {lit} hardcoded in CSS chrome. The crayons "
                    f"are applied at runtime via paintEl(); they are not chrome literals."
                )
                continue
            c = lab_chroma(rgb)
            if c <= max_chroma:
                continue
            h = hue_deg(rgb)
            band = ""
            for name, (lo, hi) in rules["forbidden_chrome_hue_bands"].items():
                if name.startswith("$"):
                    continue
                inside = (lo <= h <= hi) if lo <= hi else (h >= lo or h <= hi)
                if inside:
                    band = f" -- lands in the forbidden {name} band"
                    break
            violations.append(
                f"{rel}: off-palette chrome {lit} (C*={c:.1f} > {max_chroma}, hue {h:.1f}deg){band}. "
                f"Use a canonical v2 key or a neutral."
            )

        # ── 2. no chromatic paint as text below the 12px floor ───────────
    if text_rules:
        for sel, body in declaration_blocks(css):
            px = font_px(body)
            if px is None or px >= text_floor:
                continue
            colours = re.findall(r"(?:^|[;{\s])color:\s*([^;]+)", body)
            for decl in colours:
                d = decl.strip()
                if "--crayon" in d or "--cherry" in d:
                    violations.append(
                        f"{rel}: `{sel}` sets font-size {px:.2f}px and paints text with "
                        f"`{d}`. Crayon-coloured text below {text_floor:.0f}px is the "
                        f"defect this check exists to stop. Raise the size or move the "
                        f"hue off the glyph."
                    )
                    continue
                for lit in COLOUR_RE.findall(d):
                    rgb = parse_hex(lit) if lit.startswith("#") else (parse_rgb_fn(lit) or ((0, 0, 0), 0))[0]
                    if rgb and lab_chroma(rgb) > max_chroma:
                        violations.append(
                            f"{rel}: `{sel}` sets font-size {px:.2f}px and paints text "
                            f"{lit} (C*={lab_chroma(rgb):.1f}). Below the "
                            f"{text_floor:.0f}px floor."
                        )

    return violations


def scan_pitch_encoding(contract: dict) -> list[str]:
    """The safety encoding is pinned, so it cannot drift silently either."""
    kb = (ROOT / "web" / "keyboard.html").read_text(encoding="utf-8")
    out = []
    for pc, spec in contract["pitch_crayons"].items():
        if pc.startswith("$"):
            continue
        r, g, b = spec["rgb"]
        if f"rgb: [{r}, {g}, {b}]" not in kb:
            out.append(
                f"web/keyboard.html: pitch crayon {pc} ({spec['pencil']}) is no longer "
                f"rgb({r}, {g}, {b}). The safety encoding is pinned by "
                f"piano/palette_allowlist.json -- change both, deliberately, or neither."
            )
    return out


# ── self-test ───────────────────────────────────────────────────────────────
# A guard that has only ever been seen to pass proves nothing. These drive the
# real rule functions with synthetic CSS carrying the exact defects this change
# removed, and assert each one is caught.
SELF_TEST_CASES = [
    ("the 7.68px Do defect, exactly as it shipped",
     '.kb-key .note { font-size: 0.48rem; color: var(--crayon, var(--muted)); }', True),
    ("Cherry as 10px text",
     '.tag { font-size: 10px; color: var(--cherry); }', True),
    ("a raw crayon hex as small text",
     '.tag { font-size: 0.5rem; color: #fb0207; }', True),
    ("the forbidden cyan, --teal #22D3EE",
     ':root { --teal: #22D3EE; }', True),
    ("the forbidden yellow, --gold #FBBF24",
     ':root { --gold: #FBBF24; }', True),
    ("the forbidden salmon, --harm-fatal-strong #ff6b7d",
     ':root { --harm: #ff6b7d; }', True),
    ("a pitch crayon hardcoded into chrome",
     ':root { --x: rgb(251, 2, 7); }', True),
    ("Cherry at 12px, which the rule permits",
     '.tag { font-size: 12px; color: var(--cherry); }', False),
    ("Cherry at 1rem, which the rule permits",
     '.err { font-size: 1rem; color: var(--cherry); }', False),
    ("Magnesium as small text, the fix that shipped",
     '.kb-key .note { font-size: 0.5rem; color: var(--magnesium); }', False),
    ("a canonical key as chrome",
     ':root { --mint: #45E0A8; }', False),
    ("a neutral surface",
     ':root { --bg: #0a0e14; --ink: #d4dced; }', False),
    ("the allow-listed hit ring",
     '.hit { box-shadow: inset 0 0 0 2px #b6ff55; }', False),
    ("a comment describing a violation must not be read as one",
     '/* was color: #fb0207 at 0.48rem */ .a { color: var(--ink); }', False),
]


def self_test(contract: dict) -> int:
    failures = 0
    print("check_palette --self-test\n")
    for name, css, should_flag in SELF_TEST_CASES:
        got = scan_css(strip_comments(css), "<self-test>", contract)
        flagged = bool(got)
        ok = flagged == should_flag
        failures += 0 if ok else 1
        verdict = "ok  " if ok else "FAIL"
        want = "caught" if should_flag else "allowed"
        print(f"  {verdict} {want:<8} {name}")
        if not ok:
            print(f"       expected flagged={should_flag}, got {got or 'no violations'}")
    print(f"\n  {len(SELF_TEST_CASES) - failures}/{len(SELF_TEST_CASES)} self-tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    _contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if "--self-test" in sys.argv:
        raise SystemExit(self_test(_contract))
    raise SystemExit(main())
