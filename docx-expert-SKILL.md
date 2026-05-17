---
name: docx-expert
description: Create, read, and edit Word documents (.docx). Generate new docs from scratch (reports, proposals, invoices, resumes, letters) or modify existing styled documents — insert paragraphs/tables/images at specific positions, append rows preserving formatting, apply tracked changes and comments. Uses python-docx, docxtpl, and an XML unpack/repack flow for advanced edits.
---

# DOCX Expert

You are a specialist in creating, reading, and editing professional Word documents. `python-docx`, `docxtpl`, and helper scripts under `scripts/` are pre-installed. You choose the right tool for the task — generate from scratch, surgically edit an existing styled document, or unpack/edit-XML/repack — and write Python scripts that produce publication-ready `.docx` files.

## Quick Reference — Choose the Approach

| Task | Recommended approach |
|---|---|
| Read / analyze an existing doc | `python-docx Document(path)` + iterate `doc.paragraphs`, `doc.tables`, `doc.element.body` |
| Create a new doc from scratch | `python-docx` programmatic build |
| Fill a Word template with data | `docxtpl` (Jinja2 in Word) — preserves all original styling perfectly |
| Edit an existing styled doc | XML unpack → edit → repack via `scripts/office/{unpack,pack}.py` — see [XML-Level Document Manipulation](#xml-level-document-manipulation) |
| Tracked changes / comments | Same unpack/repack flow with `<w:ins>` / `<w:del>` / `scripts/comment.py` — see [Tracked Changes & Comments](#tracked-changes--comments) |
| Validate against OOXML schema | `scripts/office/validate.py` |
| Accept all tracked changes | `scripts/accept_changes.py` |

**Routing rule:** if the user uploaded an existing `.docx` and asks you to modify it, default to the Edit-existing flow (unpack → edit XML → repack), not Create-from-scratch.

## Core Approach — Choose the Right Tool

### `docxtpl` — for data-driven documents (PREFERRED when filling a template)

Design the layout in an existing Word template, fill it with data via Jinja2. Preserves all Word styles, tables, headers, footers perfectly. Install: pre-installed.

```python
from docxtpl import DocxTemplate

tpl = DocxTemplate('/path/to/template.docx')
context = {
    'company': 'Acme Corp',
    'date': 'March 3, 2026',
    'items': [
        {'desc': 'Widget A', 'qty': 3, 'price': 9.99, 'total': 29.97},
        {'desc': 'Widget B', 'qty': 1, 'price': 49.99, 'total': 49.99},
    ],
    'total': 79.96,
}
tpl.render(context)
tpl.save('/home/ubuntu/output.docx')
```

Template syntax in Word: `{{ variable }}` | `{% for item in items %}...{% endfor %}` | `{% if cond %}...{% endif %}`

**Use docxtpl for:** invoices, contracts, letters, reports with fixed structure, mail merge.

### `python-docx` — for programmatic structure (when no template exists)

When the document structure itself is dynamic or you're building from scratch.

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

doc = Document()
# ... build document ...
doc.save('/home/ubuntu/output.docx')
```

**Use python-docx for:** resumes, dynamically-structured reports, documents with unknown section count.

**Verify, don't just save.** After every save, re-open the output with `Document(output_path)` and assert the change you intended actually landed. Saving without error is necessary but NOT sufficient. See [Verify the Output](#verify-the-output).

## Document Structure Fundamentals

### Page Setup
```python
from docx.enum.section import WD_ORIENT

section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.top_margin = Inches(1)
section.bottom_margin = Inches(1)
section.left_margin = Inches(1)
section.right_margin = Inches(1)

# Landscape
section.orientation = WD_ORIENT.LANDSCAPE
section.page_width, section.page_height = section.page_height, section.page_width
```

### Styles — The Right Way

ALWAYS define custom styles rather than formatting each paragraph manually. See `references/styles-and-formatting.md` for the complete style system.

```python
from docx.enum.style import WD_STYLE_TYPE

style = doc.styles.add_style('CustomHeading', WD_STYLE_TYPE.PARAGRAPH)
style.font.name = 'Calibri'
style.font.size = Pt(18)
style.font.bold = True
style.font.color.rgb = RGBColor(0x1a, 0x36, 0x5d)
style.paragraph_format.space_before = Pt(24)
style.paragraph_format.space_after = Pt(12)
```

### Paragraphs
```python
p = doc.add_paragraph('Normal text', style='Normal')
p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

# Mixed formatting within a paragraph via runs
p = doc.add_paragraph()
run = p.add_run('Bold text')
run.bold = True
run = p.add_run(' and ')
run = p.add_run('italic text')
run.italic = True
```

### Headings
```python
doc.add_heading('Title', level=0)       # Title style
doc.add_heading('Chapter', level=1)     # Heading 1
doc.add_heading('Section', level=2)     # Heading 2
doc.add_heading('Subsection', level=3)  # Heading 3
```

### Images
See `references/images-guide.md` for advanced image patterns (cell-embedded images, sizing in EMU/Cm, matplotlib chart embedding).

```python
doc.add_picture('/path/to/image.png', width=Inches(5))
# Centered image:
last_paragraph = doc.paragraphs[-1]
last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
```

### Tables
See `references/tables-guide.md` for comprehensive table patterns.

```python
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL, WD_ROW_HEIGHT_RULE

table = doc.add_table(rows=3, cols=4, style='Table Grid')
table.alignment = WD_TABLE_ALIGNMENT.CENTER

# Set header row
hdr = table.rows[0].cells
hdr[0].text = 'Name'
hdr[1].text = 'Value'
# Bold header
for cell in hdr:
    for p in cell.paragraphs:
        for run in p.runs:
            run.bold = True
```

### Hyperlinks

External links (require an `<w:hyperlink>` element with a relationship):

```python
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def add_hyperlink(paragraph, url, text):
    part = paragraph.part
    r_id = part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    new_run = OxmlElement('w:r')
    rpr = OxmlElement('w:rPr')
    rstyle = OxmlElement('w:rStyle')
    rstyle.set(qn('w:val'), 'Hyperlink')
    rpr.append(rstyle)
    new_run.append(rpr)
    t = OxmlElement('w:t')
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)

p = doc.add_paragraph('See ')
add_hyperlink(p, 'https://example.com', 'our docs')
p.add_run(' for more.')
```

Internal links use bookmarks — set `<w:bookmarkStart>` / `<w:bookmarkEnd>` around the target and reference with `<w:hyperlink w:anchor="bookmark_name">`.

### Footnotes

python-docx has no public footnote API; manipulate `word/footnotes.xml` directly via the unpack/repack workflow, or use the OxmlElement approach to inject a `<w:footnoteReference w:id="N"/>` and add a matching `<w:footnote w:id="N">` block.

### Tab Stops

```python
from docx.shared import Inches
from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER

p = doc.add_paragraph()
tab_stops = p.paragraph_format.tab_stops
tab_stops.add_tab_stop(Inches(6), alignment=WD_TAB_ALIGNMENT.RIGHT, leader=WD_TAB_LEADER.DOTS)
p.add_run('Introduction')
p.add_run('\tPage 3')   # right-aligned at 6", dot leader connects the two runs
```

### Multi-Column Layouts

```python
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

section = doc.sections[0]
sectPr = section._sectPr
cols = sectPr.find(qn('w:cols'))
if cols is None:
    cols = OxmlElement('w:cols')
    sectPr.append(cols)
cols.set(qn('w:num'), '2')
cols.set(qn('w:space'), '720')   # 0.5 inch gap (DXA)
cols.set(qn('w:sep'), '1')        # vertical separator line
```

For per-section column counts, add a section break (`doc.add_section()`) and configure each section's `<w:cols>` independently.

### Page Breaks
```python
doc.add_page_break()
```

### Headers and Footers
```python
section = doc.sections[0]
header = section.header
header_para = header.paragraphs[0]
header_para.text = 'Company Name'
header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

footer = section.footer
footer_para = footer.paragraphs[0]
footer_para.text = 'Confidential'
footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
```

### Page Numbers (XML manipulation required)
```python
from docx.oxml.ns import qn

footer_para = section.footer.paragraphs[0]
footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer_para.add_run()
fldChar1 = run._r.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'begin'})
run._r.append(fldChar1)
run2 = footer_para.add_run()
instrText = run2._r.makeelement(qn('w:instrText'), {})
instrText.text = ' PAGE '
run2._r.append(instrText)
run3 = footer_para.add_run()
fldChar2 = run3._r.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'end'})
run3._r.append(fldChar2)
```

### Table of Contents (Placeholder — Word must update)
```python
from docx.oxml.ns import qn

paragraph = doc.add_paragraph()
run = paragraph.add_run()
fldChar = run._r.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'begin'})
run._r.append(fldChar)
run2 = paragraph.add_run()
instrText = run2._r.makeelement(qn('w:instrText'), {})
instrText.text = ' TOC \\o "1-3" \\h \\z \\u '
run2._r.append(instrText)
run3 = paragraph.add_run()
fldChar2 = run3._r.makeelement(qn('w:fldChar'), {qn('w:fldCharType'): 'end'})
run3._r.append(fldChar2)
# Note: user must right-click TOC in Word and "Update Field" to populate
```

## Use Case Workflows

For advanced patterns not covered below — multi-section documents, embedded charts, mail-merge templates, complex headers/footers — see `references/advanced-features.md`.

### Business Report
1. Read `references/styles-and-formatting.md` for the professional style set
2. Structure: Cover page → TOC → Executive Summary → Sections → Appendix
3. Use consistent heading hierarchy (H1 for chapters, H2 for sections, H3 for subsections)
4. Add page numbers in footer, company name in header
5. Include charts as saved images (generate with matplotlib, save as PNG, embed)
6. Use tables for data presentation

### Proposal / Quotation
1. Cover page with company logo, client name, date
2. Executive summary (1 paragraph)
3. Scope of work (bulleted list)
4. Timeline table (phase, duration, deliverables)
5. Pricing table (item, quantity, unit price, total) with totals row
6. Terms and conditions
7. Signature block

### Invoice
1. Company logo + details top-left, "INVOICE" top-right
2. Bill To / Ship To blocks
3. Invoice number, date, due date
4. Line items table with columns: Description, Qty, Rate, Amount
5. Subtotal, tax, total in right-aligned format
6. Payment terms footer

### Contract / Agreement
1. Title page with party names and effective date
2. WHEREAS clauses (recitals)
3. Numbered sections with subsections
4. Definitions section
5. Signature blocks with date lines
6. Exhibits/schedules as appendices

### Resume / CV
1. Name as large heading, contact info below
2. Professional summary (2-3 lines)
3. Experience: reverse chronological, company + role + dates + bullets
4. Education, skills, certifications
5. Tight spacing, clean fonts (Calibri or Garamond)
6. See `templates/resume-template.md` for the exact structure

### Letter (Business Correspondence)
1. Company letterhead (logo + address in header)
2. Date, recipient address block
3. Subject line (bold)
4. Salutation
5. Body paragraphs (justified)
6. Closing, signature space, name + title

### Academic Paper
1. Title, author, abstract, keywords
2. Sections: Introduction, Methods, Results, Discussion, Conclusion
3. References/bibliography
4. Figures and tables with captions (numbered: "Figure 1: ...")
5. Double-spaced, Times New Roman 12pt, 1-inch margins

### Mail Merge (Batch Documents)
Generate multiple documents from data (CSV/JSON):
```python
import csv
from docx import Document

with open('contacts.csv') as f:
    for row in csv.DictReader(f):
        doc = Document()
        doc.add_paragraph(f"Dear {row['name']},")
        doc.add_paragraph(f"Your account balance is ${row['balance']}.")
        doc.save(f"/home/ubuntu/letters/letter_{row['id']}.docx")
```

## Professional Font Recommendations

| Use Case | Heading Font | Body Font |
|---|---|---|
| Corporate / Business | Calibri Bold | Calibri |
| Traditional / Legal | Georgia Bold | Georgia |
| Academic | Times New Roman Bold | Times New Roman |
| Modern / Clean | Arial Bold | Arial |
| Creative | Helvetica Bold | Helvetica |

Note: The computer has standard system fonts. Stick to these — custom fonts may not render on the recipient's system.

## XML-Level Document Manipulation

A `.docx` file is a ZIP archive containing XML files. For advanced editing scenarios that go beyond what `python-docx` supports, you can work directly with the XML.

### Unpack / Edit / Repack Workflow

**Step 1 — Unpack** the DOCX into its constituent XML files:
```bash
python scripts/office/unpack.py document.docx unpacked/
```
This extracts all XML, pretty-prints it for readability, merges adjacent runs, and converts smart quotes to XML entities (`&#x201C;` etc.) so they survive editing. Use `--merge-runs false` to skip run merging.

**Step 2 — Edit** the XML files in `unpacked/word/`. Use direct string replacement on the XML elements — do not write Python scripts for simple edits.

**CRITICAL: Use smart quotes for new content.** When adding text with apostrophes or quotes, use XML entities for professional typography:
```xml
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```

| Entity | Character |
|--------|-----------|
| `&#x2018;` | ' (left single quote) |
| `&#x2019;` | ' (right single / apostrophe) |
| `&#x201C;` | " (left double quote) |
| `&#x201D;` | " (right double quote) |

**Step 3 — Repack** the XML back into a valid DOCX:
```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```
This validates with auto-repair, condenses XML, and creates the DOCX. Use `--validate false` to skip validation.

**Auto-repair capabilities:**
- Fixes `durableId` >= 0x7FFFFFFF (regenerates valid ID)
- Adds missing `xml:space="preserve"` on `<w:t>` elements with whitespace
- Will NOT fix malformed XML, invalid element nesting, missing relationships, or schema violations

## Tracked Changes & Comments

When working with tracked changes at the XML level, use these patterns for professional document review workflows.

### Insertions
```xml
<w:ins w:id="1" w:author="Abacus AI Agent" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>
```

### Deletions
```xml
<w:del w:id="2" w:author="Abacus AI Agent" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
```

**Inside `<w:del>` elements:** Use `<w:delText>` instead of `<w:t>`, and `<w:delInstrText>` instead of `<w:instrText>`.

### Minimal Edits — Only Mark What Changes
```xml
<!-- Change "30 days" to "60 days" -->
<w:r><w:t>The term is </w:t></w:r>
<w:del w:id="1" w:author="Abacus AI Agent" w:date="...">
  <w:r><w:delText>30</w:delText></w:r>
</w:del>
<w:ins w:id="2" w:author="Abacus AI Agent" w:date="...">
  <w:r><w:t>60</w:t></w:r>
</w:ins>
<w:r><w:t> days.</w:t></w:r>
```

### Deleting Entire Paragraphs

When removing ALL content from a paragraph, also mark the paragraph mark as deleted so it merges with the next paragraph. Add `<w:del/>` inside `<w:pPr><w:rPr>`:
```xml
<w:p>
  <w:pPr>
    <w:rPr>
      <w:del w:id="1" w:author="Abacus AI Agent" w:date="2025-01-01T00:00:00Z"/>
    </w:rPr>
  </w:pPr>
  <w:del w:id="2" w:author="Abacus AI Agent" w:date="2025-01-01T00:00:00Z">
    <w:r><w:delText>Entire paragraph content being deleted...</w:delText></w:r>
  </w:del>
</w:p>
```

### Adding Comments

Use `comment.py` to handle the boilerplate across multiple XML files:
```bash
python scripts/comment.py unpacked/ 0 "Comment text with &amp; and &#x2019;"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0  # reply to comment 0
python scripts/comment.py unpacked/ 0 "Text" --author "Custom Author"
```

Then add markers to `document.xml`. **CRITICAL:** `<w:commentRangeStart>` and `<w:commentRangeEnd>` are siblings of `<w:r>`, never inside `<w:r>`:
```xml
<w:commentRangeStart w:id="0"/>
<w:r><w:t>commented text</w:t></w:r>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>
```

### Common Pitfalls
- **Replace entire `<w:r>` elements**: When adding tracked changes, replace the whole `<w:r>...</w:r>` block — don't inject tracked change tags inside a run
- **Preserve `<w:rPr>` formatting**: Copy the original run's `<w:rPr>` block into your tracked change runs to maintain bold, font size, etc.

## Document Validation & Schema Compliance

### Validation Tool

After creating or editing a DOCX, validate it against the ISO/IEC 29500 (OOXML) schema:
```bash
python scripts/office/validate.py document.docx
```

For round-trip / edit-existing tasks, pass `--original` so validation only flags real differences:
```bash
python scripts/office/validate.py edited.docx --original original.docx
```

**Known false positive:** running `validate.py` *without* `--original` on a freshly-generated python-docx document reports `<w:zoom>` missing the `percent` attribute. python-docx omits this attribute by default; Word fills it in on first save. Ignore this specific error on freshly-generated docs, or pass `--original` to suppress it.

### Schema Compliance Rules

- **Element order in `<w:pPr>`**: Must follow this sequence: `<w:pStyle>`, `<w:numPr>`, `<w:spacing>`, `<w:ind>`, `<w:jc>`, `<w:rPr>` (last)
- **Whitespace preservation**: Add `xml:space="preserve"` to any `<w:t>` element with leading or trailing spaces
- **RSIDs**: Must be 8-digit hexadecimal values (e.g., `00AB1234`)
- **Content Types**: Every embedded media type must have a corresponding entry in `[Content_Types].xml`
- **Relationships**: Every cross-reference (images, hyperlinks, comments) must have a valid relationship entry in the appropriate `.rels` file

### Accepting Tracked Changes

To produce a clean document with all tracked changes accepted:
```bash
python scripts/accept_changes.py input.docx output.docx
```

> *The XML-level manipulation workflow, tracked changes patterns, and validation guidance in this section are informed by techniques from [Anthropic's docx skill](https://github.com/anthropics/skills/tree/main/skills/docx).*

## Quality Checklist

Before delivering:
- [ ] All headings use consistent styles (not manual formatting)
- [ ] Tables have consistent column widths and alignment
- [ ] Images are properly sized (not overflowing margins)
- [ ] Page numbers are present (if multi-page)
- [ ] Headers/footers are set correctly
- [ ] Margins are consistent
- [ ] No orphaned headings (heading at bottom of page, content on next)
- [ ] XML validates against OOXML schema (if using XML-level editing)
- [ ] All tracked changes have proper author and date attributes
- [ ] Smart quotes use XML entities (not raw Unicode characters)
- [ ] Layout verified — image alignment, table styling, page-break placement asserted via python-docx introspection or XML inspection (see [Verify the Output](#verify-the-output))

### Verify the Output

A clean save is necessary but NOT sufficient. Before delivering, re-open the saved file and assert the change actually landed:

```python
from docx import Document
out = Document(output_path)
```

What to assert:

- **Generation tasks:** key sections, headings, and tables exist with the expected content; page count is reasonable; no empty placeholder text remains.
- **Edit-in-place tasks:** the inserted/modified element is at the intended position relative to its anchors; existing styling on neighbouring elements is unchanged; tables that were extended have all rows styled (not just the original ones).
- **Layout assertions** — text-level assertions don't catch image alignment, table styling, page-break placement, or section properties. To verify these, use either:
  - **python-docx introspection** — programmatic checks against the saved file:
    ```python
    from docx import Document
    from docx.oxml.ns import qn

    out = Document(output_path)
    for i, p in enumerate(out.paragraphs):
        if p.alignment is not None:
            print(f'P{i} alignment={p.alignment}')
    for i, t in enumerate(out.tables):
        print(f'T{i} alignment={t.alignment}, autofit={t.autofit}')
    # Page breaks live in run children:
    for p in out.paragraphs:
        for run in p.runs:
            for br in run._r.iter(qn('w:br')):
                if br.get(qn('w:type')) == 'page':
                    print(f'page break at: {p.text[:60]}')
    ```
  - **XML inspection** — for exact element-level questions (where does a `<w:drawing>` sit, what does a table's `<w:tblPr>` say, where are explicit page breaks):
    ```bash
    python scripts/office/unpack.py output.docx unpacked/
    grep -n '<w:br w:type="page"/>\|<w:drawing>\|<w:tblPr>' unpacked/word/document.xml
    ```

  Pick the one that matches the question: python-docx for "is this aligned correctly" assertions, XML inspection for "where exactly is this element" debugging.
