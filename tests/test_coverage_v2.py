"""Unit tests for corrected Bronze coverage semantics (no Spark required)."""
import copy
import unittest
from datetime import date

from harness.coverage_v2 import parse_competencia, evaluate_coverage


def sample_rows():
    rows = []
    for i in range(13):
        rows.append({
            "dataset": "producao_mar" if i < 3 else "producao_terra",
            "source_file_sha256": f"{i + 1:064x}",
            "nome_arquivo": f"historical_{i}.csv",
            "registros_esperados": 1,
            "registros_encontrados": 1,
            "competencias_invalidas": 0,
            "ano_invalido_ou_divergente": 0,
            "identificadores_essenciais_ausentes": 0,
            "instalacoes_ausentes": 0,
        })
    rows[10].update({
        "nome_arquivo": "producao_por_poco_terra_2025_4_trim.csv",
        "registros_esperados": 30123,
        "registros_encontrados": 30123,
    })
    rows[11].update({
        "nome_arquivo": "producao_por_poco_terra_2026_1_trim.csv",
        "registros_esperados": 20389,
        "registros_encontrados": 20389,
        "instalacoes_ausentes": 657,
    })
    rows[12].update({
        "nome_arquivo": "producao_por_poco_terra_2026_2_trim.csv",
        "registros_esperados": 15486,
        "registros_encontrados": 15486,
        "instalacoes_ausentes": 459,
    })
    return rows


class CoveragePolicyTests(unittest.TestCase):
    def test_months_numeric_and_portuguese(self):
        self.assertEqual(parse_competencia("10/2025"), date(2025, 10, 1))
        self.assertEqual(parse_competencia("OUT/2025"), date(2025, 10, 1))
        self.assertEqual(parse_competencia("nov/2025"), date(2025, 11, 1))
        self.assertEqual(parse_competencia(" dez/2025 "), date(2025, 12, 1))

    def test_invalid_month_does_not_become_zero(self):
        for value in ("13/2025", "foo/2025", "", None, "abr/0000"):
            self.assertIsNone(parse_competencia(value))

    def test_historical_absent_installations_are_preserved(self):
        report = evaluate_coverage(sample_rows())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["missing_installations"], 1116)
        self.assertEqual(report["files_checked"], 13)

    def test_missing_essential_identifier_is_blocking(self):
        rows = sample_rows()
        rows[10]["identificadores_essenciais_ausentes"] = 1
        result = evaluate_coverage(rows)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("MISSING_ESSENTIAL_IDENTIFIER",
                      [issue["code"] for issue in result["issues"]])

    def test_unexpected_missing_installation_count_is_blocking(self):
        rows = sample_rows()
        rows[12]["instalacoes_ausentes"] = 458
        result = evaluate_coverage(rows)
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("MISSING_INSTALLATION_BASELINE_MISMATCH",
                      [issue["code"] for issue in result["issues"]])

    def test_missing_bronze_file_is_invalid(self):
        with self.assertRaises(ValueError):
            evaluate_coverage(sample_rows()[:-1])

    def test_duplicate_source_hash_is_invalid(self):
        rows = sample_rows()
        rows[1]["source_file_sha256"] = rows[0]["source_file_sha256"]
        rows[1]["dataset"] = rows[0]["dataset"]
        with self.assertRaises(ValueError):
            evaluate_coverage(rows)

    def test_row_count_mismatch_is_blocking(self):
        rows = sample_rows()
        rows[10]["registros_encontrados"] -= 1
        report = evaluate_coverage(rows)
        self.assertEqual(report["status"], "BLOCK")
        self.assertIn("ROW_COUNT_MISMATCH",
                      [issue["code"] for issue in report["issues"]])

    def test_bad_competence_is_blocking(self):
        rows = sample_rows()
        rows[10]["competencias_invalidas"] = 1
        report = evaluate_coverage(rows)
        self.assertEqual(report["status"], "BLOCK")

    def test_coverage_does_not_edit_input(self):
        rows = sample_rows()
        original = copy.deepcopy(rows)
        evaluate_coverage(rows)
        self.assertEqual(rows, original)


if __name__ == "__main__":
    unittest.main()
