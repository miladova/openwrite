#!/usr/bin/env python3
"""Build formatted PDFs for the RANA manuscript.

Usage (from repo root):
    python3 novel/build_pdf.py                 # builds every chapter + manuscript.pdf

Requires: fpdf2  (pip install fpdf2)
Outputs:  novel/pdf/<chapter-slug>.pdf         (one PDF per chapter)
          novel/pdf/RANA-manuscript.pdf        (cover + TOC + all chapters)
"""

import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent
CHAPTERS_DIR = ROOT / "chapters"
PDF_DIR = ROOT / "pdf"

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

PAPER = (253, 251, 246)      # warm off-white
INK = (28, 28, 28)           # near-black
ACCENT = (110, 20, 35)       # dried-blood oxblood
GOLD = (176, 141, 62)        # brass
MUTE = (96, 92, 88)          # warm grey

W, H = 152, 228              # mm — trade-size trim
M_SIDE, M_TOP, M_BOT = 19, 18, 17


def smart_quotes(text: str) -> str:
    text = re.sub(r'"([^"\n]+)"', r"“\1”", text)
    text = re.sub(r"(?<=\w)'(?=\w)", "’", text)
    text = re.sub(r"(?<=\s|\()'(?=\w)", "‘", text)
    text = re.sub(r"(?<=\w|[.,!?)])'(?=\s|$|[.,!?)])", "’", text)
    return text


TOKEN_RE = re.compile(r"(\*\*.+?\*\*|\*.+?\*)")


def inline_runs(text: str):
    """Yield (chunk, bold) tuples from markdown-ish inline markup."""
    for tok in TOKEN_RE.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            yield tok[2:-2], True
        elif tok.startswith("*") and tok.endswith("*"):
            yield tok[1:-1], False  # rendered as regular (no italic face available)
        else:
            yield tok, False


def parse_chapter(md_path: Path):
    """Split a chapter markdown file into structured blocks."""
    blocks = []
    buf: list[str] = []

    def flush_para():
        if buf:
            blocks.append(("p", smart_quotes(" ".join(buf).strip())))
            buf.clear()

    for raw in md_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            continue
        if line.startswith("### "):
            flush_para()
            blocks.append(("dateline", smart_quotes(line[4:].strip())))
        elif line.startswith("## "):
            flush_para()
            blocks.append(("chapter", smart_quotes(line[3:].strip())))
        elif line.startswith("# "):
            flush_para()
            blocks.append(("book", smart_quotes(line[2:].strip())))
        elif line.strip() == "---":
            flush_para()
            blocks.append(("rule", ""))
        else:
            buf.append(line.strip())
    flush_para()
    return blocks


class RanaPDF(FPDF):
    def __init__(self, header_left="R A N A", header_right="", paper=True):
        super().__init__(format=(W, H), unit="mm")
        self.add_font("serif", "", FONT_REG)
        self.add_font("serif", "B", FONT_BOLD)
        self.set_margins(M_SIDE, M_TOP, M_SIDE)
        self.set_auto_page_break(auto=True, margin=M_BOT)
        self.header_left = header_left
        self.header_right = header_right
        self.paper = paper
        self.suppress_decor = False   # True on title/cover pages

    # ---------- page furniture ----------
    def header(self):
        if self.suppress_decor:
            return
        if self.paper:
            self.set_fill_color(*PAPER)
            self.rect(0, 0, W, H, "F")
        self.set_text_color(*MUTE)
        self.set_font("serif", "B", 6.4)
        self.set_char_spacing(0.6)
        self.set_y(8)
        y = self.get_y()
        self.set_x(M_SIDE)
        self.cell(0, 4, self.header_left, align="L")
        if self.header_right:
            self.set_y(y)
            self.set_x(M_SIDE)
            self.cell(W - 2 * M_SIDE, 4, self.header_right.upper(), align="R")
        self.set_char_spacing(0)
        self.set_draw_color(*GOLD)
        self.set_line_width(0.25)
        self.line(M_SIDE, 13.4, W - M_SIDE, 13.4)

    def footer(self):
        if self.suppress_decor:
            return
        self.set_y(-11.5)
        self.set_draw_color(*GOLD)
        self.set_line_width(0.25)
        self.line(M_SIDE, self.get_y(), W - M_SIDE, self.get_y())
        self.ln(1.6)
        self.set_text_color(*ACCENT)
        self.set_font("serif", "B", 7.2)
        self.cell(0, 4, str(self.page_no()), align="C")

    # ---------- building blocks ----------
    def paper_page(self):
        self.add_page()
        if self.paper:
            self.set_fill_color(*PAPER)
            self.rect(0, 0, W, H, "F")
        self.set_auto_page_break(auto=True, margin=M_BOT)

    def ornament(self):
        self.ln(2.0)
        self.set_text_color(*GOLD)
        self.set_font("serif", "B", 8.5)
        self.cell(0, 5, "◆  ◆  ◆", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)
        self.ln(2.0)

    def chapter_masthead(self, chapter_title: str, dateline: str | None):
        """The opening block of each chapter (used in both chapter PDFs and manuscript)."""
        m = re.match(r"(Chapter\s+\S+)\s*—\s*(.+)", chapter_title)
        part, name = (m.group(1).upper(), m.group(2)) if m else ("", chapter_title)

        self.set_text_color(*GOLD)
        self.set_draw_color(*GOLD)
        self.set_line_width(0.4)
        self.ln(2)
        self.line(W / 2 - 26, self.get_y(), W / 2 + 26, self.get_y())
        self.ln(6)
        if part:
            self.set_text_color(*ACCENT)
            self.set_font("serif", "B", 9.5)
            self.set_char_spacing(1.6)
            self.cell(0, 5, part, align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_char_spacing(0)
            self.ln(2.5)
        self.set_text_color(*INK)
        self.set_font("serif", "B", 21.5)
        self.multi_cell(0, 9.2, name, align="C", new_x="LMARGIN", new_y="NEXT")
        if dateline:
            self.ln(2.5)
            self.set_text_color(*MUTE)
            self.set_font("serif", "", 9)
            self.set_char_spacing(0.8)
            self.cell(0, 5, dateline.upper(), align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_char_spacing(0)
        self.ln(4)
        self.set_draw_color(*GOLD)
        self.line(W / 2 - 26, self.get_y(), W / 2 + 26, self.get_y())
        self.ln(7)
        self.set_text_color(*INK)

    def body_paragraph(self, text: str):
        self.set_font("serif", "", 10.3)
        self.set_text_color(*INK)
        size = self.font_size
        for chunk, bold in inline_runs(text):
            self.set_font("serif", "B" if bold else "", 10.3)
            self.write(5.6, chunk)
        self.ln(5.6)
        self.ln(2.6)

    def render_blocks(self, blocks, masthead=True):
        dateline = None
        pending_chapter = None
        for kind, payload in blocks:
            if kind == "book":
                continue
            if kind == "chapter":
                pending_chapter = payload
                continue
            if kind == "dateline":
                dateline = payload
                continue
            if kind == "rule":
                self.ornament()
                continue
            if kind == "p":
                if pending_chapter is not None:
                    if masthead:
                        self.chapter_masthead(pending_chapter, dateline)
                    pending_chapter, dateline = None, None
                self.body_paragraph(payload)
        if pending_chapter is not None and masthead:
            self.chapter_masthead(pending_chapter, dateline)


def chapter_title_of(md_path: Path) -> str:
    for raw in md_path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## "):
            return raw[3:].strip()
    return md_path.stem


def build_chapter_pdf(md_path: Path, out_path: Path):
    chapter = chapter_title_of(md_path)
    pdf = RanaPDF(header_left="R A N A", header_right=re.sub(r"^Chapter\s*", "", chapter).split("—")[0].strip() and chapter)
    pdf.header_right = re.sub(r".*—\s*", "", chapter)

    # ---- title page ----
    pdf.suppress_decor = True
    pdf.add_page()
    pdf.set_fill_color(*PAPER)
    pdf.rect(0, 0, W, H, "F")

    pdf.set_y(30)
    pdf.set_text_color(*MUTE)
    pdf.set_font("serif", "", 7.5)
    pdf.set_char_spacing(2.2)
    pdf.cell(0, 5, "A  N O V E L   O F   W A R S A W", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)

    pdf.ln(16)
    pdf.set_text_color(*INK)
    pdf.set_font("serif", "B", 64)
    pdf.set_char_spacing(6)
    pdf.cell(0, 26, "RANA", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)

    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.5)
    pdf.line(W / 2 - 30, pdf.get_y() + 2, W / 2 + 30, pdf.get_y() + 2)
    pdf.ln(14)
    pdf.set_text_color(*ACCENT)
    pdf.set_font("serif", "B", 8.5)
    pdf.set_char_spacing(1.8)
    pdf.cell(0, 5, "K R W A W N I K  ·  T H E  W O U N D - H E R B", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)

    pdf.set_y(118)
    m = re.match(r"(Chapter\s+\S+)\s*—\s*(.+)", chapter)
    part, name = (m.group(1).upper(), m.group(2)) if m else ("", chapter)
    pdf.set_text_color(*GOLD)
    pdf.set_font("serif", "B", 10)
    pdf.set_char_spacing(2.0)
    pdf.cell(0, 6, part, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.ln(3)
    pdf.set_text_color(*INK)
    pdf.set_font("serif", "B", 19)
    pdf.multi_cell(0, 8, name, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(206)
    pdf.set_text_color(*MUTE)
    pdf.set_font("serif", "", 6.8)
    pdf.set_char_spacing(1.1)
    pdf.cell(0, 4, "I N   T H E   M A N N E R   O F   J A M E S   C L A V E L L", align="C")
    pdf.set_char_spacing(0)

    # ---- body ----
    pdf.paper_page()  # add_page() finalises the cover while decor is suppressed
    pdf.suppress_decor = False
    blocks = parse_chapter(md_path)
    # skip the book-level H1 (already on the cover), keep chapter/dateline/body
    pdf.render_blocks([b for b in blocks if b[0] != "book"])
    pdf.output(str(out_path))


def build_manuscript_pdf(md_paths: list[Path], out_path: Path):
    pdf = RanaPDF(header_left="R A N A", header_right="A NOVEL OF WARSAW")

    # ---- cover ----
    pdf.suppress_decor = True
    pdf.add_page()
    pdf.set_fill_color(*PAPER)
    pdf.rect(0, 0, W, H, "F")

    pdf.set_y(34)
    pdf.set_text_color(*MUTE)
    pdf.set_font("serif", "", 7.5)
    pdf.set_char_spacing(2.2)
    pdf.cell(0, 5, "A  N O V E L   O F   W A R S A W", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)

    pdf.ln(18)
    pdf.set_text_color(*INK)
    pdf.set_font("serif", "B", 74)
    pdf.set_char_spacing(7)
    pdf.cell(0, 30, "RANA", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.5)
    pdf.line(W / 2 - 32, pdf.get_y() + 3, W / 2 + 32, pdf.get_y() + 3)
    pdf.ln(16)
    pdf.set_text_color(*ACCENT)
    pdf.set_font("serif", "B", 8.5)
    pdf.set_char_spacing(1.8)
    pdf.cell(0, 5, "K R W A W N I K  ·  T H E  W O U N D - H E R B", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)

    pdf.set_y(150)
    pdf.set_text_color(*MUTE)
    pdf.set_font("serif", "", 9)
    pdf.multi_cell(0, 5.5, "Warsaw, November 1943. A female surgeon\nholds the life of the man she was born\nto hate — and her oath may kill her.", align="C")

    pdf.set_y(208)
    pdf.set_text_color(*MUTE)
    pdf.set_font("serif", "", 6.8)
    pdf.set_char_spacing(1.1)
    pdf.cell(0, 4, "I N   T H E   M A N N E R   O F   J A M E S   C L A V E L L", align="C")
    pdf.set_char_spacing(0)

    # ---- contents ----
    pdf.paper_page()  # add_page() finalises the cover while decor is suppressed
    pdf.suppress_decor = False
    pdf.set_text_color(*GOLD)
    pdf.set_font("serif", "B", 9.5)
    pdf.set_char_spacing(2.0)
    pdf.ln(4)
    pdf.cell(0, 6, "C O N T E N T S", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.ln(2)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.3)
    pdf.line(W / 2 - 20, pdf.get_y(), W / 2 + 20, pdf.get_y())
    pdf.ln(6)
    for md in md_paths:
        chapter = chapter_title_of(md)
        m = re.match(r"(Chapter\s+\S+)\s*—\s*(.+)", chapter)
        part, name = (m.group(1).upper(), m.group(2)) if m else ("", chapter)
        pdf.set_text_color(*ACCENT)
        pdf.set_font("serif", "B", 8)
        pdf.set_char_spacing(1.2)
        pdf.cell(0, 5, part, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_char_spacing(0)
        pdf.set_text_color(*INK)
        pdf.set_font("serif", "", 10.5)
        pdf.multi_cell(0, 5.6, name, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4.5)

    # ---- chapters ----
    for md in md_paths:
        pdf.paper_page()
        blocks = parse_chapter(md)
        pdf.render_blocks(blocks)

    pdf.output(str(out_path))


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    md_paths = [Path(a) for a in args] if args else sorted(CHAPTERS_DIR.glob("*.md"))
    for md in md_paths:
        out = PDF_DIR / (md.stem + ".pdf")
        build_chapter_pdf(md, out)
        print(f"built {out}")
    manuscript = PDF_DIR / "RANA-manuscript.pdf"
    build_manuscript_pdf(md_paths, manuscript)
    print(f"built {manuscript}")


if __name__ == "__main__":
    main()
