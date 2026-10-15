#!/usr/bin/env python3
"""Regression tests for the accessibility checkers (no pytest needed).

Builds the synthetic fixtures, runs each checker's check() function, and
compares the issue titles against what each fixture is designed to trigger.

Usage:  python tests/run_tests.py
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(HERE))
import make_fixtures  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# fixture -> (checker, substrings that MUST appear in issue titles, exact issue count)
EXPECTED = {
    "docx_bad.docx": ("check_docx_accessibility", [
        "No heading structure",
        "Table 1: first row may need header marking",
        "Table 1: no alt text",
        "no alt text",                      # image without descr
        "alt text is just a filename",      # descr="image2.png"
        'Hyperlink text "click here."',     # punctuation no longer hides it
        "No document title set",
        "Language set only on individual styles",
    ], 8),
    "docx_skip.docx": ("check_docx_accessibility", [
        'starts at "Heading 2"',
        'Heading level skipped before "Details"',
    ], 2),
    "docx_good.docx": ("check_docx_accessibility", [], 0),
    "pptx_bad.pptx": ("check_pptx_accessibility", [
        "Slide 1: no title placeholder",
        "alt text is just a filename",
        "Slide 2:",                          # grouped picture with no alt text
        "Slide 2: table missing header row flag",
        'Duplicate slide title "Overview"',
    ], 5),
    "pptx_good.pptx": ("check_pptx_accessibility", [], 0),
    "pdf_bad.pdf": ("check_pdf_accessibility", [
        "PDF is not tagged",
        "No real document title",
        "No document language set",
    ], 3),
    "pdf_good.pdf": ("check_pdf_accessibility", [], 0),
}


def main():
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for fname, (checker, must_have, count) in EXPECTED.items():
            path = Path(tmp) / fname
            make_fixtures.BUILDERS[fname](path)
            result = load(checker).check(str(path))
            titles = [t for t, _ in result[0]]
            problems = [m for m in must_have if not any(m in t for t in titles)]
            if len(titles) != count:
                problems.append(f"expected {count} issue(s), got {len(titles)}")
            status = "PASS" if not problems else "FAIL"
            print(f"[{status}] {fname}")
            for p in problems:
                print(f"         missing/mismatch: {p}")
            if problems:
                print("         got: " + "; ".join(titles))
                failures += 1
    print(f"\n{len(EXPECTED) - failures}/{len(EXPECTED)} fixtures behaved as expected.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
