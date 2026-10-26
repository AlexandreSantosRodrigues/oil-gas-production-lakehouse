"""Deterministic, fail-closed evaluation of pinned Databricks Ops checks.

The gate never runs SQL or mutates Lakehouse tables. Its inputs are a compact
snapshot exported from existing Ops tables by harness.databricks.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

STAGES = {
    "structure": {"PASS", "REVIEW", "ERROR"},
    "coverage": {"PASS", "REVIEW"},
    "silver": {"PASS", "FAIL"},
    "published": {"PASS", "FAIL"},
}
MAX_ROWS = 500
SCOPE = "historico_anp_v2"


class InvalidSnapshot(ValueError):
    """Snapshot is insufficient or inconsistent; never infer PASS."""


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidSnapshot(f"{label} must be a nonempty string")
    return value.strip()


def _number(row: dict, field: str) -> Decimal:
    value = row.get(field)
    if isinstance(value, bool) or value is None:
        raise InvalidSnapshot(f"missing numeric field: {field}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidSnapshot(f"invalid numeric field: {field}") from exc
    if not number.is_finite():
        raise InvalidSnapshot(f"non-finite numeric field: {field}")
    return number


def _identity(stage: str, row: dict, offset: int) -> str:
    if stage == "published":
        return str(row.get("view") or f"row_{offset}")
    return str(row.get("nome_arquivo") or row.get("source_file_sha256")
               or row.get("dataset") or f"row_{offset}")[:180]


def _invariant_error(stage: str, row: dict) -> str | None:
    """Independently check PASS rows so a mislabeled PASS cannot slip through."""
    if stage == "structure":
        if row.get("hash_confere") is not True:
            return "HASH_MISMATCH_OR_MISSING"
        if _number(row, "registros_com_estrutura_invalida") != 0:
            return "INVALID_CSV_STRUCTURE"
    elif stage == "coverage":
        if _number(row, "registros_encontrados") != _number(row, "registros_esperados"):
            return "ROW_COUNT_MISMATCH"
        for name in ("competencias_invalidas", "ano_invalido_ou_divergente",
                     "registros_com_chave_incompleta"):
            if _number(row, name) != 0:
                return "INVALID_COVERAGE"
    elif stage == "silver":
        pairs = (("registros_csv", "registros_silver"),
                 ("total_csv", "total_silver"),
                 ("preenchidos_csv", "preenchidos_silver"),
                 ("zeros_csv", "zeros_silver"))
        for left, right in pairs:
            # Spark SQL can reconcile two NULL totals with eqNullSafe.
            # Preserve that exact semantics for measures that are all NULL.
            if row.get(left) is None and row.get(right) is None:
                continue
            if _number(row, left) != _number(row, right):
                return f"RECONCILIATION_MISMATCH:{left}"
    elif stage == "published":
        expected = _number(row, "registros_esperados")
        if expected != _number(row, "registros_publicados"):
            return "PUBLISHED_COUNT_MISMATCH"
        if expected != _number(row, "fatos_distintos"):
            return "NON_UNIQUE_FACT_IDS"
    return None


def evaluate(snapshot: dict) -> dict:
    """Return a deterministic PASS/BLOCK result; reject incomplete evidence.

    There is no accepted WARN state: REVIEW, ERROR, FAIL and invalid input block.
    All four stages and nonempty explicit run IDs are mandatory.
    """
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise InvalidSnapshot("schema_version must be 1")
    scope_id = _required_text(snapshot.get("scope_id"), "scope_id")
    if scope_id != SCOPE:
        raise InvalidSnapshot(f"unsupported scope: {scope_id}")
    contract_run_id = _required_text(snapshot.get("contract_run_id"),
                                     "contract_run_id")
    checks = snapshot.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(STAGES):
        raise InvalidSnapshot("checks must contain exactly: " + ", ".join(STAGES))

    issues: list[dict] = []
    totals: dict[str, int] = {}
    run_ids: dict[str, str] = {}
    for stage, allowed in STAGES.items():
        check = checks[stage]
        if not isinstance(check, dict):
            raise InvalidSnapshot(f"{stage}: check must be an object")
        run_id = _required_text(check.get("run_id"), f"{stage}.run_id")
        rows = check.get("rows")
        if not isinstance(rows, list) or not (1 <= len(rows) <= MAX_ROWS):
            raise InvalidSnapshot(f"{stage}: expected 1..{MAX_ROWS} rows")
        run_ids[stage] = run_id
        totals[stage] = len(rows)
        for pos, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise InvalidSnapshot(f"{stage}: row {pos} is not an object")
            if row.get("status") not in allowed:
                raise InvalidSnapshot(f"{stage}: unknown/missing status on row {pos}")
            if row.get("run_id") != run_id:
                raise InvalidSnapshot(f"{stage}: row {pos} belongs to another run")
            if stage in ("coverage", "silver"):
                if row.get("contract_run_id") != contract_run_id:
                    raise InvalidSnapshot(f"{stage}: contract lineage mismatch")
            if stage == "published" and row.get("escopo_id") != scope_id:
                raise InvalidSnapshot("published: scope lineage mismatch")

            status = row["status"]
            identity = _identity(stage, row, pos)
            if status != "PASS":
                issues.append({
                    "stage": stage, "item": identity,
                    "code": f"OPERATIONAL_{status}",
                    "message": str(row.get("error_message") or status)[:300],
                })
            else:
                invalid = _invariant_error(stage, row)
                if invalid:
                    issues.append({
                        "stage": stage, "item": identity, "code": invalid,
                        "message": "A PASS row violates an independent invariant",
                    })
    issues.sort(key=lambda x: (x["stage"], x["item"], x["code"]))
    return {
        "status": "BLOCK" if issues else "PASS",
        "scope_id": scope_id,
        "contract_run_id": contract_run_id,
        "run_ids": run_ids,
        "checked_rows": totals,
        "issues": issues,
    }
