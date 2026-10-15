#!/usr/bin/env python3
"""
Read-only accessibility checker for .pptx files.

Checks the issues that matter most for screen-reader users navigating a
deck: slide titles (present, unique, and tagged as a real title placeholder
-- not just big bold text), reading order, image/chart/SmartArt alt text,
and table header rows.

Does NOT modify the file. Usage:
    python check_pptx_accessibility.py <file.pptx>

Exits 1 if any issues were found, 0 if clean.
"""
import re
import sys
from collections import Counter
from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

FILENAME_LIKE = re.compile(r"\.(png|jpe?g|gif|bmp|tiff?|emf|wmf|svg)$", re.IGNORECASE)
GENERIC_SHAPE_NAME = re.compile(r"^(picture|image|graphic|chart|content placeholder)\s*\d*$", re.IGNORECASE)


DIAGRAM_URI = "http://schemas.openxmlformats.org/drawingml/2006/diagram"


def iter_shapes(shapes):
    """Yield every shape, descending into groups (grouped images were missed before)."""
    for shape in shapes:
        yield shape
        if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP
            yield from iter_shapes(shape.shapes)


def is_smartart(shape):
    gd = shape._element.find(".//" + qn("a:graphicData"))
    return gd is not None and gd.get("uri") == DIAGRAM_URI


def slide_label(i):
    return f"Slide {i}"


def check(path):
    prs = Presentation(path)
    issues = []
    passes = []
    titles = []

    for i, slide in enumerate(prs.slides, start=1):
        label = slide_label(i)

        # 1. Title placeholder present and non-empty
        title_shape = slide.shapes.title
        title_text = title_shape.text.strip() if (title_shape and title_shape.has_text_frame) else ""
        if not title_shape:
            issues.append((
                f"{label}: no title placeholder",
                "This slide has no Title placeholder at all. Even if there's large "
                "bold text that looks like a heading, without the placeholder a "
                "screen reader user tabbing through slides has no way to identify "
                "what this slide is about. Use Insert > Layout with a title, or "
                "the Outline view, rather than a plain text box."
            ))
        elif not title_text:
            issues.append((
                f"{label}: title placeholder is empty",
                "There's a title placeholder but it has no text. Screen readers "
                "announce an empty title as blank when navigating between slides."
            ))
        else:
            titles.append((i, title_text))

        spTree = slide.shapes._spTree

        # 2. Reading order heuristic: title should be the first shape in XML order
        if title_shape is not None:
            top_level = [el for el in spTree if el.tag in (qn("p:sp"), qn("p:pic"), qn("p:graphicFrame"), qn("p:grpSp"), qn("p:cxnSp"))]
            if top_level and top_level[0] is not title_shape._element:
                issues.append((
                    f"{label}: title isn't first in reading order",
                    "Screen readers read shapes in the order they appear in the file, "
                    "not their visual position. The title placeholder isn't the first "
                    "shape here, so it may get read after other content. In "
                    "PowerPoint, use the Selection Pane (or Tab key) to check/reorder."
                ))

        # 3. Images / graphics: alt text
        for shape in iter_shapes(slide.shapes):
            is_picture = shape.shape_type == 13  # MSO_SHAPE_TYPE.PICTURE
            is_graphic = (getattr(shape, "has_chart", False) or is_smartart(shape))
            if not (is_picture or is_graphic):
                continue
            cNvPr = shape._element.find(".//" + qn("p:cNvPr"))
            if cNvPr is None:
                continue
            descr = (cNvPr.get("descr") or "").strip()
            title_attr = (cNvPr.get("title") or "").strip()
            name = cNvPr.get("name") or "image"
            subtree_xml = etree.tostring(cNvPr, encoding="unicode").lower()
            marked_decorative = "decorative" in subtree_xml
            alt_text = descr or title_attr

            if not alt_text and not marked_decorative:
                issues.append((
                    f'{label}: "{name}" has no alt text',
                    "Add a concise description of what this image/chart shows, or "
                    "mark it decorative if it's purely visual."
                ))
            elif alt_text and not marked_decorative and (
                FILENAME_LIKE.search(alt_text) or GENERIC_SHAPE_NAME.match(alt_text.strip())
            ):
                issues.append((
                    f'{label}: "{name}" alt text is just a filename/placeholder ("{alt_text}")',
                    "PowerPoint auto-fills alt text with the source filename or a "
                    "generic label like 'Picture 2' -- that passes a blank check but "
                    "tells a screen reader user nothing about what's actually shown. "
                    "Replace it with a real description of the content."
                ))

        # 4. Table header row
        for shape in iter_shapes(slide.shapes):
            if not getattr(shape, "has_table", False):
                continue
            tbl = shape.table._tbl.find(qn("a:tbl"))
            if tbl is None:
                tbl = shape.table._tbl  # some python-pptx versions return the a:tbl directly
            tblPr = tbl.find(qn("a:tblPr"))
            first_row_flag = tblPr is not None and tblPr.get("firstRow") == "1"
            n_rows = len(shape.table.rows)
            n_cols = len(shape.table.columns)
            if n_rows > 1 and n_cols > 1 and not first_row_flag:
                issues.append((
                    f"{label}: table missing header row flag",
                    "This table has multiple rows/columns but isn't marked with a "
                    "header row. In PowerPoint, select the table > Table Design > "
                    "check 'Header Row' so screen readers announce column labels."
                ))
            elif n_rows > 1 and n_cols > 1:
                passes.append(f"{label}: table header row correctly marked")

    # 5. Duplicate or generic titles across the deck
    text_counts = Counter(t for _, t in titles)
    for text, count in text_counts.items():
        if count > 1:
            slide_nums = [i for i, t in titles if t == text]
            issues.append((
                f'Duplicate slide title "{text}" (slides {", ".join(map(str, slide_nums))})',
                "Screen reader users often jump between slides by title. Identical "
                "titles on multiple slides make it impossible to tell them apart "
                "without opening each one -- add a distinguishing word, e.g. "
                "'Grading (1 of 2)' / 'Grading (2 of 2)'."
            ))

    if titles and not any(text_counts[t] > 1 for _, t in titles):
        passes.append("No duplicate slide titles found")

    return issues, passes


def main():
    if len(sys.argv) != 2:
        print("Usage: python check_pptx_accessibility.py <file.pptx>")
        sys.exit(2)

    path = sys.argv[1]
    issues, passes = check(path)

    print(f"=== PPTX accessibility check: {path} ===\n")
    print(f"{len(issues)} issue(s) found, {len(passes)} check(s) passed.\n")

    if issues:
        print("ISSUES")
        print("-" * 60)
        for title, detail in issues:
            print(f"[FAIL] {title}")
            print(f"       {detail}\n")

    if passes:
        print("PASSED")
        print("-" * 60)
        for p in passes:
            print(f"[OK]   {p}")

    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
