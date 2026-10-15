#!/usr/bin/env python3
"""
Read-only accessibility auditor for PDFs.

PDF remediation (tagging, reading order, alt text) is NOT automated by this
script or the skill it belongs to -- reliably fixing an untagged PDF needs
Adobe Acrobat Pro's accessibility tools, or regenerating the PDF from a
tagged source (an accessible Word/PowerPoint file exported with tags kept).
This script only reports what's wrong and points to the right fix.

Usage:
    python check_pdf_accessibility.py <file.pdf>

Exits 1 if any issues were found, 0 if the basic checks pass. A passing
result here does NOT mean the PDF is fully accessible -- it means the
easy-to-detect blockers (no tags at all, no title, no language) are absent.
Reading order, alt text quality, and table structure inside a tagged PDF
still need a human pass in Acrobat's Accessibility Checker.
"""
import os
import re
import sys
import pikepdf

PLACEHOLDER_TITLES = {"untitled", "untitled document", "untitled1", "document1"}
WORD_AUTOTITLE = re.compile(r"^Microsoft Word\b", re.IGNORECASE)


def check(path):
    issues = []
    passes = []

    with pikepdf.open(path) as pdf:
        root = pdf.Root

        # 1. Tagged PDF (the single biggest blocker)
        mark_info = root.get("/MarkInfo")
        marked = bool(mark_info and mark_info.get("/Marked", False))
        has_struct_tree = "/StructTreeRoot" in root

        if not marked or not has_struct_tree:
            issues.append((
                "PDF is not tagged",
                "There's no structure tree (or the Marked flag isn't set), which "
                "means screen readers have no reliable way to determine reading "
                "order, headings, or which text is a table vs. a caption vs. body "
                "text. This is the accessibility issue that matters most for PDFs "
                "and it can't be safely automated here -- fix it by either (a) "
                "regenerating the PDF from its original Word/PowerPoint file using "
                "an export option that keeps accessibility tags (Word: File > "
                "Save As > PDF > Options > check 'Document structure tags for "
                "accessibility'), or (b) running Acrobat Pro's Prepare for "
                "Accessibility > Autotag Document, then fixing what its "
                "Accessibility Checker flags by hand."
            ))
        else:
            passes.append("PDF has a tagged structure tree")

        # 2. Document title (metadata, distinct from filename)
        info = pdf.docinfo if pdf.docinfo is not None else {}
        title = str(info.get("/Title", "")).strip() if info else ""
        filename_stem = os.path.splitext(os.path.basename(path))[0].strip().lower()
        is_placeholder = (
            not title
            or title.lower() in PLACEHOLDER_TITLES
            or WORD_AUTOTITLE.match(title)
            or title.lower() == filename_stem
        )
        if is_placeholder:
            # Built outside the f-string: a backslash inside an f-string
            # expression is a SyntaxError before Python 3.12.
            title_state = "empty" if not title else f'a generic placeholder ("{title}")'
            issues.append((
                "No real document title in metadata" if title else "No document title in metadata",
                f"The Title metadata is {title_state}. "
                "Screen readers and browser tabs show this field when present -- a "
                "default like 'untitled' or the raw filename tells a listener "
                "nothing. Set a real title in Acrobat (File > Properties > "
                "Description > Title) or from the original source file before "
                "exporting."
            ))
        else:
            passes.append(f'Document title set: "{title}"')

        # 3. Document language
        lang = root.get("/Lang")
        if not lang:
            issues.append((
                "No document language set",
                "Without a /Lang entry, screen readers may guess the wrong "
                "pronunciation rules. Set it in Acrobat (File > Properties > "
                "Advanced > Reading Options > Language)."
            ))
        else:
            passes.append(f'Document language set: "{lang}"')

        # 4. Page count sanity note for very large tagged/untagged decks
        n_pages = len(pdf.pages)

    return issues, passes, n_pages


def main():
    if len(sys.argv) != 2:
        print("Usage: python check_pdf_accessibility.py <file.pdf>")
        sys.exit(2)

    path = sys.argv[1]
    issues, passes, n_pages = check(path)

    print(f"=== PDF accessibility audit: {path} ({n_pages} page(s)) ===\n")
    print(f"{len(issues)} issue(s) found, {len(passes)} check(s) passed.\n")
    print("Note: this is a report only. This skill does not modify PDFs --")
    print("fixes need Acrobat Pro or re-exporting from a tagged source.\n")

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
