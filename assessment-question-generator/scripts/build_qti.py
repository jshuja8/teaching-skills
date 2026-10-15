#!/usr/bin/env python3
"""Build a Canvas-importable QTI 1.2 .zip from questions.json (standard library only).

Usage:  python3 build_qti.py questions.json [-o quiz.zip] [--no-feedback]

Package layout follows the format Canvas imports via
Settings > Import Course Content > "QTI .zip file" (same layout as text2qti):
  imsmanifest.xml
  <quiz_id>/<quiz_id>.xml          QTI 1.2 questestinterop
  <quiz_id>/assessment_meta.xml    Canvas quiz settings
Also writes <name>_answer_key.csv (instructor copy: key, rationales, metadata).

Variants: questions that share a "group" value become one Canvas question
group; each student is shown `pick` of them (default 1). Optional settings per
group go in a top-level "groups" object: {"G1": {"title": "...", "pick": 1}}.
"""
import argparse, csv, datetime, hashlib, html, json, re, sys, zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xesc, quoteattr

LETTERS = "ABCDEFGH"


def uid(*parts):
    return "g" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:30]


def to_html(text, code=None):
    """Plain text -> small HTML: ```fenced``` blocks, `inline code`, line breaks."""
    out = []
    for i, chunk in enumerate(re.split(r"```(?:[\w+-]*\n)?(.*?)```", text or "", flags=re.S)):
        if i % 2:
            out.append("<pre><code>" + html.escape(chunk.strip("\n")) + "</code></pre>")
        elif chunk.strip():
            h = html.escape(chunk.strip())
            h = re.sub(r"`([^`]+)`", r"<code>\1</code>", h)
            out.append("<p>" + h.replace("\n", "<br/>") + "</p>")
    if code:
        out.append("<pre><code>" + html.escape(code.strip("\n")) + "</code></pre>")
    return "".join(out) or "<p></p>"


def validate(data):
    errors, warnings = [], []
    qs = data.get("questions")
    if not data.get("quiz_title"):
        errors.append("quiz_title is missing")
    if not isinstance(qs, list) or not qs or not all(isinstance(q, dict) for q in qs):
        errors.append("questions must be a non-empty list of objects")
        return errors, warnings
    bad = [q.get("id") or f"Q{n}" for n, q in enumerate(qs, 1)
           if not isinstance(q.get("options"), list) or not all(isinstance(o, dict) for o in q["options"])]
    if bad:
        errors.append(f"options must be a list of objects in: {', '.join(bad)}")
        return errors, warnings
    stems, key_pos = set(), []
    for n, q in enumerate(qs, 1):
        tag = q.get("id") or f"Q{n}"
        opts = q.get("options") or []
        if not (q.get("stem") or "").strip():
            errors.append(f"{tag}: empty stem")
        if not 2 <= len(opts) <= 8:
            errors.append(f"{tag}: needs 2-8 options, has {len(opts)}")
        elif len(opts) != 4:
            warnings.append(f"{tag}: has {len(opts)} options (skill standard is 4)")
        correct = [i for i, o in enumerate(opts) if o.get("correct") is True]
        if len(correct) != 1:
            errors.append(f"{tag}: must have exactly one correct option, has {len(correct)}")
        else:
            key_pos.append(correct[0])
        texts = []
        for i, o in enumerate(opts):
            t = (o.get("text") or "").strip()
            if not t:
                errors.append(f"{tag} option {LETTERS[i]}: empty text")
            if not (o.get("rationale") or "").strip():
                errors.append(f"{tag} option {LETTERS[i]}: missing rationale")
            if re.search(r"\b(all|none) of the above\b", t, re.I):
                warnings.append(f"{tag} option {LETTERS[i]}: uses 'all/none of the above'")
            texts.append(t)
        if len(set(t.lower() for t in texts)) != len(texts):
            errors.append(f"{tag}: duplicate option text")
        if len(correct) == 1 and len(texts) > 2:
            lens = [len(t) for t in texts]
            others = [l for i, l in enumerate(lens) if i != correct[0]]
            if lens[correct[0]] > 1.5 * max(others) and lens[correct[0]] - max(others) >= 15:
                warnings.append(f"{tag}: correct option is much longer than the distractors (length clue)")
        s = re.sub(r"\s+", " ", (q.get("stem") or "").lower()).strip()
        if s in stems:
            errors.append(f"{tag}: duplicate stem")
        stems.add(s)
        for f in ("outcome", "bloom", "difficulty", "source"):
            if not q.get(f):
                warnings.append(f"{tag}: metadata '{f}' is empty")
        for flag in q.get("flags") or []:
            warnings.append(f"{tag}: flagged {flag}")
    # Question groups (variants)
    groups, settings = {}, data.get("groups") or {}
    if not isinstance(settings, dict):
        errors.append("groups must be an object keyed by group id")
        settings = {}
    for q in qs:
        g = q.get("group")
        if g is not None:
            groups.setdefault(str(g), []).append(q)
    for g in settings:
        if g not in groups:
            warnings.append(f"group {g}: settings given but no question uses it")
    for g, members in groups.items():
        cfg = settings.get(g) or {}
        pick = cfg.get("pick", 1)
        gpts = cfg.get("points_per_item", data.get("points_per_question", 1))
        if not isinstance(gpts, (int, float)) or isinstance(gpts, bool) or gpts <= 0:
            errors.append(f"group {g}: points_per_item must be a positive number")
        if not isinstance(pick, int) or isinstance(pick, bool) or pick < 1:
            errors.append(f"group {g}: pick must be a positive whole number")
        elif pick > len(members):
            errors.append(f"group {g}: pick is {pick} but the group has only {len(members)} question(s)")
        elif pick == len(members):
            warnings.append(f"group {g}: pick equals group size, so every student sees every variant")
        for f in ("outcome", "difficulty"):
            vals = {str(m.get(f) or "") for m in members}
            if len(vals) > 1:
                warnings.append(f"group {g}: variants differ in {f} ({', '.join(sorted(vals))}); students may get unequal questions")

    if len(key_pos) >= 4:
        counts = {LETTERS[i]: key_pos.count(i) for i in range(4)}
        if max(counts.values()) > 0.5 * len(key_pos):
            warnings.append(f"answer key is unbalanced across positions: {counts}")
    return errors, warnings


def mattext(h):
    return f'<mattext texttype="text/html">{xesc(h)}</mattext>'


def item_xml(q, n, quiz_id, points, feedback):
    qid = uid(quiz_id, n, q["stem"])
    opts = q["options"]
    aids = [uid(qid, i, o["text"]) for i, o in enumerate(opts)]
    key = next(i for i, o in enumerate(opts) if o.get("correct") is True)
    meta = [q.get("id") or f"Q{n}", q.get("outcome"), q.get("bloom"), q.get("difficulty")]
    title = " | ".join(str(m) for m in meta if m)[:250]
    x = [f'      <item ident="{qid}" title={quoteattr(title)}>',
         '        <itemmetadata><qtimetadata>',
         '          <qtimetadatafield><fieldlabel>question_type</fieldlabel><fieldentry>multiple_choice_question</fieldentry></qtimetadatafield>',
         f'          <qtimetadatafield><fieldlabel>points_possible</fieldlabel><fieldentry>{points}</fieldentry></qtimetadatafield>',
         f'          <qtimetadatafield><fieldlabel>original_answer_ids</fieldlabel><fieldentry>{",".join(aids)}</fieldentry></qtimetadatafield>',
         f'          <qtimetadatafield><fieldlabel>assessment_question_identifierref</fieldlabel><fieldentry>{uid(qid, "ref")}</fieldentry></qtimetadatafield>',
         '        </qtimetadata></itemmetadata>',
         '        <presentation>',
         f'          <material>{mattext(to_html(q["stem"], q.get("stem_code")))}</material>',
         '          <response_lid ident="response1" rcardinality="Single"><render_choice>']
    for aid, o in zip(aids, opts):
        x.append(f'            <response_label ident="{aid}"><material>{mattext(to_html(o["text"]))}</material></response_label>')
    x += ['          </render_choice></response_lid>', '        </presentation>', '        <resprocessing>',
          '          <outcomes><decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/></outcomes>']
    if feedback:
        for aid in aids:
            x.append(f'          <respcondition continue="Yes"><conditionvar><varequal respident="response1">{aid}</varequal></conditionvar>'
                     f'<displayfeedback feedbacktype="Response" linkrefid="{aid}_fb"/></respcondition>')
    x.append(f'          <respcondition continue="No"><conditionvar><varequal respident="response1">{aids[key]}</varequal></conditionvar>'
             '<setvar action="Set" varname="SCORE">100</setvar></respcondition>')
    x.append('        </resprocessing>')
    if feedback:
        for aid, o in zip(aids, opts):
            x.append(f'        <itemfeedback ident="{aid}_fb"><flow_mat><material>{mattext(to_html(o["rationale"]))}</material></flow_mat></itemfeedback>')
    x.append('      </item>')
    return "\n".join(x)


def build(data, out_zip, feedback=True):
    title = data["quiz_title"]
    quiz_id = uid("quiz", title, datetime.datetime.now().isoformat())
    pts = data.get("points_per_question", 1)
    qs = data["questions"]
    settings = data.get("groups") or {}
    parts, seen, total_points = [], set(), 0.0
    for n, q in enumerate(qs, 1):
        g = q.get("group")
        if g is None:
            parts.append(item_xml(q, n, quiz_id, pts, feedback))
            total_points += float(pts)
            continue
        g = str(g)
        if g in seen:
            continue  # emitted with the group's first question
        seen.add(g)
        cfg = settings.get(g) or {}
        pick = cfg.get("pick", 1)
        gpts = cfg.get("points_per_item", pts)
        members = [(m, q2) for m, q2 in enumerate(qs, 1) if str(q2.get("group")) == g and q2.get("group") is not None]
        title = cfg.get("title") or f"Question group {g}"
        sec = [f'      <section ident="{uid(quiz_id, "group", g)}" title={quoteattr(str(title))}>',
               '        <selection_ordering><selection>',
               f'          <selection_number>{pick}</selection_number>',
               f'          <selection_extension><points_per_item>{gpts}</points_per_item></selection_extension>',
               '        </selection></selection_ordering>']
        sec += [item_xml(q2, m, quiz_id, gpts, feedback) for m, q2 in members]
        sec.append('      </section>')
        parts.append("\n".join(sec))
        total_points += float(gpts) * pick
    items = "\n".join(parts)
    assessment = f'''<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.imsglobal.org/xsd/ims_qtiasiv1p2 http://www.imsglobal.org/xsd/ims_qtiasiv1p2p1.xsd">
  <assessment ident="{quiz_id}" title={quoteattr(title)}>
    <qtimetadata><qtimetadatafield><fieldlabel>cc_maxattempts</fieldlabel><fieldentry>1</fieldentry></qtimetadatafield></qtimetadata>
    <section ident="root_section">
{items}
    </section>
  </assessment>
</questestinterop>
'''
    shuffle = "true" if data.get("shuffle_answers") else "false"
    meta = f'''<?xml version="1.0" encoding="UTF-8"?>
<quiz identifier="{quiz_id}" xmlns="http://canvas.instructure.com/xsd/cccv1p0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://canvas.instructure.com/xsd/cccv1p0 https://canvas.instructure.com/xsd/cccv1p0.xsd">
  <title>{xesc(title)}</title>
  <description>{xesc(to_html(data.get("description", "")))}</description>
  <shuffle_answers>{shuffle}</shuffle_answers>
  <scoring_policy>keep_highest</scoring_policy>
  <hide_results></hide_results>
  <quiz_type>assignment</quiz_type>
  <points_possible>{total_points:.1f}</points_possible>
  <show_correct_answers>true</show_correct_answers>
  <anonymous_submissions>false</anonymous_submissions>
  <could_be_locked>false</could_be_locked>
  <allowed_attempts>1</allowed_attempts>
  <one_question_at_a_time>false</one_question_at_a_time>
  <cant_go_back>false</cant_go_back>
  <available>false</available>
  <one_time_results>false</one_time_results>
  <show_correct_answers_last_attempt>false</show_correct_answers_last_attempt>
  <only_visible_to_overrides>false</only_visible_to_overrides>
  <module_locked>false</module_locked>
</quiz>
'''
    dep = uid(quiz_id, "meta")
    manifest = f'''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{uid(quiz_id, 'manifest')}" xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1" xmlns:imsmd="http://www.imsglobal.org/xsd/imsmd_v1p2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1 http://www.imsglobal.org/xsd/imscp_v1p1.xsd http://www.imsglobal.org/xsd/imsmd_v1p2 http://www.imsglobal.org/xsd/imsmd_v1p2p2.xsd">
  <metadata>
    <schema>IMS Content</schema>
    <schemaversion>1.1.3</schemaversion>
    <imsmd:lom><imsmd:general><imsmd:title><imsmd:string>{xesc(title)}</imsmd:string></imsmd:title></imsmd:general>
      <imsmd:lifeCycle><imsmd:contribute><imsmd:date><imsmd:dateTime>{datetime.date.today()}</imsmd:dateTime></imsmd:date></imsmd:contribute></imsmd:lifeCycle></imsmd:lom>
  </metadata>
  <organizations/>
  <resources>
    <resource identifier="{quiz_id}" type="imsqti_xmlv1p2">
      <file href="{quiz_id}/{quiz_id}.xml"/>
      <dependency identifierref="{dep}"/>
    </resource>
    <resource identifier="{dep}" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="{quiz_id}/assessment_meta.xml">
      <file href="{quiz_id}/assessment_meta.xml"/>
    </resource>
  </resources>
</manifest>
'''
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("imsmanifest.xml", manifest)
        z.writestr(zipfile.ZipInfo("non_cc_assessments/"), b"")
        z.writestr(f"{quiz_id}/assessment_meta.xml", meta)
        z.writestr(f"{quiz_id}/{quiz_id}.xml", assessment)
    # well-formedness self-check
    import xml.dom.minidom as md
    with zipfile.ZipFile(out_zip) as z:
        for name in z.namelist():
            if name.endswith(".xml"):
                md.parseString(z.read(name))
    key_csv = out_zip.with_name(out_zip.stem + "_answer_key.csv")
    with open(key_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        width = max(4, max(len(q["options"]) for q in qs))
        w.writerow(["id", "group", "stem", "key", "outcome", "bloom", "difficulty", "source"] +
                   [f"option_{L}" for L in LETTERS[:width]] + [f"rationale_{L}" for L in LETTERS[:width]])
        for n, q in enumerate(qs, 1):
            o = q["options"]
            k = LETTERS[next(i for i, x in enumerate(o) if x.get("correct") is True)]
            pad = lambda vals: (vals + [""] * width)[:width]
            w.writerow([q.get("id") or f"Q{n}", q.get("group", ""), q["stem"], k, q.get("outcome", ""),
                        q.get("bloom", ""), q.get("difficulty", ""), q.get("source", "")] +
                       pad([x["text"] for x in o]) + pad([x["rationale"] for x in o]))
    return key_csv


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file")
    ap.add_argument("-o", "--output", help="output .zip (default: <quiz_title>_qti.zip)")
    ap.add_argument("--no-feedback", action="store_true", help="omit per-answer rationales from the QTI")
    a = ap.parse_args()
    try:
        data = json.loads(Path(a.json_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read {a.json_file}: {e}")
        sys.exit(1)
    errors, warnings = validate(data)
    for w_ in warnings:
        print("WARNING:", w_)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print(f"\nExport stopped: {len(errors)} error(s). Fix questions.json and run again.")
        sys.exit(1)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", data["quiz_title"]).strip("_")[:60] or "quiz"
    out = Path(a.output or f"{slug}_qti.zip")
    key = build(data, out, feedback=not a.no_feedback)
    n_groups = len({str(q["group"]) for q in data["questions"] if q.get("group") is not None})
    extra = f", {n_groups} question group(s)" if n_groups else ""
    print(f"OK: wrote {out} ({len(data['questions'])} questions{extra}, {len(warnings)} warning(s))")
    print(f"OK: wrote {key} (instructor answer key)")


if __name__ == "__main__":
    main()
