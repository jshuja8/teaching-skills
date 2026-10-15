# canvas-rubric-builder

A Claude skill that turns an assignment sheet into an analytic grading
rubric and exports a CSV for Canvas's **Import Rubric** tool.

## What you get

- **3 to 6 criteria**, each assessing one quality of the work and tied to a
  learning outcome or an explicit requirement in the assignment sheet
- **4 levels** for every criterion (Exemplary, Proficient, Developing,
  Beginning), each with a single point value
- **Level descriptions written for students**, naming what a grader can see in
  the work rather than words like "good" or "adequate"
- **Points that add up** exactly to the assignment total

Claude proposes the criteria and weights first and waits for your approval.
It then shows the full rubric as a table and exports only after you sign off.

## Install

**Claude apps (claude.ai, desktop):** zip the `canvas-rubric-builder` folder
and upload it as a custom skill in Claude's settings.

**Claude Code:** copy the folder into `~/.claude/skills/`.

Then attach an assignment sheet and ask something like *"Build a 100-point
Canvas rubric for this assignment."*

## Using the export script on its own

`scripts/build_rubric_csv.py` uses only the Python standard library:

```bash
python scripts/build_rubric_csv.py examples/rubric.json -o Research_Poster_rubric.csv
```

It validates the rubric before writing anything. It stops with an ERROR if
points don't add up, don't decrease from level to level, or have more than
2 decimals, or if levels are missing or out of order. It prints a WARNING for
likely double-barreled criteria ("Analysis and Writing") and short level
descriptions that lean on vague words.

`examples/` has a sample `rubric.json` for a made-up research poster
assignment and the CSV it produces.

## Importing into Canvas

1. In your course, open **Rubrics** in the course navigation and click
   **Import Rubric** (requires Canvas Enhanced Rubrics).
2. Upload the CSV. **Don't open and re-save it in Excel first**: Excel can
   add a byte-order mark, which stops Canvas from finding the "Rubric Name"
   column.
3. The rubric arrives as a draft. Open it in edit mode, check Type (Scale),
   Scored, rating display (Points) and order (High to Low), then click
   **Save Rubric**.
4. Attach it to the assignment from the assignment page.

## Tests

```bash
python tests/run_tests.py
```

The tests export the example rubric and read the CSV back using the same
column-matching rules as Canvas's importer (`lib/rubric_csv_importer.rb` in
canvas-lms). They also confirm that each kind of broken rubric is rejected.
Tested on Python 3.11 and 3.13.

## Limitations

- Fixed at 4 levels with the names above.
- Single point values only; Canvas's point-range option is always off.
- Learning outcomes are kept for your review but aren't part of the CSV,
  because Canvas's import format has no outcome column.
