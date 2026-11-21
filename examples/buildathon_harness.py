"""Run all four tracks through the one shared harness.

The analog of his ``examples/enterprise_pipeline.py``: every unit wired together
behind one contract. Importing each track package registers its ``TrackSpec``;
``all_tracks()`` discovers them; one ``Harness`` scores them identically and
writes each ``RESULTS.md``.

    python examples/buildathon_harness.py [--n N] [--write]
"""
from __future__ import annotations

import argparse
from pathlib import Path

# Importing registers each track with buildathon_core.
import databricks_shopping  # noqa: F401
import machina_deid  # noqa: F401
import mech_royale  # noqa: F401
import rwx_blast_radius  # noqa: F401
from buildathon_core import Harness, all_tracks, render_report

# folder each track's RESULTS.md belongs in
_FOLDER = {
    "rwx_blast_radius": "rwx_blast_radius_model",
    "databricks_shopping": "databricks_shopping_model",
    "machina_deid": "machina_deid_model",
    "mech_royale": "mech_royale_model",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="cases per split")
    ap.add_argument("--write", action="store_true", help="write each track's RESULTS.md")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    harness = Harness(n=args.n)
    for spec in all_tracks():
        report = harness.run(spec)
        md = render_report(report)
        print(md)
        best = report.best
        if best is not None:
            print(f">>> {spec.name}: best hidden {spec.metric_name} = "
                  f"{best.hidden.headline:.3f} ({best.solution.name})\n")
        if args.write and spec.name in _FOLDER:
            (root / _FOLDER[spec.name] / "RESULTS.md").write_text(md, encoding="utf-8")
    print(harness.tracer.tree())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
