"""De-identifiers for the practice CAD De-ID benchmark, weakest to strongest.

Lifted verbatim (behaviour-preserving) from the original
``practice/machina_cad_deid/solutions.py``. The ladder climbs from the two
opposite failure modes -- scrub too little (identifiers leak into labels,
comments and ``\\X2\\`` escapes) and scrub too much (blank every string and the
file is no longer valid or useful) -- to two that pass: a schema allowlist, and
``seed-and-propagate``, which learns the file's own identity tokens from its
PERSON / ORGANIZATION / PRODUCT / header records and removes exactly those
everywhere while keeping harmless strings. That climb (0% -> 100% on synthetic
data) is the PLAYBOOK's "learn the identifiers from the document itself" lesson.
"""
from __future__ import annotations

import re

_STR = re.compile(r"'(?:[^']|'')*'")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_REC = re.compile(r"(#\d+\s*=\s*)(.*?)(;\s*(?=#\d+\s*=|ENDSEC))", re.S)
SCHEMA_TYPES = ("APPLICATION_CONTEXT", "APPLICATION_PROTOCOL_DEFINITION", "PRODUCT_CONTEXT",
                "PRODUCT_DEFINITION_CONTEXT", "NAMED_UNIT", "SI_UNIT", "LENGTH_UNIT")
SAFE_KEYS = ("material", "finish", "thickness", "units", "tolerance class")


def decode_x2(s: str) -> str:
    return re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\",
                  lambda m: "".join(chr(int(m.group(1)[i:i + 4], 16)) for i in range(0, len(m.group(1)), 4)), s)


def _split(text: str):
    head, rest = text.split("DATA;", 1)
    return head, rest


def _blank_strings(s: str) -> str:
    return _STR.sub("''", s)


def _scrub_header(head: str) -> str:
    def fix(m):
        return _blank_strings(m.group(0))
    head = re.sub(r"FILE_NAME\(.*?\);", fix, head, flags=re.S)
    head = re.sub(r"FILE_DESCRIPTION\(.*?\);", lambda m: "FILE_DESCRIPTION((''),'2;1');", head, flags=re.S)
    return head


def v0_noop(text: str) -> str:
    return text


def v1_header_only(text: str) -> str:
    head, data = _split(text)
    return _scrub_header(head) + "DATA;" + data


def v2_identity_entities(text: str) -> str:
    """Header + PERSON / ORGANIZATION / PRODUCT records + comments."""
    head, data = _split(text)
    data = _COMMENT.sub("", data)

    def fix(m):
        body = m.group(2)
        if re.match(r"\s*(PERSON|ORGANIZATION|PRODUCT)\(", body):
            body = _blank_strings(body)
        return m.group(1) + body + m.group(3)
    return _scrub_header(head) + "DATA;" + _REC.sub(fix, data)


def v3_blank_everything(text: str) -> str:
    """Blank every string in the data section. No leaks, but it destroys strings the format needs."""
    head, data = _split(text)
    return _scrub_header(head) + "DATA;" + _blank_strings(_COMMENT.sub("", data))


def v4_schema_allowlist(text: str) -> str:
    """Blank every string except in schema/unit records and known-safe engineering properties."""
    head, data = _split(text)
    data = _COMMENT.sub("", data)

    def fix(m):
        body = m.group(2)
        typ = re.match(r"\(?\s*([A-Z_0-9]+)", body)
        t = typ.group(1) if typ else ""
        if t in SCHEMA_TYPES:
            return m.group(0)
        if t == "DESCRIPTIVE_REPRESENTATION_ITEM":
            key = re.search(r"\('([^']*)'", body)
            if key and key.group(1).lower() in SAFE_KEYS:
                return m.group(0)
        return m.group(1) + _blank_strings(body) + m.group(3)
    return _scrub_header(head) + "DATA;" + _REC.sub(fix, data)


def _seeds(text: str) -> set[str]:
    """Identity tokens the file itself declares: header, PERSON, ORGANIZATION, PRODUCT."""
    src = []
    for pat in (r"FILE_NAME\(.*?\);", r"FILE_DESCRIPTION\(.*?\);", r"=\s*PERSON\(.*?\);", r"=\s*ORGANIZATION\(.*?\);", r"=\s*PRODUCT\(.*?\);"):
        for m in re.finditer(pat, text, re.S):
            src += [decode_x2(s[1:-1]) for s in _STR.findall(m.group(0))]
    seeds: set[str] = set()
    for s in src:
        if re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:]+", s) or "SwiftCAD" in s:
            continue
        for tok in re.split(r"[^A-Za-z0-9-]+", s):
            # keep proper nouns, codes and anything with digits; drop ordinary lowercase words
            if len(tok) >= 3 and (tok[0].isupper() or any(c.isdigit() for c in tok)) and tok.lower() not in ("rev", "stp", "users", "cad"):
                seeds.add(tok.lower())
        m = re.search(r"Users\\+(\w+)", s)
        if m:
            seeds.add(m.group(1).lower())
    return seeds


def v5_seed_and_propagate(text: str) -> str:
    """Learn who the file belongs to from its identity records, then remove those tokens
    everywhere (labels, notes, colours, escaped names) while keeping harmless strings."""
    seeds = _seeds(text)
    head, data = _split(text)
    data = _COMMENT.sub("", data)

    def clean_string(m):
        raw = m.group(0)
        low = decode_x2(raw).lower()
        return "''" if any(s in low for s in seeds) or "@" in low else raw

    def fix(m):
        body = m.group(2)
        typ = re.match(r"\(?\s*([A-Z_0-9]+)", body)
        t = typ.group(1) if typ else ""
        if t in SCHEMA_TYPES:
            return m.group(0)
        if t in ("PERSON", "ORGANIZATION", "PRODUCT"):
            return m.group(1) + _blank_strings(body) + m.group(3)
        return m.group(1) + _STR.sub(clean_string, body) + m.group(3)
    return _scrub_header(head) + "DATA;" + _REC.sub(fix, data)


ALL = [("v0 do nothing", v0_noop),
       ("v1 scrub header only", v1_header_only),
       ("v2 + person / organization / product records, comments", v2_identity_entities),
       ("v3 blank every string", v3_blank_everything),
       ("v4 blank all except schema records and safe properties", v4_schema_allowlist),
       ("v5 learn identity tokens, remove them everywhere", v5_seed_and_propagate)]
