#!/usr/bin/env python3
"""docs/piano/ is BUILD OUTPUT and must not be tracked in git.

Why this guard exists
---------------------
pages.yml builds the site with ``build_type: workflow``: it runs
``scripts/stage_pages_piano.py`` and uploads ``docs/`` as the Pages artifact.
What is served is therefore ALWAYS the freshly staged output, never the copy
committed in the repository.

While docs/piano/ was tracked, it looked like an ordinary editable page. It is
not. PR #49 and PR #52 both edited it, both merged green, and neither reached
the live site, because the next deploy regenerated the directory from
web/keyboard.html and discarded the edits. Live served one thing, git held
another, and nothing failed.

The earlier fix for this was a drift check: regenerate, and fail if the result
differs from what was committed. That makes the loss visible, but it does not
make it impossible, and it only blocks a merge if a branch protection rule
requires it. This repository has no branch protection and no rulesets, so a red
drift job blocks nothing -- an auto-merge lands the PR anyway and the edit is
still lost.

This guard removes the trap instead of reporting it. If docs/piano/ is not in
the index, a fresh clone does not contain it, an edit to it cannot be staged
for commit, and a PR that tries to change the published page by hand is empty
rather than silently discarded. That holds without branch protection.

Fail-closed: if this script cannot determine trackedness -- no git, not a work
tree, git returning non-zero -- it exits non-zero rather than assuming the tree
is clean. A guard that cannot run properly must not report a pass.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = "docs/piano/"


def tracked_under(prefix: str) -> list[str]:
    """Paths tracked in the index under `prefix`. Raises on any git failure."""
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", prefix],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "FATAL: `git ls-files` failed -- cannot determine what is tracked.\n"
            "       Refusing to run: a guard that cannot check must not report a pass.\n"
            f"       git said: {proc.stderr.strip()}"
        )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def self_test() -> None:
    """Prove the guard catches what it claims to catch.

    The positive case is not hypothetical: `git ls-files docs/piano/` returning
    entries is exactly the state of main before this change. The self-test pins
    both directions so the check cannot quietly become a no-op -- a guard that
    has only ever been observed passing is a check that agrees with itself.
    """
    ok = True

    def case(name: str, got: object, want: object) -> None:
        nonlocal ok
        good = got == want
        ok = ok and good
        print(f"  {'ok  ' if good else 'FAIL'}   {name}")
        if not good:
            print(f"         got {got!r}, want {want!r}")

    # A populated listing must be treated as a failure, and an empty one as a pass.
    case("tracked entries present  -> verdict FAIL", verdict(["docs/piano/index.html"]), False)
    case("no tracked entries       -> verdict PASS", verdict([]), True)
    case("a single stray file      -> verdict FAIL", verdict(["docs/piano/now_playing.js"]), False)

    # The real repository must answer the question at all: web/keyboard.html is
    # the source and must exist, or this guard is protecting nothing.
    src = ROOT / "web" / "keyboard.html"
    case("web/keyboard.html is the source and exists", src.is_file(), True)

    if not ok:
        raise SystemExit("self-test FAILED")
    print("self-test: the guard fails on a tracked docs/piano/ and passes on an absent one.")


def verdict(entries: list[str]) -> bool:
    """True == acceptable. Pure, so the self-test can exercise both directions."""
    return not entries


def main() -> None:
    if "--self-test" in sys.argv:
        self_test()
        return

    entries = tracked_under(GENERATED)
    if not verdict(entries):
        print("docs/piano/ is tracked in git, but it is build output.", file=sys.stderr)
        print(file=sys.stderr)
        for path in entries:
            print(f"    tracked: {path}", file=sys.stderr)
        print(
            "\n"
            "pages.yml stages docs/piano/ from web/ on every deploy and uploads the\n"
            "result, so the committed copy is never what gets served. Keeping it in\n"
            "the tree invites an edit that will be silently discarded -- which is\n"
            "what happened to PR #49 and PR #52.\n"
            "\n"
            "Fix: stop tracking it.\n"
            "    git rm -r --cached docs/piano\n"
            "and keep the `docs/piano/` entry in .gitignore.\n"
            "\n"
            "Edit the page at web/keyboard.html. To preview the staged result:\n"
            "    python3 scripts/stage_pages_piano.py",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("docs/piano/ is not tracked — the published page is generated, not hand-editable.")


if __name__ == "__main__":
    main()
