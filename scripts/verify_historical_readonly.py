"""Run with an existing Databricks `spark`; reads only, prints a receipt.

This is a historical evidence repeatability check, not a pipeline replay.
"""
import hashlib
import json
from collections import Counter

from harness.core import evaluate
from harness.coverage_v2 import audit_bronze
from harness.databricks import export_snapshot

CONTRACT = "aea99472-c0f7-4fb7-b8b6-e2336f272fc4"
RUNS = {
    "structure": "6629c509-a338-4933-8e97-e0ad5c2bb98c",
    "coverage": "e31b28e1-fdd1-439a-92ea-b42e24197bad",
    "silver": "5186fc62-65c2-473d-af27-d294b08cbb78",
    "published": "e6a5a17b-62b0-4458-9afb-7b73dc60ed2d",
}


def fingerprint(snapshot):
    """Ignore Spark collect order, preserve every row and its multiplicity."""
    canonical = dict(snapshot)
    canonical["checks"] = {
        stage: {**check, "rows": sorted(
            check["rows"], key=lambda row: json.dumps(row, sort_keys=True))}
        for stage, check in snapshot["checks"].items()
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def verify(spark):
    first = export_snapshot(spark, RUNS, CONTRACT)
    gate = evaluate(first)
    if gate["checked_rows"] != dict(structure=15, coverage=13, silver=169, published=3):
        raise ValueError("Historical evidence cardinality changed")
    expected = Counter({("structure", "OPERATIONAL_REVIEW"): 1,
                        ("coverage", "OPERATIONAL_REVIEW"): 3})
    if gate["status"] != "BLOCK" or Counter(
        (issue["stage"], issue["code"]) for issue in gate["issues"]
    ) != expected:
        raise ValueError("Historical gate differs from the documented baseline")
    coverage = audit_bronze(spark, CONTRACT, expected_files=13,
                            expected_missing_installation=1116)
    if coverage["status"] != "PASS":
        raise ValueError("Corrected Bronze coverage failed")
    second = export_snapshot(spark, RUNS, CONTRACT)
    if fingerprint(first) != fingerprint(second):
        raise ValueError("Pinned Ops evidence changed between reads")
    return {"diagnostic_status": "PASS", "historical_gate": gate,
            "coverage_v2": coverage, "ops_sha256": fingerprint(first),
            "publication_allowed": False, "clean_workspace_replay_proven": False}


if __name__ == "__main__":
    print(json.dumps(verify(spark), indent=2, ensure_ascii=False))
