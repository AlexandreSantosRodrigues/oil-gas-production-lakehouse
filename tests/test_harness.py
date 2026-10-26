"""Offline tests: all evidence here is synthetic, never ANP operational data."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.agent import optional_llm_review, prepare_investigation
from harness.cli import run
from harness.core import InvalidSnapshot, evaluate

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "ops_snapshot_synthetic.json"


def snapshot():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class GateTests(unittest.TestCase):
    def test_valid_snapshot_passes(self):
        result = evaluate(snapshot())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["checked_rows"]["silver"], 1)

    def test_structural_review_blocks(self):
        data = snapshot()
        data["checks"]["structure"]["rows"][0]["status"] = "REVIEW"
        result = evaluate(data)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["issues"][0]["code"], "OPERATIONAL_REVIEW")

    def test_silver_fail_blocks(self):
        data = snapshot()
        data["checks"]["silver"]["rows"][0]["status"] = "FAIL"
        self.assertEqual(evaluate(data)["status"], "BLOCK")

    def test_fake_pass_cannot_hide_reconciliation_mismatch(self):
        data = snapshot()
        data["checks"]["silver"]["rows"][0]["total_silver"] = "12.51"
        issues = evaluate(data)["issues"]
        self.assertEqual(issues[0]["code"],
                         "RECONCILIATION_MISMATCH:total_csv")

    def test_null_totals_are_valid_if_both_are_null(self):
        data = snapshot()
        row = data["checks"]["silver"]["rows"][0]
        row["total_csv"] = None
        row["total_silver"] = None
        self.assertEqual(evaluate(data)["status"], "PASS")

    def test_mixed_contracts_are_invalid(self):
        data = snapshot()
        data["checks"]["coverage"]["rows"][0]["contract_run_id"] = "other"
        with self.assertRaises(InvalidSnapshot):
            evaluate(data)

    def test_mixed_scope_is_invalid(self):
        data = snapshot()
        data["checks"]["published"]["rows"][0]["escopo_id"] = "other"
        with self.assertRaises(InvalidSnapshot):
            evaluate(data)

    def test_mixed_run_ids_are_invalid(self):
        data = snapshot()
        data["checks"]["silver"]["rows"][0]["run_id"] = "other"
        with self.assertRaises(InvalidSnapshot):
            evaluate(data)

    def test_absent_stage_is_invalid(self):
        data = snapshot()
        del data["checks"]["coverage"]
        with self.assertRaises(InvalidSnapshot):
            evaluate(data)

    def test_empty_rows_are_invalid(self):
        data = snapshot()
        data["checks"]["published"]["rows"] = []
        with self.assertRaises(InvalidSnapshot):
            evaluate(data)

    def test_bad_status_is_invalid(self):
        data = snapshot()
        data["checks"]["structure"]["rows"][0]["status"] = "UNKNOWN"
        with self.assertRaises(InvalidSnapshot):
            evaluate(data)

    def test_published_duplicate_facts_are_blocked(self):
        data = snapshot()
        data["checks"]["published"]["rows"][0]["fatos_distintos"] = 1
        issues = evaluate(data)["issues"]
        self.assertEqual(issues[0]["code"], "NON_UNIQUE_FACT_IDS")

    def test_bad_hash_blocked_even_when_labeled_pass(self):
        data = snapshot()
        data["checks"]["structure"]["rows"][0]["hash_confere"] = False
        self.assertEqual(evaluate(data)["status"], "BLOCK")

    def test_agent_only_proposes_read_only_checks(self):
        data = snapshot()
        data["checks"]["coverage"]["rows"][0]["status"] = "REVIEW"
        investigation = prepare_investigation(evaluate(data))
        self.assertFalse(investigation["publication_allowed"])
        self.assertEqual(investigation["permission"], "read_only")
        self.assertEqual(len(investigation["hypotheses"]), 1)

    def test_remote_http_is_rejected_for_llm(self):
        with self.assertRaises(ValueError):
            optional_llm_review({"hypotheses": []},
                                "http://example.com/v1/chat/completions",
                                "some-model")

    def test_cli_writes_receipt_and_keeps_gate_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            code, receipt = run(FIXTURE, path / "receipts")
            self.assertEqual(code, 0)
            saved = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "PASS")
            self.assertFalse(saved["investigation"]["publication_allowed"])
            self.assertEqual(len(saved["input_sha256"]), 64)

            broken = snapshot()
            broken["checks"]["silver"]["rows"][0]["status"] = "FAIL"
            failure = path / "failure.json"
            failure.write_text(json.dumps(broken), encoding="utf-8")
            code, receipt = run(failure, path / "receipts")
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(receipt.read_text())["status"], "BLOCK")

    def test_invalid_snapshot_receipt_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "invalid.json"
            p.write_text("{}", encoding="utf-8")
            code, receipt = run(p, Path(directory) / "logs")
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(receipt.read_text())["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()
