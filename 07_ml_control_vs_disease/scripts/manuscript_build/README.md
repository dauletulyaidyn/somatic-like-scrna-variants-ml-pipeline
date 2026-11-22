# manuscript_build

Builds the revised manuscripts (NAN RK rev6, KBTU Herald rev2, Vestnik ARU v9), their supplementary materials and table exports from the result tables in `../../results/light_additions_2026-11-21/`.

| Script | Output |
|---|---|
| `results_numbers.py` | loads all numbers used in the texts from the result TSV files |
| `docbuild.py` | docx helpers (highlighted paragraphs, equations, tables, citation renumbering) |
| `build_nanrk.py` | NAN RK manuscript (new element: coverage-normalised gene burden) |
| `build_kbtu.py` | KBTU manuscript (new element: Brier score with exact null) |
| `build_aru.py` | ARU manuscript (new element: elastic-net logistic regression); needs the v8 source docx locally |
| `build_supp.py` | Supplementary Materials docx + CSV tables S1–S6 for all three articles |
| `make_clean_and_tables.py` | clean (unhighlighted) copies and per-table docx/CSV exports |

Numbers are never typed by hand: every value in the texts is read from the analysis outputs (`light_00`–`light_06` scripts in `../`).
Letters to the editors and source manuscripts are not tracked (they contain contact data).
Run with Python ≥ 3.11, `python-docx`, `pandas`.
