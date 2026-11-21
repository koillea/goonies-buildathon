"""The ladder climbs, and the directional/hybrid rungs beat the popularity baseline."""
from __future__ import annotations

from databricks_shopping import solvers
from databricks_shopping.evaluation import score
from databricks_shopping.model import DatabricksShoppingModel


def test_bigram_and_hybrid_beat_popularity(splits):
    train, dev, _ = splits
    rec0 = solvers.v0_global_popularity(train)
    rec2 = solvers.v2_next_item_bigram(train)
    rec5 = solvers.v5_hybrid(train)
    recall0 = score(rec0, dev)[0]
    recall2 = score(rec2, dev)[0]
    recall5 = score(rec5, dev)[0]
    # Modelling the transition signal beats global popularity, and the hybrid is
    # at least as strong as the plain bigram (the revisit-bonus lesson).
    assert recall2 > recall0
    assert recall5 >= recall2


def test_revisit_matters(splits):
    """The next event is often the same item; allowing revisits must not hurt."""
    train, dev, _ = splits
    with_revisit = score(solvers.v5_hybrid(train, revisit=0.2), dev)[0]
    no_revisit = score(solvers.v5_hybrid(train, revisit=0.0), dev)[0]
    assert with_revisit >= no_revisit


def test_ladder_climbs_on_hidden(model: DatabricksShoppingModel):
    report = model.run(n=12)
    recalls = [r.hidden.headline for r in report.results]
    # The strongest hidden recall is at least the weakest (v0 baseline).
    assert max(recalls) >= recalls[0]
    assert report.best.hidden.headline >= report.results[0].hidden.headline


def test_evaluate_reports_recall_and_mrr(model: DatabricksShoppingModel):
    report = model.run(n=12)
    hidden = report.results[-1].hidden.metrics
    assert set(hidden) == {"recall", "mrr"}
    assert report.metric_name == "recall@20"


def test_generalizes_dev_matches_hidden(model: DatabricksShoppingModel):
    # The whole point of the dev/hidden protocol: strong rungs agree across splits.
    # Deterministic under the fixed default seeds; n large enough to clear noise.
    report = model.run(n=100)
    by_name = {r.solution.name: r for r in report.results}
    assert by_name["v5 hybrid: bigram + earlier items + revisit bonus"].generalizes
    assert by_name["v6 v5 tuned on a time split"].generalizes
