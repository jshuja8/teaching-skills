---
name: canvas-accessibility
description: Audits and fixes accessibility issues in Word (.docx) and PowerPoint (.pptx) course materials, and audits (without editing) PDF materials, before posting to Canvas or another LMS. Covers missing heading structure, tables without header rows, missing/low-quality table and image alt text (including placeholder alt text that's just a filename), non-descriptive hyperlink text, missing document title/language metadata, PowerPoint slide titles and reading order, and untagged PDFs. Use whenever the user asks to check, audit, fix, or improve accessibility of a document, slide deck, or PDF; mentions a Canvas/LMS accessibility score; mentions WCAG, Section 508, ADA, or UDL compliance; or uploads a docx/pptx/pdf asking to "clean it up" or "get it ready to post." Trigger even without the word "accessibility" if symptoms are described (e.g. "Canvas flagged this," "no headings show in the outline").
---

# Canvas course material accessibility review

Course materials get reviewed by a screen reader far more often than most
instructors realize — not just for students with documented accommodations,
but because Canvas's own accessibility checker scores every upload, and a
low score is visible institution-wide. The goal here is to find and fix the
issues that most affect screen-reader students and the Canvas checker,
without changing how the document looks to everyone else.

**The three file types are handled differently — read this before doing
anything else:**

| File type | Mode | Why |
|---|---|---|
| `.docx` | **Fix directly** | Structural issues live in readable XML; fixes are safe and mechanical once understood. |
| `.pptx` | **Fix directly** | Same reasoning, with more caution around reading order (see below). |
| `.pdf`  | **Report only, never edit** | Accessibility depends on a tag tree that can't be safely generated or patched by script — a wrong auto-tag is worse than an honest "needs Acrobat" flag. See `references/pdf-checklist.md` for why. |

## Workflow

### Step 1: Identify the file type and run the checker script first

Before touching anything, run the matching read-only script to get a
deterministic baseline:

```bash
python scripts/check_docx_accessibility.py <file.docx>
python scripts/check_pptx_accessibility.py <file.pptx>
python scripts/check_pdf_accessibility.py <file.pdf>
```

Each prints a plain-text report (issues found + checks passed) and exits 1
if anything failed. Treat this as a starting checklist, not the final word —
it catches the mechanically-detectable issues (missing headings, missing
header-row flags, missing/placeholder alt text, missing metadata) but not
things that need human judgment (color contrast, whether alt text is
*accurate*, whether reading order makes sense on a complex slide). Read the
relevant reference file's "what this doesn't catch" section and give those a
quick manual look too.

### Step 2: For docx and pptx, settle how you'll edit the file

This skill covers *what* to check and *why* it matters. For the mechanics of
editing safely:

- **If a `docx` or `pptx` file-format skill is available in this
  environment** (Claude's built-in ones usually are), read its SKILL.md
  before editing. It covers the unzip → edit → validate → rezip workflow and
  schema gotchas in more depth.
- **If not**, edit through `python-docx` / `python-pptx` and `lxml` (the
  same libraries the checker scripts use): open the file, change the XML
  elements described in the checklists through the object model or
  `element.find(qn(...))`, and save to a **new** file. Never overwrite the
  instructor's original.

Then read the matching checklist in `references/` for the specific
accessibility fixes:

- `references/docx-checklist.md` — headings, table headers, table/image alt
  text (including correct XML element ordering, which is easy to get wrong
  for `tblCaption`/`tblDescription`), hyperlink text, document title,
  language.
- `references/pptx-checklist.md` — slide titles (and the placeholder-vs-text-box
  trap), unique titles, reading order, image/chart alt text (including the
  filename/placeholder trap), table header rows, and which issues to flag
  rather than auto-fix.

### Step 3: Fix docx/pptx issues in place

Apply fixes directly in the unpacked XML, matching the patterns in the
checklists. Two things matter more than the individual fixes:

1. **Preserve visual appearance exactly.** Every fix in the docx/pptx
   checklists is additive (a style reference, a flag, an attribute) rather
   than a change to existing formatting — direct run/paragraph formatting
   still overrides style defaults, so applying `Heading2` to an
   already-bold-red-underlined paragraph doesn't change how it looks. If a
   fix you're considering *would* change the visual layout, flag it for the
   instructor's review instead of applying it silently.
2. **Reading order in PowerPoint needs more caution than everything else
   here.** Reordering shapes in `p:spTree` can break z-order-dependent
   layouts (overlapping shapes, layered graphics). If a slide's shape
   arrangement is simple (a title + one content block), reordering is safe.
   If it's a complex layout, flag the reading-order issue in your summary
   rather than silently reordering — getting this wrong is worse than
   leaving it for the instructor to fix by hand in the Selection Pane.

### Step 4: Validate and visually confirm nothing changed

Render the original and the fixed file to images and compare them side by
side (for example, `soffice --headless --convert-to pdf` followed by
`pdftoppm -png`). If the docx skill's `validate.py` is available, also run
it against the original to catch schema-ordering errors. Otherwise, at
minimum, re-open the fixed file with `python-docx` / `python-pptx` and confirm
it converts with LibreOffice without errors. Never skip this step; a schema
ordering mistake (like `tblCaption` in the wrong position) can look right in
a text diff but fail when Word opens the file.

Then re-run the checker script on the fixed file to confirm the issues it
originally found are now resolved — this also catches anything the manual
fix pass missed.

### Step 5: For PDFs, produce a report — do not edit the file

Run `check_pdf_accessibility.py`, then write up findings using
`references/pdf-checklist.md` as a guide: identify likely root cause (source
file export settings vs. no accessible source available) and give the
specific fix path (Acrobat's Prepare for Accessibility wizard, or re-export
settings for Word/PowerPoint). Be explicit that this skill does not modify
PDFs and that a clean script result doesn't mean the PDF is fully
accessible — say plainly what still needs a human pass in Acrobat.

### Step 6: Summarize plainly

Whether you fixed something or just reported it, tell the instructor in
plain language what was found and what changed (or, for PDFs, what to do
next) — a short list is enough, not a line-by-line XML diff. If you fixed
issues automatically, still name them, since silently fixing things the
instructor doesn't know were broken makes it hard for them to learn the
pattern for materials they build without this skill's help.

## A note on scope

This skill focuses on the issues that most commonly tank a Canvas
accessibility score and matter most to screen-reader users: heading
structure, table headers, alt text, link text, and core document metadata.
It does not attempt automated color-contrast remediation, does not rewrite
prose for readability/plain-language, and does not touch PDFs beyond
reporting. When something falls outside this scope but you notice it (e.g.
a color-only status indicator, dense jargon in a student-facing handout),
mention it once in the summary rather than trying to fix it — some of these
are judgment calls the instructor should make, not defaults to silently
apply.

## Dependencies

The checker scripts need Python 3.9+ with `python-docx`, `python-pptx`,
`pikepdf`, and `lxml`. These are usually already present in Claude's
sandbox. If a script fails with `ModuleNotFoundError`, install them:

```bash
pip install python-docx python-pptx pikepdf lxml --break-system-packages
```

`tests/run_tests.py` builds synthetic files that break each rule and checks
that every script flags exactly what it should. Run it after changing any
checker.

