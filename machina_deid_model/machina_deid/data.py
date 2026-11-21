"""Synthetic STEP (ISO 10303-21) file generator and the STEP parsing helpers.

Lifted verbatim (behaviour-preserving) from the original
``practice/machina_cad_deid/bench.py``. We do not know the real Machina CAD
De-ID format yet; this generates the hidden ways an identifier can hide in a CAD
file: inside STEP ``\\X2\\`` unicode escapes, header file paths and e-mails,
``/* ... */`` comments, PERSON / ORGANIZATION / PRODUCT records, and geometry
labels -- while real engineering data (schema name, units, material) and
harmless labels (``datum A``) must survive.

This module owns only *data*: the generator (``make_case`` / ``dataset``) and
the STEP parsing helpers a scorer needs (``parse``, ``decode_x2``,
``geometry_signature``, the record/number/string regexes). The scorer itself
(``check`` / ``score``) lives in :mod:`machina_deid.evaluation`.
"""
from __future__ import annotations

import random
import re

COMPANIES = ["Aerodyne Systems", "Northwind Motors", "Halcyon Aerospace", "Vexel Robotics", "Corvid Defense", "Lumen Marine"]
PEOPLE = ["Priya Raman", "Tomas Okafor", "Elena Vasquez", "Marcus Lindqvist", "Jun Watanabe", "Sofia Marchetti"]
PROGRAMS = ["FALCON-9X", "Project Kestrel", "ORION-MK2", "Bluebird", "TITAN-LV", "Skylark"]
PARTS = ["bracket", "housing", "flange", "manifold", "rib", "panel", "gusset", "fairing"]
MATERIALS = ["Al 6061-T6", "Ti-6Al-4V", "SS 304", "Inconel 718"]


def _x2(s: str) -> str:
    return "\\X2\\" + "".join(f"{ord(c):04X}" for c in s) + "\\X0\\"


def make_case(rng: random.Random):
    company, person, program = rng.choice(COMPANIES), rng.choice(PEOPLE), rng.choice(PROGRAMS)
    part = rng.choice(PARTS)
    pn = f"{rng.choice('ABCDEFGH')}{rng.choice('KLMNPR')}-{rng.randint(10000, 99999)}-{rng.randint(1, 9):02d}"
    email = f"{person.split()[0].lower()}.{person.split()[1].lower()}@{company.split()[0].lower()}.com"
    user = person.split()[0].lower()[0] + person.split()[1].lower()
    material = rng.choice(MATERIALS)
    sensitive = [company, company.split()[0], person, person.split()[1], program, pn, email, user]
    L: list[str] = ["ISO-10303-21;", "HEADER;",
                    f"FILE_DESCRIPTION(('{part} for {program}'),'2;1');",
                    f"FILE_NAME('C:\\\\Users\\\\{user}\\\\CAD\\\\{pn}_{part}.stp','2026-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}T10:22:31',('{person}'),('{company}'),'SwiftCAD 2026','SwiftCAD','{person.split()[1]}');",
                    "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", "ENDSEC;", "DATA;"]
    if rng.random() < 0.6:
        L.append(f"/* exported by {email} - {company} proprietary - do not distribute */")
    n = 10
    ents: list[tuple[int, str]] = []

    def add(body: str) -> int:
        nonlocal n
        n += 1
        ents.append((n, body))
        return n

    add("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    add("APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#11)")
    add("PRODUCT_CONTEXT('',#11,'mechanical')")
    name_style = rng.random()
    if name_style < 0.4:
        prod_name = f"{company} {part}"
    elif name_style < 0.7:
        prod_name = _x2(f"{program} {part}")            # unicode-escaped identifier
    else:
        prod_name = f"{part}_{pn}"
    add(f"PRODUCT('{pn}','{prod_name}','rev C - {program}',(#13))")
    add(f"PERSON('{user}','{person.split()[1]}','{person.split()[0]}',$,$,$)")
    add(f"ORGANIZATION('{company.split()[0].upper()}','{company}','design authority')")
    add(f"PERSON_AND_ORGANIZATION(#{n - 1},#{n})")
    add("(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.))")
    add(f"DESCRIPTIVE_REPRESENTATION_ITEM('material','{material}')")
    if rng.random() < 0.5:
        add(f"DESCRIPTIVE_REPRESENTATION_ITEM('customer','{company}')")
    if rng.random() < 0.5:
        add(f"DESCRIPTIVE_REPRESENTATION_ITEM('notes','contact {person} re: {program} tolerance stack')")
    for k in range(rng.randint(25, 45)):
        r = rng.random()
        label = ""
        if r < 0.12:
            label = f"{company.split()[0]}_{part}_face{k}"   # identifier hiding in a geometry label
        elif r < 0.2:
            label = f"{pn}-hole{k}"
        elif r < 0.3:
            label = f"datum {rng.choice('ABC')}"             # harmless label
        kind = rng.choice(["CARTESIAN_POINT", "DIRECTION", "CIRCLE", "LINE"])
        nums = ",".join(f"{rng.uniform(-250, 250):.4f}" for _ in range(3))
        if kind in ("CARTESIAN_POINT", "DIRECTION"):
            add(f"{kind}('{label}',({nums}))")
        else:
            add(f"{kind}('{label}',#{rng.randint(11, n)},{rng.uniform(0.5, 80):.4f})")
    if rng.random() < 0.4:
        add(f"COLOUR_RGB('{company.split()[0]} Blue',0.1,0.3,0.8)")
    add("ADVANCED_BREP_SHAPE_REPRESENTATION('',(#30),#18)")
    for i, body in ents:
        if rng.random() < 0.08 and len(body) > 60:          # long records wrap across lines
            cut = body.rfind(",", 0, 50)
            L.append(f"#{i}={body[:cut + 1]}\n   {body[cut + 1:]};")
        else:
            L.append(f"#{i}={body};")
    L += ["ENDSEC;", "END-ISO-10303-21;"]
    truth = {"sensitive": sorted(set(sensitive), key=len, reverse=True), "material": material}
    return "\n".join(L) + "\n", truth


def dataset(n: int, seed: int):
    """A list of ``(step_text, truth)`` pairs."""
    rng = random.Random(seed)
    return [make_case(rng) for _ in range(n)]


# ---------- STEP parsing helpers (shared by the scorer in evaluation.py) ----------
_ENT = re.compile(r"#(\d+)\s*=\s*(.*?);\s*(?=#\d+\s*=|ENDSEC)", re.S)
_NUM = re.compile(r"(?<![\w#'.])-?\d+\.\d+(?:E[+-]?\d+)?")
_STR = re.compile(r"'(?:[^']|'')*'")


def decode_x2(s: str) -> str:
    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\",
                  lambda m: "".join(chr(int(m.group(1)[i:i + 4], 16)) for i in range(0, len(m.group(1)), 4)), s)


def parse(text: str):
    if "DATA;" not in text or "END-ISO-10303-21;" not in text or not text.startswith("ISO-10303-21;"):
        return None
    data = text.split("DATA;", 1)[1]
    data = re.sub(r"/\*.*?\*/", "", data, flags=re.S)
    out = []
    for m in _ENT.finditer(data):
        body = re.sub(r"\s*\n\s*", "", m.group(2))
        typ = re.match(r"\(?\s*([A-Z_0-9]+)", body)
        out.append((int(m.group(1)), typ.group(1) if typ else "?", body))
    return out


def geometry_signature(ents) -> list:
    return [(i, t, tuple(_NUM.findall(_STR.sub("''", b))), tuple(re.findall(r"#\d+", b))) for i, t, b in ents]
