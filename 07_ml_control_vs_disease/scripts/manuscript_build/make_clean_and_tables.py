"""Make *_clean.docx (all yellow highlight removed) from every *_highlighted.docx in FINAL_2026-11-21,
then export each article's numbered tables to 3_tables/ (one .docx + one CSV per table)."""
import csv
import re
import shutil
import sys
from pathlib import Path

import docx
from docx.oxml.ns import qn

FIN = Path(r"D:\! ! ! Defense Dissertation - State 13.08.2026\! ! ! Final documents ! ! !\0. ----WAIT---- Articles (KBTU, NANRK, Aqtobe)\Articles\FINAL_2026-11-21")
TABLES = {  # article folder: (clean article, tables docx name, csv prefix)
    "1_NANRK": ("NANRK_rev6_clean.docx", "NANRK_rev6_Tables.docx", "NANRK_Table_"),
    "2_KBTU": ("Gene-Burden_KBTU_rev2_clean.docx", "KBTU_rev2_Tables.docx", "KBTU_Table_"),
    "3_ARU": ("Мақала_KZ_Вестник_АРУ_v9_clean.docx", "ARU_v9_Кестелер_Tables.docx", "ARU_Кесте_"),
}
CAPTION = re.compile(r"^(Table|Кесте|Таблица)\s*\d+\s*[–.]")


def strip_highlight(src: Path, dst: Path) -> None:
    d = docx.Document(src)
    for part in [d.part] + [rel.target_part for rel in d.part.rels.values() if "header" in rel.reltype or "footer" in rel.reltype]:
        for h in list(part.element.iter(qn("w:highlight"))):
            h.getparent().remove(h)
    d.save(dst)


def text(el) -> str:
    return "".join(x.text or "" for x in el.iter(qn("w:t"))).strip()


def export_tables(article: Path, out_docx: Path, csv_prefix: str) -> list[str]:
    d = docx.Document(article)
    body = d.element.body
    kids = list(body)
    keep, found = set(), []
    for i, el in enumerate(kids):
        if el.tag == qn("w:p") and CAPTION.match(text(el)):
            for j in range(i + 1, min(i + 4, len(kids))):
                if kids[j].tag == qn("w:tbl"):
                    keep.update([i, j]); found.append((text(el), kids[j])); break
    for i, el in enumerate(kids):
        if el.tag == qn("w:sectPr"):
            continue
        if i not in keep:
            body.remove(el)
        elif el.tag == qn("w:tbl"):
            el.addnext(docx.oxml.OxmlElement("w:p"))
    d.save(out_docx)
    names = []
    for cap, tbl in found:
        num = re.match(r"^\D*(\d+)", cap).group(1)
        rows = [[text(tc) for tc in tr.iter(qn("w:tc"))] for tr in tbl.iter(qn("w:tr"))]
        with open(f"{csv_prefix}{num}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow([cap]); w.writerows(rows)
        names.append(cap[:60])
    return names


def main() -> int:
    for hl in sorted(FIN.glob("*/1_article/*_highlighted.docx")):
        clean = hl.with_name(hl.name.replace("_highlighted", "_clean"))
        strip_highlight(hl, clean)
        print("clean:", clean.name)
    for art, (clean, tdoc, pfx) in TABLES.items():
        tdir = FIN / art / "3_tables"
        tdir.mkdir(exist_ok=True)
        caps = export_tables(FIN / art / "1_article" / clean, tdir / tdoc, str(tdir / pfx))
        print(art, "tables:", caps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
