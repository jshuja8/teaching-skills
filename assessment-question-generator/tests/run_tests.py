#!/usr/bin/env python3
"""Regression tests for build_qti.py (standard library only).

Checks that the example quiz builds a well-formed Canvas QTI package
(manifest, assessment, quiz settings), that question groups use the
structure Canvas's own QTI exporter writes, and that broken input is
rejected or warned about.

Usage:  python tests/run_tests.py
"""
import copy
import csv
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_qti.py"
EXAMPLE = json.loads((ROOT / "examples" / "questions.json").read_text(encoding="utf-8"))
NS = {"q": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"}


def run(data, tmp, name="quiz", extra=()):
    src, out = Path(tmp) / f"{name}.json", Path(tmp) / f"{name}.zip"
    src.write_text(json.dumps(data), encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), "-o", str(out), *extra],
                       capture_output=True, text=True)
    return p.returncode, p.stdout, out


def parts(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        quiz = next(n for n in names if n.endswith(".xml") and "/" in n and not n.endswith("assessment_meta.xml"))
        meta = next(n for n in names if n.endswith("assessment_meta.xml"))
        return names, ET.fromstring(z.read(quiz)), z.read(meta).decode()


def mutated(fn):
    d = copy.deepcopy(EXAMPLE)
    fn(d)
    return d


def q(d, qid):
    return next(x for x in d["questions"] if x["id"] == qid)


ERRORS = {
    "no correct option": (lambda d: q(d, "Q1")["options"][0].update(correct=False), "exactly one correct"),
    "two correct options": (lambda d: q(d, "Q1")["options"][1].update(correct=True), "exactly one correct"),
    "empty stem": (lambda d: q(d, "Q2").update(stem=""), "empty stem"),
    "missing rationale": (lambda d: q(d, "Q3")["options"][2].update(rationale=""), "missing rationale"),
    "duplicate options": (lambda d: q(d, "Q5")["options"][1].update(text="512"), "duplicate option"),
    "pick larger than group": (lambda d: d["groups"]["G1"].update(pick=3), "has only 2"),
    "bad group points": (lambda d: d["groups"]["G1"].update(points_per_item=0), "points_per_item"),
    "option not an object": (lambda d: q(d, "Q1")["options"].__setitem__(0, "O(n)"), "list of objects"),
}

WARNINGS = {
    "real length clue": (lambda d: q(d, "Q3")["options"][3].update(
        text="The array is sorted in ascending order by the exact key that the search compares against"),
        "length clue"),
    "variants differ in difficulty": (lambda d: q(d, "Q4b").update(difficulty="hard"), "differ in difficulty"),
    "all of the above": (lambda d: q(d, "Q2")["options"][1].update(text="All of the above"), "all/none of the above"),
}


def main():
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        print(f"[{'PASS' if ok else 'FAIL'}] {label}" + ("" if ok else f"\n         {str(detail)[:400]}"))
        fails += not ok

    n_checks = 0
    with tempfile.TemporaryDirectory() as tmp:
        code, out, z = run(EXAMPLE, tmp, "example")
        check(code == 0 and "WARNING" not in out, "example builds with no warnings", out); n_checks += 1
        names, root, meta = parts(z)
        check("imsmanifest.xml" in names and any(n.endswith("assessment_meta.xml") for n in names),
              "package has manifest, assessment and quiz settings", names); n_checks += 1

        top = root.find("q:assessment/q:section", NS)
        groups = top.findall("q:section", NS)
        loose = top.findall("q:item", NS)
        check(len(groups) == 1 and len(loose) == 4, "1 question group + 4 standalone items at top level",
              f"{len(groups)} groups, {len(loose)} items"); n_checks += 1

        g = groups[0]
        sel = g.find("q:selection_ordering/q:selection", NS)
        ok = (sel is not None
              and sel.findtext("q:selection_number", namespaces=NS) == "1"
              and sel.findtext("q:selection_extension/q:points_per_item", namespaces=NS) == "1"
              and len(g.findall("q:item", NS)) == 2
              and g.get("title") == "Binary search trace (variants)")
        check(ok, "group uses Canvas's selection_ordering structure with both variants inside"); n_checks += 1

        check("<points_possible>5.0</points_possible>" in meta,
              "quiz total counts a group once (4 + 1 = 5 points, not 6)"); n_checks += 1

        # every item: score 100 is set on exactly the keyed option
        all_items = root.findall(".//q:item", NS)
        ok = True
        for item in all_items:
            ids = [r.get("ident") for r in item.findall(".//q:response_label", NS)]
            full = [c for c in item.findall(".//q:respcondition", NS) if c.find("q:setvar", NS) is not None]
            title = item.get("title").split(" | ")[0]
            key_idx = next(i for i, o in enumerate(q(EXAMPLE, title)["options"]) if o["correct"])
            ok &= len(full) == 1 and full[0].findtext("q:conditionvar/q:varequal", namespaces=NS) == ids[key_idx]
        check(ok, "each question awards full credit to its keyed option only"); n_checks += 1

        check(all(len(i.findall("q:itemfeedback", NS)) == 4 for i in all_items),
              "per-option feedback included by default"); n_checks += 1
        _, _, z2 = run(EXAMPLE, tmp, "nofb", ["--no-feedback"])
        check(not parts(z2)[1].findall(".//q:itemfeedback", NS), "--no-feedback removes feedback"); n_checks += 1

        key = list(csv.DictReader(open(z.with_name(z.stem + "_answer_key.csv"), encoding="utf-8")))
        check(len(key) == 6 and {r["group"] for r in key} == {"", "G1"} and key[3]["key"] == "B",
              "answer key lists all 6 questions with group column", key[:1]); n_checks += 1

        # the short numeric options that used to trigger a false length-clue warning
        short = mutated(lambda d: q(d, "Q5")["options"].__setitem__(3, {"text": "11", "correct": True, "rationale": "r"}))
        q(short, "Q5")["options"][0]["text"] = "6"
        _, out, _ = run(short, tmp, "short")
        check("length clue" not in out, "no false length-clue warning for '11' vs '6'", out); n_checks += 1

        for label, (fn, expect) in ERRORS.items():
            code, out, path = run(mutated(fn), tmp, "err")
            check(code == 1 and expect in out and not path.exists(), f"rejects: {label}", out); n_checks += 1

        for label, (fn, expect) in WARNINGS.items():
            code, out, _ = run(mutated(fn), tmp, "warn")
            check(code == 0 and expect in out, f"warns: {label}", out); n_checks += 1

    print(f"\n{n_checks - fails}/{n_checks} checks passed.")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
