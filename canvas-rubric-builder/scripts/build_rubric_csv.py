#!/usr/bin/env python3
"""Build a Canvas rubric import .csv from rubric.json (standard library only).

Usage:  python3 build_rubric_csv.py rubric.json [-o Rubric_Name.csv]

Writes the format read by Canvas's "Import Rubric" button (Enhanced Rubrics):
one row per criterion, headers
  Rubric Name, Criteria Name, Criteria Description, Criteria Enable Range,
  then (Rating Name, Rating Description, Rating Points) once per level.
UTF-8 without a byte-order mark: a BOM would break Canvas's "Rubric Name" lookup.
"""
import argparse, csv, json, re, sys
from pathlib import Path

LEVELS = ["Exemplary", "Proficient", "Developing", "Beginning"]
VAGUE = re.compile(r"\b(good|adequate|satisfactory|sufficient|appropriate|poor|excellent)\b", re.I)
# Typographic punctuation -> plain ASCII (escapes keep invisible characters visible)
ASCII = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                       "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " "})


def clean(text):
    return re.sub(r"\s+", " ", str(text or "").translate(ASCII)).strip()


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def validate(data):
    errors, warnings = [], []
    if not clean(data.get("rubric_title")):
        errors.append("rubric_title is missing")
    total = num(data.get("total_points"))
    if total is None or total <= 0:
        errors.append("total_points must be a positive number")
    crits = data.get("criteria")
    if not isinstance(crits, list) or not crits or not all(isinstance(c, dict) for c in crits):
        errors.append("criteria must be a non-empty list of objects")
        return errors, warnings
    if not 3 <= len(crits) <= 6:
        warnings.append(f"{len(crits)} criteria (skill standard is 3 to 6)")
    names, top_sum = set(), 0.0
    for n, c in enumerate(crits, 1):
        name = clean(c.get("name"))
        tag = f"Criterion {n} ({name or 'unnamed'})"
        if not name:
            errors.append(f"{tag}: name is missing")
        elif name.lower() in names:
            errors.append(f"{tag}: duplicate criterion name")
        names.add(name.lower())
        if not clean(c.get("description")):
            errors.append(f"{tag}: description (what this criterion assesses) is missing")
        if not clean(c.get("outcome")):
            warnings.append(f"{tag}: no learning outcome recorded")
        if re.search(r"\band\b|&", name, re.I):
            warnings.append(f"{tag}: name contains 'and', check it assesses only one quality")
        r = c.get("ratings") or []
        if not isinstance(r, list) or not all(isinstance(x, dict) for x in r):
            errors.append(f"{tag}: ratings must be a list of objects with level, points, description")
            continue
        if len(r) != 4:
            errors.append(f"{tag}: needs exactly 4 ratings, has {len(r)}")
            continue
        got = [clean(x.get("level")) for x in r]
        if got != LEVELS:
            errors.append(f"{tag}: ratings must be {', '.join(LEVELS)} in that order, got {', '.join(got)}")
        pts = [num(x.get("points")) for x in r]
        if any(p is None or p < 0 for p in pts):
            errors.append(f"{tag}: every rating needs a single non-negative point value")
            continue
        if any(round(p, 2) != p for p in pts):
            errors.append(f"{tag}: points allow at most 2 decimal places")
        if any(pts[i] <= pts[i + 1] for i in range(3)):
            errors.append(f"{tag}: points must strictly decrease from Exemplary to Beginning, got {pts}")
        top_sum += pts[0]
        descs = [clean(x.get("description")) for x in r]
        for lvl, d in zip(LEVELS, descs):
            if not d:
                errors.append(f"{tag} {lvl}: description is missing")
            elif VAGUE.search(d) and len(d.split()) < 12:
                warnings.append(f"{tag} {lvl}: short description uses '{VAGUE.search(d).group(0)}', anchor it to evidence")
        if len(set(d.lower() for d in descs if d)) < len([d for d in descs if d]):
            errors.append(f"{tag}: two levels have identical descriptions")
    if total is not None and abs(top_sum - total) > 1e-9:
        errors.append(f"Exemplary points add up to {top_sum:g}, but total_points is {total:g}")
    return errors, warnings


def write_csv(data, out):
    header = ["Rubric Name", "Criteria Name", "Criteria Description", "Criteria Enable Range"]
    header += ["Rating Name", "Rating Description", "Rating Points"] * 4
    title = clean(data["rubric_title"])
    with open(out, "w", newline="", encoding="utf-8") as f:   # utf-8, no BOM
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        for c in data["criteria"]:
            row = [title, clean(c["name"]), clean(c["description"]), "false"]
            for x in c["ratings"]:
                p = float(x["points"])
                row += [clean(x["level"]), clean(x["description"]), f"{p:g}"]
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file")
    ap.add_argument("-o", "--output", help="output .csv (default: <rubric_title>.csv)")
    a = ap.parse_args()
    try:
        data = json.loads(Path(a.json_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read {a.json_file}: {e}")
        sys.exit(1)
    if not isinstance(data, dict):
        print("ERROR: rubric.json must contain a JSON object")
        sys.exit(1)
    errors, warnings = validate(data)
    for w_ in warnings:
        print("WARNING:", w_)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print(f"\nExport stopped: {len(errors)} error(s). Fix rubric.json and run again.")
        sys.exit(1)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", data["rubric_title"]).strip("_")[:60] or "rubric"
    out = Path(a.output or f"{slug}_rubric.csv")
    write_csv(data, out)
    total = sum(float(c["ratings"][0]["points"]) for c in data["criteria"])
    print(f"OK: wrote {out} ({len(data['criteria'])} criteria, {total:g} points, {len(warnings)} warning(s))")


if __name__ == "__main__":
    main()
