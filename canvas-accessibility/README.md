# canvas-accessibility

A Claude skill that audits and fixes accessibility problems in course
materials before they go up on Canvas (or any other LMS).

| File type | What the skill does |
|---|---|
| Word (`.docx`) | Finds and **fixes** issues without changing how the document looks |
| PowerPoint (`.pptx`) | Finds and **fixes** issues; flags complex reading-order problems for a manual fix |
| PDF | **Reports only.** Explains whether to re-export from the source file or use Acrobat Pro |

## What it checks

- **Headings:** no heading styles at all, the document's own title left untagged, and skipped levels (for example, Heading 2 straight to Heading 4)
- **Tables:** missing header rows (after checking that row 1 really is a header) and missing table alt text
- **Images, charts and SmartArt:** missing alt text, and alt text that is only a filename or "Picture 2"
- **Links:** text like "click here" or "here."
- **Metadata:** document title and default language
- **PowerPoint only:** missing or duplicate slide titles, and a title that isn't first in reading order
- **PDF only:** untagged files, placeholder titles such as "Microsoft Word - handout.docx", and missing language

It does not fix color contrast, rewrite prose, or edit PDFs. It mentions these in its summary for the instructor to decide on.

## Install

**Claude apps (claude.ai, desktop):** zip the `canvas-accessibility` folder
and upload it as a custom skill in Claude's settings.

**Claude Code:** copy the folder into `~/.claude/skills/` (personal) or
`.claude/skills/` in a project.

Then ask Claude something like *"Check this handout for accessibility before
I post it to Canvas"* and attach the file.

## Using the checker scripts on their own

The three scripts in `scripts/` are read-only and work without Claude:

```bash
pip install -r requirements.txt
python scripts/check_docx_accessibility.py handout.docx
python scripts/check_pptx_accessibility.py lecture.pptx
python scripts/check_pdf_accessibility.py syllabus.pdf
```

Each prints a report and exits with code 1 if it finds issues, so it also
works as a pass/fail check. See `examples/` for sample output.

## Tests

```bash
python tests/run_tests.py
```

This builds synthetic Word, PowerPoint and PDF files that break specific
rules (and clean files that break none), then checks that each script flags
exactly what it should. The test files contain no real course material.
Tested on Python 3.11 and 3.13.

## Folder layout

```
canvas-accessibility/
├── SKILL.md              instructions Claude follows
├── references/           per-format checklists: what to check, why, how to fix
├── scripts/              read-only checker scripts
├── tests/                fixture generator and regression tests
└── examples/             sample checker output
```

## Limitations

- A clean script result is a baseline, not a certificate. Alt-text
  accuracy, color contrast and reading order on complex slides still need a
  human look.
- Word has no way to mark row headers (only column headers), so the skill
  uses table alt text for tables laid out by row.
- Images in Word headers and footers are not checked.
