# assessment-question-generator

A Claude skill that writes multiple-choice questions from your lecture
material and exports them as a quiz you can import into Canvas.

## What you get

- **Four options per question**, with distractors built from real
  misconceptions (a reversed concept, a wrong formula, a partly correct
  answer), not filler
- **A rationale for every option**, which becomes per-answer feedback in Canvas
- **Metadata per question:** learning outcome, Bloom's level, difficulty, and the slide or page it came from
- **A Canvas QTI 1.2 .zip** plus an instructor answer key (.csv)
- **Optional variants:** 2 or more versions of a question (same concept,
  different numbers or code) exported as a Canvas question group, so each
  student sees a different version

Claude proposes a plan first (concepts, Bloom's levels), shows every question
in a review table, and exports only after you approve. If you're short on
time, you can tell it to skip straight to the file.

## Install

**Claude apps (claude.ai, desktop):** zip the `assessment-question-generator`
folder and upload it as a custom skill in Claude's settings.

**Claude Code:** copy the folder into `~/.claude/skills/`.

Then attach your slides or notes and ask something like *"Write 10 quiz
questions from this lecture for Canvas"* or *"Make 3 variants of each
calculation question."*

## Using the export script on its own

`scripts/build_qti.py` uses only the Python standard library:

```bash
python scripts/build_qti.py examples/questions.json -o Sample_Quiz_qti.zip
python scripts/build_qti.py examples/questions.json --no-feedback   # hide rationales from students
```

It validates first and stops with an ERROR for problems such as no correct
answer (or two), a missing rationale, duplicate options, or a group asking
students to see more versions than exist. It prints a WARNING for an answer
key bunched on one letter, a correct answer much longer than the
distractors, "all/none of the above", and variants that differ in difficulty.

`examples/questions.json` is a made-up 5-point quiz on algorithm analysis
with one question group (two binary-search variants).

## Importing into Canvas

Settings → Import Course Content → Content Type **QTI .zip file** → choose
the .zip → Import. The quiz arrives unpublished as a Classic Quiz, with
variants as question groups. Preview it before publishing.

## Tests

```bash
python tests/run_tests.py
```

21 checks: the example builds a valid package; question groups use the same
XML structure Canvas's own QTI exporter writes; the quiz total counts each
group once; every question gives full credit only to its keyed option;
feedback can be turned off; and broken input is rejected or flagged. Tested
on Python 3.11 and 3.13.

## Limitations

- Multiple choice only (no multiple-answer, matching or numeric questions).
- Imports as a Classic Quiz. Canvas can migrate it to New Quizzes.
- Variants are written by Claude, so check that every version is equally hard. The script warns when the difficulty labels differ, but it can't judge the questions themselves.
