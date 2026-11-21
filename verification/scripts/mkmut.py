import subprocess, os, shutil, json, sys
SRC="/tmp/claude-0/gt/sqlglot"; OUT="/tmp/claude-0/mut"
# (id, kind, file, old, new)  -- first occurrence replaced
M = [
 # --- blind-spot probes
 ("p_syntax", "syntax error in a 1-test function (tsql splitpart_sql)", "sqlglot/generators/tsql.py",
  "        split_count = len(this.name.split(\".\"))\n", "        split_count = len(this.name.split(\".\")\n"),
 ("p_indent", "IndentationError in a never-run simplify function", "sqlglot/optimizer/simplify.py", None, "INDENT@137"),
 ("p_typing", "redundant typing metadata entry (static test_typing)", "sqlglot/typing/duckdb.py",
  "EXPRESSION_METADATA = {\n    **EXPRESSION_METADATA,\n", "EXPRESSION_METADATA = {\n    **EXPRESSION_METADATA,\n    exp.Floor: dict(EXPRESSION_METADATA[exp.Floor]),\n"),
 ("p_lazy", "eager dialect import in sqlglot/__init__ (subprocess test_lazy_load)", "sqlglot/__init__.py",
  "from sqlglot.diff import diff as diff\n", "from sqlglot.diff import diff as diff\nimport sqlglot.dialects.duckdb  # noqa: F401\n"),
 ("p_rename", "rename drill escape_sql -> like_sql (dispatch shadowing)", "sqlglot/generators/drill.py",
  "    def escape_sql(self, expression: exp.Escape) -> str:", "    def like_sql(self, expression: exp.Escape) -> str:"),
 ("p_default", "def-line default arg NameError at import", "sqlglot/generators/tsql.py",
  "    def splitpart_sql(self, expression: exp.SplitPart) -> str:", "    def splitpart_sql(self, expression: exp.SplitPart, _x=UNDEFINED_NAME) -> str:"),
 ("p_comment_str", "comment-only line that changes a string (inside triple quote)", None, None, None),
 # --- controls (normal kinds)
 ("c_code1", "flip a condition in tsql splitpart_sql", "sqlglot/generators/tsql.py",
  "            or split_count > 4\n", "            or split_count > 3\n"),
 ("c_code2", "off-by-one in tsql exact-1-test helper _sha2_sql", "sqlglot/generators/tsql.py",
  "length', 256)", "length', 257)"),
 ("c_parser", "real bug in a hot parser path: _parse_limit", "sqlglot/parser.py", None, None),
 ("c_kw", "class attr: tsql tokenizer keyword edit", "sqlglot/dialects/tsql.py",
  '"DATETIME2": TokenType.DATETIME2,', '"DATETIME2": TokenType.DATETIME,'),
 ("c_fix", "fixture edit: identity.sql line", "tests/fixtures/identity.sql", "SELECT 1\n", "SELECT  1\n"),
 ("c_cls", "class attr: drop a duckdb typing entry", None, None, None),
 ("c_cmt", "pure comment inside a function", "sqlglot/generators/tsql.py",
  "        split_count = len(this.name.split(\".\"))\n", "        # count parts\n        split_count = len(this.name.split(\".\"))\n"),
 ("c_none", "no-op whitespace at file end of a test helper doc", "README.md", None, "APPEND"),
]
def mk(mid, kind, f, old, new):
    w=f"/tmp/claude-0/work/mk_{mid}"; shutil.rmtree(w, ignore_errors=True); os.makedirs(w)
    subprocess.run(f"cd {SRC} && git archive HEAD | tar -x -C {w} && cd {w} && git init -q && git add -A && git -c user.email=a@b -c user.name=a commit -qm x", shell=True, check=True)
    p=os.path.join(w,f); s=open(p).read()
    if new.startswith("INDENT@") or new.startswith("FLIP@"):
        n=int(new.split("@")[1]); L=s.split("\n")
        # first body line after def at line n
        i=n  # 0-based index n == line n+1
        while L[i].strip()=="" or L[i].strip().startswith(('"""',"#")): i+=1
        if new.startswith("INDENT"): L[i]="  "+L[i]
        else:
            L[i]=L[i].replace("256","257",1) if "256" in L[i] else L[i].replace("(", "( ", 1)
        s2="\n".join(L)
    elif new=="APPEND": s2=s+"\n"
    else:
        assert old in s, (mid, old); s2=s.replace(old,new,1)
    open(p,"w").write(s2)
    d=subprocess.run(f"cd {w} && git diff", shell=True, capture_output=True, text=True).stdout
    open(f"{OUT}/{mid}.patch","w").write(d); shutil.rmtree(w)
    json.dump(kind, open(f"{OUT}/{mid}.kind","w"))
for m in M:
    if m[2] and m[4]: mk(*m)
