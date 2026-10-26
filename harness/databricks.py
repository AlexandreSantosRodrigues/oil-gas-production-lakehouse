"""Explicit, read-only bridge for existing Databricks Ops Delta tables.

Use from a Databricks notebook with a SparkSession and *pinned* run IDs.
Do not auto-select latest runs: the newest rows can describe different batches.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from harness.core import MAX_ROWS, SCOPE, InvalidSnapshot

SOURCES = {
    "structure": {
        "table": "workspace.oil_gas_ops.source_file_structure_checks",
        "key": "check_run_id",
        "fields": [
            "status", "dataset", "nome_arquivo", "error_message",
            "hash_confere", "registros_com_estrutura_invalida",
            "colunas_adicionadas", "colunas_ausentes"
        ],
    },
    "coverage": {
        "table": "workspace.oil_gas_ops.production_file_coverage_checks",
        "key": "check_run_id",
        "fields": [
            "status", "contract_run_id", "dataset", "nome_arquivo",
            "registros_esperados", "registros_encontrados",
            "competencias_invalidas", "ano_invalido_ou_divergente",
            "registros_com_chave_incompleta"
        ],
    },
    "silver": {
        "table": "workspace.oil_gas_ops.silver_v2_measure_reconciliation",
        "key": "recon_run_id",
        "fields": [
            "status", "contract_run_id", "dataset", "nome_arquivo", "medida",
            "registros_csv", "registros_silver", "total_csv", "total_silver",
            "preenchidos_csv", "preenchidos_silver",
            "zeros_csv", "zeros_silver"
        ],
    },
    "published": {
        "table": "workspace.oil_gas_ops.published_scope_checks",
        "key": "check_run_id",
        "fields": [
            "status", "escopo_id", "view", "registros_esperados",
            "registros_publicados", "fatos_distintos"
        ],
    },
}


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def export_snapshot(spark, run_ids: dict[str, str], contract_run_id: str,
                    scope_id: str = SCOPE) -> dict:
    """Read only four explicit Ops runs; never modify data or choose latest.

    Run IDs must belong to a consistent contract/scope, independently
    verified by core.evaluate after extraction. No source URLs or raw
    production rows are exported; only an allowlist of check results.
    """
    if not isinstance(run_ids, dict) or set(run_ids) != set(SOURCES):
        raise InvalidSnapshot("specify exactly four run IDs")
    if not isinstance(contract_run_id, str) or not contract_run_id.strip():
        raise InvalidSnapshot("contract_run_id is required")
    if scope_id != SCOPE:
        raise InvalidSnapshot("unexpected analytical scope")

    from pyspark.sql import functions as F

    checks = {}
    for stage, spec in SOURCES.items():
        run_id = run_ids[stage]
        if not isinstance(run_id, str) or not run_id.strip():
            raise InvalidSnapshot(f"{stage}: run ID is required")

        # The table names and column lists are constants, not LLM-generated SQL.
        frame = (spark.table(spec["table"])
                 .filter(F.col(spec["key"]) == F.lit(run_id))
                 .select(*spec["fields"])
                 .limit(MAX_ROWS + 1))
        records = frame.collect()
        if not records or len(records) > MAX_ROWS:
            raise InvalidSnapshot(
                f"{stage}: found {len(records)} rows; expected 1..{MAX_ROWS}"
            )
        rows = []
        for record in records:
            row = {key: _plain(value)
                   for key, value in record.asDict(recursive=True).items()}
            row["run_id"] = run_id
            rows.append(row)
        checks[stage] = {"run_id": run_id, "rows": rows}
    return {
        "schema_version": 1,
        "scope_id": scope_id,
        "contract_run_id": contract_run_id,
        "checks": checks,
    }
