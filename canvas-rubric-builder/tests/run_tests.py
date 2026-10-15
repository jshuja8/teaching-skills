#!/usr/bin/env python3
"""Regression tests for build_rubric_csv.py (standard library only).

1. The example rubric exports, and the CSV reads back correctly when parsed
   the way Canvas's importer parses it (header matching rules from
   canvas-lms lib/rubric_csv_importer.rb).
2. Each broken rubric is rejected with the expected ERROR.

Usage:  python tests/run_tests.py
"""
import copy
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_rubric_csv.py"
EXAMPLE = json.loads((ROOT / "examples" / "rubric.json").read_text(encoding="utf-8"))


def run(data, tmp, name="r"):
    src = Path(tmp) / f"{name}.json"
    out = Path(tmp) / f"{name}.csv"
    src.write_text(json.dumps(data), encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), "-o", str(out)],
                       capture_output=True, text=True)
    return p.returncode, p.stdout, out


def canvas_parse(path):
    """Mirror Canvas's importer: exact keys for rubric/criterion columns,
    case-insensitive substring match for rating columns, points to_f.round(2)."""
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "file starts with a UTF-8 BOM"
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    idx = {k: [i for i, h in enumerate(header) if k in h.lower()]
           for k in ("rating name", "rating description", "rating points")}
    col = {h: header.index(h) for h in ("Rubric Name", "Criteria Name", "Criteria Description", "Criteria Enable Range")}
    parsed = []
    for r in body:
        ratings = [{"name": r[n], "desc": r[d], "points": round(float(r[p].replace(",", ".")), 2)}
                   for n, d, p in zip(idx["rating name"], idx["rating description"], idx["rating points"])]
        parsed.append({"rubric": r[col["Rubric Name"]], "name": r[col["Criteria Name"]],
                       "range": r[col["Criteria Enable Range"]], "ratings": ratings})
    return parsed


def broken(mutate):
    d = copy.deepcopy(EXAMPLE)
    mutate(d)
    return d


ERROR_CASES = {
    "points do not add up": (lambda d: d["criteria"][0]["ratings"][0].update(points=11), "add up to 51"),
    "points not decreasing": (lambda d: d["criteria"][1]["ratings"][2].update(points=16), "strictly decrease"),
    "wrong level order": (lambda d: d["criteria"][0]["ratings"].reverse(), "in that order"),
    "three levels": (lambda d: d["criteria"][0]["ratings"].pop(), "exactly 4 ratings"),
    "duplicate criterion": (lambda d: d["criteria"][1].update(name="Research Question"), "duplicate criterion name"),
    "identical descriptions": (lambda d: d["criteria"][3]["ratings"][1].update(
        description=d["criteria"][3]["ratings"][0]["description"]), "identical descriptions"),
    "three decimals": (lambda d: d["criteria"][3]["ratings"][1].update(points=6.125), "2 decimal places"),
    "rating not an object": (lambda d: d["criteria"][2]["ratings"].__setitem__(1, "oops"), "list of objects"),
    "missing title": (lambda d: d.update(rubric_title=""), "rubric_title is missing"),
}

WARNING_CASES = {
    "double-barreled name": (lambda d: d["criteria"][3].update(name="Citations and Formatting"), "contains 'and'"),
    "vague short level": (lambda d: d["criteria"][3]["ratings"][1].update(description="Good citations."), "uses 'Good'"),
}


def main():
    fails = 0

    def report(ok, label, detail=""):
        nonlocal fails
        print(f"[{'PASS' if ok else 'FAIL'}] {label}" + ("" if ok else f"\n         {detail}"))
        fails += not ok

    with tempfile.TemporaryDirectory() as tmp:
        code, out, csv_path = run(EXAMPLE, tmp, "example")
        report(code == 0 and "WARNING" not in out, "example exports with no warnings", out)
        if code == 0:
            rows = canvas_parse(csv_path)
            exp = EXAMPLE["criteria"]
            ok = (len(rows) == len(exp)
                  and all(r["rubric"] == EXAMPLE["rubric_title"] for r in rows)
                  and [r["name"] for r in rows] == [c["name"] for c in exp]
                  and all(r["range"] == "false" for r in rows)
                  and all([x["points"] for x in r["ratings"]] == [x["points"] for x in c["ratings"]]
                          for r, c in zip(rows, exp))
                  and sum(r["ratings"][0]["points"] for r in rows) == EXAMPLE["total_points"])
            report(ok, "CSV reads back correctly with Canvas's parsing rules", rows)

        for label, (mutate, expect) in ERROR_CASES.items():
            code, out, path = run(broken(mutate), tmp, "err")
            report(code == 1 and expect in out and not path.exists(), f"rejects: {label}", out.strip())

        for label, (mutate, expect) in WARNING_CASES.items():
            code, out, _ = run(broken(mutate), tmp, "warn")
            report(code == 0 and "WARNING" in out and expect in out, f"warns: {label}", out.strip())

    total = 2 + len(ERROR_CASES) + len(WARNING_CASES)
    print(f"\n{total - fails}/{total} checks passed.")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
