# PDF accessibility: audit only, never auto-fix

PDFs are structurally different from docx/pptx: accessibility depends on a
**tag tree** (`/StructTreeRoot`) that maps the visual content to a logical
reading order, headings, and table structure. There's no reliable, safe way
to generate or repair that tag tree with a script — Adobe's own "Autotag"
feature uses proprietary heuristics refined over years and still usually
needs manual correction afterward. Attempting to hand-build or patch a tag
tree here would likely produce something that validates but reads worse than
having no tags at all (a screen reader trusts the tags completely, so wrong
tags are worse than none).

**This skill only reports PDF issues. It does not modify PDFs.** Always say
this explicitly in the summary so it's not mistaken for a completed fix.

## What the checker script covers

`scripts/check_pdf_accessibility.py` checks the handful of things that are
both important and reliably detectable without deep structural analysis:

1. **Tagged / not tagged** (`/MarkInfo /Marked` + presence of
   `/StructTreeRoot`) — the single biggest factor. An untagged PDF is
   essentially just an image of text to a screen reader, regardless of
   anything else about it.
2. **Document title metadata** — checks for empty *and* placeholder values
   (`untitled`, `Document1`, `Microsoft Word - ...`, or a title that's
   just the filename) since these pass a naive blank check but are useless.
3. **Document language** (`/Lang` on the document catalog).

A clean result from the script means these three blockers are absent — it
does **not** mean the PDF is fully accessible. Reading order, alt text
quality, and correct table/heading tagging inside an already-tagged PDF
still require Acrobat's Accessibility Checker and a human pass.

## What to tell the instructor

Structure the report around **root cause**, since the fix path differs:

- **If the PDF was exported from Word/PowerPoint/Canvas:** the fastest and
  most reliable fix is almost always to fix accessibility in the *source*
  file (using the docx/pptx checks) and re-export with tags preserved:
  - Word: File > Save As > PDF > **Options** > check "Document structure
    tags for accessibility" (unchecked by default in some versions/export
    paths — this is the most common reason a Word-sourced PDF ends up
    untagged).
  - PowerPoint: File > Export > Create PDF/XPS — PowerPoint includes tags
    by default when exporting, but "Print" (Ctrl+P > Save as PDF) does
    **not** tag the output — this is a common accidental cause of untagged
    PDFs from decks that are otherwise fine.
- **If there's no accessible source file to regenerate from** (scanned
  document, third-party PDF, etc.): recommend Adobe Acrobat Pro's **Prepare
  for Accessibility** wizard — Autotag Document, then run the
  **Accessibility Checker** (Acrobat's built-in one, not this script) and
  work through its findings, particularly reading order and table headers,
  which often need manual correction even after autotagging.
- **Scanned/image-only PDFs** need OCR before tagging means anything — check
  whether the PDF has a real text layer at all (if extracting text returns
  nothing or garbage, that's the issue to raise first).

## Framing the "flag only" limitation for the instructor

Be direct that this is a deliberate scope boundary, not a missing feature:
automated PDF tagging tools exist but produce inconsistent, sometimes
actively wrong, results without human review — and a screen-reader user
trusts PDF tags completely, so shipping a bad auto-tag is worse than
shipping an honest "needs Acrobat" flag. Recommending Acrobat's guided
workflow (or a source re-export) gets a genuinely accessible result; a
scripted patch would not.
