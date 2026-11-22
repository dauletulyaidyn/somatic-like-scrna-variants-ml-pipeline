"""Small helpers to rebuild a journal .docx in place with python-docx + lxml.

Inline markup in text:
  ⟦ ... ⟧   yellow highlight (changed / new text)
  ⟪ ... ⟫   italic
  【 ... 】   bold
  ^{...}    superscript,  _{...} subscript
"""
from __future__ import annotations

import re
from copy import deepcopy

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn, nsdecls
from docx.shared import Emu
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
TOK = re.compile(r"(⟦|⟧|⟪|⟫|【|】|\^\{[^}]*\}|_\{[^}]*\})")


def parse_markup(text: str, hl_default=False):
    """Yield (text, flags) with flags dict: h,i,b,sup,sub."""
    h, i, b = hl_default, False, False
    for part in TOK.split(text):
        if not part:
            continue
        if part == "⟦": h = True; continue
        if part == "⟧": h = hl_default and False; continue
        if part == "⟪": i = True; continue
        if part == "⟫": i = False; continue
        if part == "【": b = True; continue
        if part == "】": b = False; continue
        if part.startswith("^{"):
            yield part[2:-1], dict(h=h, i=i, b=b, sup=True); continue
        if part.startswith("_{"):
            yield part[2:-1], dict(h=h, i=i, b=b, sub=True); continue
        yield part, dict(h=h, i=i, b=b)


def strip_rpr(rpr):
    for tag in ("w:highlight", "w:b", "w:bCs", "w:i", "w:iCs", "w:vertAlign", "w:color", "w:u", "w:shd"):
        for el in rpr.findall(qn(tag)):
            rpr.remove(el)
    return rpr


def set_rpr(rpr, flags):
    # order matters loosely for schema; Word tolerates, validator prefers rFonts,b,bCs,i,iCs,...,sz,szCs,highlight,vertAlign
    def ins(tag, val=None):
        el = etree.SubElement(rpr, qn(tag))
        if val is not None:
            el.set(qn("w:val"), val)
        return el
    children = list(rpr)
    for c in children:
        rpr.remove(c)
    fonts = [c for c in children if c.tag == qn("w:rFonts")]
    rest = [c for c in children if c.tag not in (qn("w:rFonts"),)]
    for c in fonts:
        rpr.append(c)
    if flags.get("b"):
        ins("w:b"); ins("w:bCs")
    if flags.get("i"):
        ins("w:i"); ins("w:iCs")
    sizes = [c for c in rest if c.tag in (qn("w:sz"), qn("w:szCs"))]
    others = [c for c in rest if c.tag not in (qn("w:sz"), qn("w:szCs"))]
    for c in others:
        rpr.append(c)
    for c in sizes:
        rpr.append(c)
    if flags.get("h"):
        ins("w:highlight", "yellow")
    if flags.get("sup"):
        ins("w:vertAlign", "superscript")
    if flags.get("sub"):
        ins("w:vertAlign", "subscript")
    return rpr


def make_run(base_rpr, text, flags):
    r = etree.Element(qn("w:r"))
    rpr = strip_rpr(deepcopy(base_rpr)) if base_rpr is not None else etree.Element(qn("w:rPr"))
    r.append(set_rpr(rpr, flags))
    parts = text.split("\t")
    for k, p in enumerate(parts):
        if k:
            etree.SubElement(r, qn("w:tab"))
        if p:
            t = etree.SubElement(r, qn("w:t"))
            t.text = p
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


class Builder:
    def __init__(self, src):
        self.doc = Document(src)
        self.body = self.doc.element.body
        self.sectPr = self.body.find(qn("w:sectPr"))
        self.orig = [el for el in self.body.iterchildren() if el.tag != qn("w:sectPr")]
        self.out = []

    # ----- templates
    def tmpl(self, i):
        el = self.orig[i]
        ppr = el.find(qn("w:pPr"))
        rpr = None
        for r in el.iter(qn("w:r")):
            if r.find(qn("w:rPr")) is not None and (r.find(qn("w:t")) is not None or rpr is None):
                rpr = r.find(qn("w:rPr"))
                if r.find(qn("w:t")) is not None:
                    break
        return ppr, rpr

    def keep(self, i):
        self.out.append(deepcopy(self.orig[i]))

    def P(self, tmpl_i, text, hl=False, size=None, align=None, ppr_over=None):
        """New paragraph using formatting of original element tmpl_i. hl=True highlights everything."""
        ppr, rpr = self.tmpl(tmpl_i)
        p = etree.Element(qn("w:p"))
        if ppr is not None:
            ppr2 = deepcopy(ppr)
            rp = ppr2.find(qn("w:rPr"))
            if rp is not None:
                ppr2.remove(rp)
            if align:
                jc = ppr2.find(qn("w:jc"))
                if jc is None:
                    jc = etree.SubElement(ppr2, qn("w:jc"))
                jc.set(qn("w:val"), align)
            p.append(ppr2)
        base = deepcopy(rpr) if rpr is not None else etree.Element(qn("w:rPr"))
        if size:
            for tag in ("w:sz", "w:szCs"):
                el = base.find(qn(tag))
                if el is None:
                    el = etree.SubElement(base, qn(tag))
                el.set(qn("w:val"), str(size))
        if hl:
            text = "⟦" + text.replace("⟦", "").replace("⟧", "") + "⟧"
        for t, fl in parse_markup(text):
            p.append(make_run(base, t, fl))
        self.out.append(p)
        return p

    def picture(self, tmpl_i, png, width_cm):
        par = self.doc.add_paragraph()
        par.add_run().add_picture(png, width=Emu(int(width_cm * 360000)))
        el = par._p
        self.body.remove(el)
        ppr, _ = self.tmpl(tmpl_i)
        old = el.find(qn("w:pPr"))
        if old is not None:
            el.remove(old)
        if ppr is not None:
            el.insert(0, deepcopy(ppr))
        self.out.append(el)

    def equation(self, tmpl_tbl_i, omml_inner, number, hl=True, size=28):
        """Copy an equation table (3 cells: blank | oMathPara | (n)) and replace content."""
        tbl = deepcopy(self.orig[tmpl_tbl_i])
        rows = tbl.findall(qn("w:tr"))
        for extra in rows[1:]:
            tbl.remove(extra)
        cells = rows[0].findall(qn("w:tc"))
        mid_p = cells[1].find(qn("w:p"))
        for c in list(mid_p):
            if c.tag != qn("w:pPr"):
                mid_p.remove(c)
        xml = f'<m:oMathPara {nsdecls("m", "w")}><m:oMath>{omml_inner}</m:oMath></m:oMathPara>'
        omp = parse_xml(xml)
        if hl:
            for rpr in omp.iter(qn("w:rPr")):
                h = etree.SubElement(rpr, qn("w:highlight")); h.set(qn("w:val"), "yellow")
        for rpr in omp.iter(qn("w:rPr")):
            for tag in ("w:sz", "w:szCs"):
                pass
        mid_p.append(omp)
        num_p = cells[2].find(qn("w:p"))
        rpr_src = None
        for r in num_p.iter(qn("w:r")):
            rpr_src = r.find(qn("w:rPr")); break
        for c in list(num_p):
            if c.tag != qn("w:pPr"):
                num_p.remove(c)
        num_p.append(make_run(rpr_src, f"({number})", dict(h=hl)))
        self.out.append(tbl)
        return tbl

    def data_table(self, rows, widths_cm, font_size=20, header=True, hl=True, align_first_left=True, font="Times New Roman", note=None):
        ncol = len(rows[0])
        tw = int(sum(widths_cm) * 567)
        grid = "".join(f'<w:gridCol w:w="{int(w*567)}"/>' for w in widths_cm)
        border = '<w:tblBorders><w:top w:val="single" w:sz="6" w:space="0" w:color="000000"/><w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/><w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tblBorders>'
        tbl = parse_xml(f'<w:tbl {nsdecls("w")}><w:tblPr><w:tblW w:w="{tw}" w:type="dxa"/><w:jc w:val="center"/>{border}<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="57" w:type="dxa"/><w:right w:w="57" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>{grid}</w:tblGrid></w:tbl>')
        base = parse_xml(f'<w:rPr {nsdecls("w")}><w:rFonts w:ascii="{font}" w:eastAsia="{font}" w:hAnsi="{font}" w:cs="{font}"/><w:sz w:val="{font_size}"/><w:szCs w:val="{font_size}"/></w:rPr>')
        all_rows = list(rows) + ([[note] + [None] * (ncol - 1)] if note else [])
        for ri, row in enumerate(all_rows):
            tr = etree.SubElement(tbl, qn("w:tr"))
            trpr = etree.SubElement(tr, qn("w:trPr")); etree.SubElement(trpr, qn("w:cantSplit"))
            if ri == 0 and header:
                etree.SubElement(trpr, qn("w:tblHeader"))
            is_note = note and ri == len(all_rows) - 1
            ci = 0
            while ci < ncol:
                val = row[ci]
                span = 1
                while ci + span < ncol and row[ci + span] is None:
                    span += 1
                tc = etree.SubElement(tr, qn("w:tc"))
                tcpr = etree.SubElement(tc, qn("w:tcPr"))
                tcw = etree.SubElement(tcpr, qn("w:tcW")); tcw.set(qn("w:w"), str(int(sum(widths_cm[ci:ci + span]) * 567))); tcw.set(qn("w:type"), "dxa")
                if span > 1:
                    gs = etree.SubElement(tcpr, qn("w:gridSpan")); gs.set(qn("w:val"), str(span))
                va = etree.SubElement(tcpr, qn("w:vAlign")); va.set(qn("w:val"), "center")
                p = etree.SubElement(tc, qn("w:p"))
                ppr = etree.SubElement(p, qn("w:pPr"))
                sp = etree.SubElement(ppr, qn("w:spacing")); sp.set(qn("w:before"), "0"); sp.set(qn("w:after"), "0"); sp.set(qn("w:line"), "240"); sp.set(qn("w:lineRule"), "auto")
                jc = etree.SubElement(ppr, qn("w:jc"))
                jc.set(qn("w:val"), "both" if is_note else ("left" if (ci == 0 and align_first_left) else "center"))
                txt = str(val) if val is not None else ""
                if hl:
                    txt = "⟦" + txt + "⟧"
                if ri == 0 and header:
                    txt = "【" + txt + "】"
                for t, fl in parse_markup(txt):
                    p.append(make_run(base, t, fl))
                ci += span
        self.out.append(tbl)
        return tbl

    def edit(self, i, old, new, occurrence=0):
        """In-place replacement inside original paragraph i; `new` uses the inline markup
        (wrap changed parts in ⟦⟧). The base formatting is taken from the run where `old` starts."""
        p = self.orig[i]
        runs = [r_ for r_ in p.iter(qn("w:r")) if r_.getparent() is p or r_.getparent().tag == qn("w:hyperlink")]
        texts = ["".join(t.text or "" for t in r_.findall(qn("w:t"))) for r_ in runs]
        full = "".join(texts)
        if occurrence == -1:
            pos = full.rfind(old)
        else:
            pos = -1
            for _ in range(occurrence + 1):
                pos = full.find(old, pos + 1)
        if pos < 0:
            raise ValueError(f"[{i}] not found: {old[:80]}")
        end = pos + len(old)
        offs, o = [], 0
        for t in texts:
            offs.append(o); o += len(t)
        k0 = max(k for k in range(len(runs)) if offs[k] <= pos and texts[k] and pos < offs[k] + len(texts[k]))
        k1 = max(k for k in range(len(runs)) if offs[k] < end and texts[k])
        def set_text(run, txt):
            for t in run.findall(qn("w:t")):
                run.remove(t)
            if txt:
                t = etree.SubElement(run, qn("w:t")); t.text = txt
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        base = runs[k0].find(qn("w:rPr"))
        pre = texts[k0][: pos - offs[k0]]
        post = texts[k1][end - offs[k1]:]
        if k0 == k1:
            tail = deepcopy(runs[k0])
            for c in list(tail):
                if c.tag not in (qn("w:rPr"), qn("w:t")):
                    tail.remove(c)
            set_text(tail, post)
            runs[k0].addnext(tail)
        else:
            for k in range(k0 + 1, k1):
                runs[k].getparent().remove(runs[k])
            set_text(runs[k1], post)
        set_text(runs[k0], pre)
        anchor = runs[k0]
        for t, fl in parse_markup(new):
            nr = make_run(base, t, fl)
            anchor.addnext(nr); anchor = nr
        return self

    def insert_after_orig(self, i, builder_fn):
        pass

    def save(self, path):
        for el in list(self.body.iterchildren()):
            if el.tag != qn("w:sectPr"):
                self.body.remove(el)
        for el in self.out:
            self.sectPr.addprevious(el)
        self.doc.save(path)


def add_table_row(tbl, cells, before_last=True, hl=True):
    """Append a row to an existing table by copying its last data row (the row before a merged note row
    when before_last=True) and replacing the cell texts; the new cells are highlighted."""
    rows = tbl.findall(qn("w:tr"))
    tmpl = rows[-2] if before_last else rows[-1]
    new = deepcopy(tmpl)
    tcs = new.findall(qn("w:tc"))
    assert len(tcs) == len(cells), (len(tcs), cells)
    for tc, text in zip(tcs, cells):
        runs = list(tc.iter(qn("w:r")))
        for r_ in runs[1:]:
            r_.getparent().remove(r_)
        r0 = runs[0]
        for t in r0.findall(qn("w:t")):
            r0.remove(t)
        t = etree.SubElement(r0, qn("w:t")); t.text = text
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        if hl:
            rpr = r0.find(qn("w:rPr"))
            if rpr is None:
                rpr = etree.Element(qn("w:rPr")); r0.insert(0, rpr)
            flags = dict(h=True, b=rpr.find(qn("w:b")) is not None, i=rpr.find(qn("w:i")) is not None)
            set_rpr(strip_rpr(rpr), flags)
    tmpl.addnext(new)
    return new


def renumber_citations(elements, mapping):
    """Rewrite numeric citations [n] in all text runs of the given elements in one pass (old -> new).
    Raises if a bracketed number is split across runs, so no citation is left unmapped silently."""
    import re
    pat = re.compile(r"\[(\d+)\]")
    for el in elements:
        for p in el.iter(qn("w:p")):
            ts = list(p.iter(qn("w:t")))
            joined = "".join(t.text or "" for t in ts)
            n_before = len(pat.findall(joined))
            n_runs = 0
            for t in ts:
                if t.text:
                    n_runs += len(pat.findall(t.text))
                    t.text = pat.sub(lambda m: f"[{mapping.get(int(m.group(1)), int(m.group(1)))}]", t.text)
            if n_runs != n_before:
                raise ValueError(f"citation split across runs: {joined[:120]}")


# ---------------- OMML helpers ----------------
def _rpr(size=28):
    return f'<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'


SIZE = [28]


def r(t, plain=False):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    sty = '<m:rPr><m:sty m:val="p"/></m:rPr>' if plain else ""
    return f'<m:r>{sty}{_rpr(SIZE[0])}<m:t xml:space="preserve">{t}</m:t></m:r>'


def f(num, den):
    return f"<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>"


def sub(base, s):
    return f"<m:sSub><m:e>{base}</m:e><m:sub>{s}</m:sub></m:sSub>"


def sup(base, s):
    return f"<m:sSup><m:e>{base}</m:e><m:sup>{s}</m:sup></m:sSup>"


def subsup(base, s, p):
    return f"<m:sSubSup><m:e>{base}</m:e><m:sub>{s}</m:sub><m:sup>{p}</m:sup></m:sSubSup>"


def nary(ch, lo, hi, body):
    hide = '<m:supHide m:val="1"/>' if hi == "" else ""
    return f'<m:nary><m:naryPr><m:chr m:val="{ch}"/><m:limLoc m:val="undOvr"/>{hide}</m:naryPr><m:sub>{lo}</m:sub><m:sup>{hi}</m:sup><m:e>{body}</m:e></m:nary>'


def d(body, beg="(", end=")"):
    return f'<m:d><m:dPr><m:begChr m:val="{beg}"/><m:endChr m:val="{end}"/></m:dPr><m:e>{body}</m:e></m:d>'
