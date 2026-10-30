"""Synthetic regression: a successful diagnostic must preserve historic BLOCK."""
import copy
import unittest
from unittest.mock import patch

from test_harness import snapshot
from scripts.verify_historical_readonly import verify, fingerprint


def baseline():
    data = snapshot()
    for stage, count in dict(structure=15, coverage=13, silver=169, published=3).items():
        row = data['checks'][stage]['rows'][0]
        data['checks'][stage]['rows'] = [copy.deepcopy(row) for _ in range(count)]
    data['checks']['structure']['rows'][0]['status'] = 'REVIEW'
    for row in data['checks']['coverage']['rows'][:3]:
        row['status'] = 'REVIEW'
    return data


class HistoricalDiagnosticTests(unittest.TestCase):
    def run_check(self, data, coverage='PASS', second=None):
        with patch('scripts.verify_historical_readonly.export_snapshot',
                   side_effect=[data, second if second is not None else data]), patch(
                       'scripts.verify_historical_readonly.audit_bronze',
                       return_value={'status': coverage}):
            return verify(object())

    def test_diagnostic_success_preserves_block_and_input(self):
        data = baseline()
        original = copy.deepcopy(data)
        receipt = self.run_check(data)
        self.assertEqual(receipt['diagnostic_status'], 'PASS')
        self.assertEqual(receipt['historical_gate']['status'], 'BLOCK')
        self.assertFalse(receipt['publication_allowed'])
        self.assertFalse(receipt['clean_workspace_replay_proven'])
        self.assertEqual(data, original)

    def test_erasing_review_is_rejected(self):
        data = baseline()
        data['checks']['structure']['rows'][0]['status'] = 'PASS'
        with self.assertRaises(ValueError):
            self.run_check(data)

    def test_missing_silver_evidence_is_rejected(self):
        data = baseline()
        data['checks']['silver']['rows'].pop()
        with self.assertRaises(ValueError):
            self.run_check(data)

    def test_v2_failure_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_check(baseline(), coverage='BLOCK')

    def test_drift_between_reads_is_rejected(self):
        data = baseline()
        changed = copy.deepcopy(data)
        changed['checks']['structure']['rows'][0]['error_message'] = 'changed'
        with self.assertRaises(ValueError):
            self.run_check(data, second=changed)

    def test_collect_order_does_not_change_fingerprint(self):
        data = baseline()
        changed = copy.deepcopy(data)
        for check in changed['checks'].values():
            check['rows'].reverse()
        self.assertEqual(fingerprint(data), fingerprint(changed))
