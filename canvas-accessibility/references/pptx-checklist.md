# PowerPoint (.pptx) accessibility: what to check and how to fix it

Run `scripts/check_pptx_accessibility.py <file>` first for a deterministic
report, then fix directly (with the `pptx` skill's edit approach if available,
otherwise through python-pptx/lxml). Always
render before/after to images and compare — PowerPoint reading order and
placeholder types are easy to get subtly wrong in ways that don't show up
until a screen reader (or the Selection Pane) is used.

## 1. Slide titles

**Why it matters:** Screen reader users navigate between slides largely by
title, the same way sighted users skim a deck by glancing at slide headers.
A title that's a plain text box instead of the actual **Title placeholder**
is invisible to that navigation, even if it looks identical on screen.

**How to check:** Does `slide.shapes.title` exist and have non-empty text?
A big, bold, top-of-slide text box that *isn't* a placeholder of type
`title`/`ctrTitle` will pass a visual check but fail this one.

**How to fix:** Use a layout with a title placeholder (Insert > Reset, or
change layout), or convert an existing text box into the title placeholder
by editing `<p:nvSpPr><p:nvPr><p:ph type="title"/>` — but it's more reliable
to duplicate the layout's title placeholder and move the existing text into
it, since retrofitting the `<p:ph>` type can conflict with the shape's
existing formatting.

## 2. Unique, descriptive titles across the deck

**Why it matters:** If slide 12 and slide 19 are both titled "Overview",
someone jumping between them by title has no way to tell which is which.

**How to fix:** Add a distinguishing word or number: "Grading Policy (1 of
2)" / "Grading Policy (2 of 2)", or make titles specific to content rather
than generic section labels repeated across the deck.

## 3. Reading order

**Why it matters:** Screen readers read shapes in the order they appear in
the slide's XML (`p:spTree`), which is **not necessarily** the visual
top-to-bottom order. A title placed visually first but added to the slide
last will be read last.

**How to check:** In PowerPoint, open the Selection Pane (Home > Arrange >
Selection Pane, or Alt+F10) — it lists shapes in reverse reading order (top
of the pane list = last read). Programmatically, walk `spTree`'s children in
document order and check the title placeholder comes first, then check
content flows in a sensible order after it.

**How to fix:** Reorder the XML elements within `<p:spTree>` (moving a shape
element earlier/later in document order), or in the PowerPoint UI, use the
Selection Pane's reorder arrows. This is easiest to do by hand in PowerPoint
after the report flags which slide has the problem — reordering many shapes
via raw XML risks breaking z-order-dependent visual layouts (overlapping
shapes), so prefer flagging this one for manual fix over auto-editing XML
unless the slide is simple.

## 4. Alt text on images, charts, and SmartArt

**Why it matters:** Same as Word — no alt text means a screen reader has
nothing to describe.

**Watch for a specific trap:** PowerPoint (and python-pptx) often
auto-populates alt text with the source **filename** ("IMG_4521.png") or a
generic shape name ("Picture 2", "Chart 1") when an image is inserted. This
technically isn't blank, so a naive "is descr empty?" check will miss it —
check whether the alt text matches a filename pattern or a generic
`Picture N` / `Chart N` label, and flag it as low-quality even though it's
"present."

**How to fix:** Replace with a real description of the content (a diagram's
meaning, a chart's takeaway) or mark the image decorative if it's purely
visual (right-click > Edit Alt Text > "Mark as decorative" in PowerPoint;
this sets an `a16:decorative` extension in the XML).

## 5. Table header rows

**Why it matters:** Same rationale as Word tables — without a header flag, a
screen reader can't distinguish column labels from data.

**How to check:** For a table (`a:tbl`) with more than one row and column,
does `<a:tblPr>` have `firstRow="1"`? This is the same flag PowerPoint's
Table Design > "Header Row" checkbox controls — it's both a visual style
toggle and the accessibility signal.

**How to fix:** Set `firstRow="1"` on `<a:tblPr>` (or check the box in
PowerPoint's Table Design tab, which is more reliable since it also applies
the header row's visual style so the fix isn't invisible to sighted users
either).

## 6. Color contrast and color-only meaning

These need a human eye — flag them in the report rather than trying to
auto-fix:
- Text color vs. background contrast (WCAG AA wants roughly 4.5:1 for normal
  text).
- Any slide that conveys meaning through color alone (e.g., a status
  indicator that's "red = urgent" with no icon or text label alongside it).

## 7. Text embedded in images

If a slide's content is a screenshot containing text (e.g., a UI mockup with
labels baked into the image), that text is invisible to screen readers no
matter how good the image's alt text is. Flag this for the instructor to
decide whether to rebuild the slide with real text/shapes or accept a
detailed alt-text description as a substitute — this is a judgment call, not
something to silently fix.
