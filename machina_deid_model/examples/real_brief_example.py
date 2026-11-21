"""Adapting to the real brief (the equivalent of the reference repo's engineering example).

When the real Machina CAD De-ID brief drops at kickoff, the harness does not
change -- only the data loader and the metric do. The three edits:

1. Replace ``data.py`` so a "case" is the brief's real file format (could be
   DXF / IGES / native CAD or a metadata JSON) with the real truth set.
2. Replace ``evaluation.py`` so ``check`` matches the brief's real pass
   conditions exactly (add identifier classes: addresses, phone numbers, GD&T
   notes), still reporting leak / broken / lost separately.
3. Keep ``solvers.py`` (the seed-and-propagate idea) and the ladder.

This example applies the strongest de-identifier to one hand-built STEP file and
checks it with the scorer, so it runs fast with no RNG.

    python machina_deid_model/examples/real_brief_example.py [--n N]
"""
from __future__ import annotations

import argparse

from machina_deid.evaluation import check
from machina_deid.model import MachinaDeidModel

# A single case shaped like the real task: a tiny valid STEP file whose owner's
# identity hides in the header path, a comment, a \X2\ escape, and a label.
CASE_TEXT = (
    "ISO-10303-21;\n"
    "HEADER;\n"
    "FILE_DESCRIPTION(('bracket for Project Kestrel'),'2;1');\n"
    "FILE_NAME('C:\\\\Users\\\\praman\\\\CAD\\\\AK-12345-01_bracket.stp','2026-01-10T10:22:31',"
    "('Priya Raman'),('Aerodyne Systems'),'SwiftCAD 2026','SwiftCAD','Raman');\n"
    "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\n"
    "ENDSEC;\n"
    "DATA;\n"
    "/* exported by priya.raman@aerodyne.com - Aerodyne Systems proprietary */\n"
    "#11=APPLICATION_CONTEXT('core data for automotive mechanical design processes');\n"
    "#12=APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#11);\n"
    "#13=PRODUCT_CONTEXT('',#11,'mechanical');\n"
    "#14=PRODUCT('AK-12345-01','\\X2\\00410065007200\\X0\\','rev C - Project Kestrel',(#13));\n"
    "#15=PERSON('praman','Raman','Priya',$,$,$);\n"
    "#16=ORGANIZATION('AERODYNE','Aerodyne Systems','design authority');\n"
    "#17=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.));\n"
    "#18=DESCRIPTIVE_REPRESENTATION_ITEM('material','Ti-6Al-4V');\n"
    "#19=CARTESIAN_POINT('datum A',(1.0000,2.0000,3.0000));\n"
    "#20=CARTESIAN_POINT('Aerodyne_bracket_face1',(4.0000,5.0000,6.0000));\n"
    "ENDSEC;\n"
    "END-ISO-10303-21;\n"
)
TRUTH = {"sensitive": ["Aerodyne Systems", "Aerodyne", "Priya Raman", "Raman", "Priya",
                       "Project Kestrel", "AK-12345-01", "praman",
                       "priya.raman@aerodyne.com"],
         "material": "Ti-6Al-4V"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1, help="ignored; kept for harness parity")
    ap.parse_args()

    model = MachinaDeidModel()
    cleaned = model.solve(CASE_TEXT, level=5)  # v5 seed-and-propagate
    result = check(CASE_TEXT, cleaned, TRUTH)
    print("v5 seed-and-propagate on one hand-built case:")
    print(f"  passes:   {result['pass']}")
    print(f"  leaked:   {result['leak']}   geometry ok: {result['geometry']}   "
          f"valid: {result['valid']}   required data kept: {result['kept']}")
    datum_label = "'datum A'"
    print(f"  harmless 'datum A' label survives: {datum_label in cleaned}")
    print("\nWhen the brief drops: swap data.py + evaluation.py, keep solvers.py and the ladder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
