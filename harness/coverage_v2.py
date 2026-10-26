"""Independent read-only Bronze coverage audit for the pinned historical contract.

Fixes two *diagnostic* mismatches in the old notebook's coverage check:
1. months spelled jan..dez/AAAA (the Silver v2 parser already accepts these);
2. missing installation (Silver v2 preserves it with AUSENTE status).

Does not rewrite existing Ops checks, waive structural REVIEW, or approve Gold.
Requires an explicit source-file read contract ID and expected historical scope.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

MONTHS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4,
    "mai": 5, "jun": 6, "jul": 7, "ago": 8,
    "set": 9, "out": 10, "nov": 11, "dez": 12,
}
NUMERIC_MONTH = re.compile(r"^(0[1-9]|1[0-2])/([0-9]{4})$")
PORTUGUESE_MONTH = re.compile(
    r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/([0-9]{4})$"
)


def parse_competencia(text: str | None) -> date | None:
    """Reference parser for offline tests; mirrors Silver v2 and Spark logic."""
    if not isinstance(text, str):
        return None
    value = text.strip().lower()
    numeric = NUMERIC_MONTH.fullmatch(value)
    named = PORTUGUESE_MONTH.fullmatch(value)
    if not numeric and not named:
        return None
    month = int(numeric.group(1)) if numeric else MONTHS[named.group(1)]
    year = int((numeric or named).group(2))
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def evaluate_coverage(rows: list[dict[str, Any]],
                      *, expected_files: int = 13,
                      expected_missing_installation: int = 1116) -> dict:
    """Pure function checking audited aggregates; cannot modify any table.

    Expected 13 files/1116 missing installations are ONLY for the pinned
    historico_anp_v2 historical production scope, not for new ANP deliveries.
    """
    if not isinstance(rows, list) or len(rows) != expected_files:
        raise ValueError(f"Expected exactly {expected_files} historical files")
    problems = []
    identities = set()
    missing_installations = 0
    report = []
    for row in rows:
        dataset = row.get("dataset")
        sha = row.get("source_file_sha256")
        if dataset not in ("producao_terra", "producao_mar"):
            raise ValueError(f"Unexpected dataset: {dataset}")
        if not isinstance(sha, str) or len(sha) != 64 or any(
            c not in "0123456789abcdefABCDEF" for c in sha
        ):
            raise ValueError("Missing or invalid source-file SHA-256")
        identity = (dataset, sha.lower())
        if identity in identities:
            raise ValueError("Duplicated source-file identity")
        identities.add(identity)
        name = row.get("nome_arquivo")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Missing source file name")

        required = (
            "registros_esperados", "registros_encontrados",
            "competencias_invalidas", "ano_invalido_ou_divergente",
            "identificadores_essenciais_ausentes", "instalacoes_ausentes"
        )
        for field in required:
            value = row.get(field)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name}: invalid {field}")
        expected = row["registros_esperados"]
        observed = row["registros_encontrados"]
        missing_install = row["instalacoes_ausentes"]
        if missing_install > observed:
            raise ValueError(f"{name}: impossible missing installation count")
        if row["identificadores_essenciais_ausentes"] > observed:
            raise ValueError(f"{name}: impossible missing essential count")
        if row["competencias_invalidas"] > observed:
            raise ValueError(f"{name}: impossible invalid month count")
        missing_installations += missing_install

        reasons = []
        if observed != expected:
            reasons.append("ROW_COUNT_MISMATCH")
        if row["competencias_invalidas"]:
            reasons.append("INVALID_MONTH")
        if row["ano_invalido_ou_divergente"]:
            reasons.append("YEAR_MISMATCH")
        if row["identificadores_essenciais_ausentes"]:
            reasons.append("MISSING_ESSENTIAL_IDENTIFIER")
        for code in reasons:
            problems.append({"file": name, "code": code})
        report.append({
            "dataset": dataset,
            "file": name,
            "status": "BLOCK" if reasons else "PASS",
            "rows": observed,
            "missing_installation": missing_install,
        })

    if missing_installations != expected_missing_installation:
        problems.append({
            "file": "HISTORICAL_SCOPE",
            "code": "MISSING_INSTALLATION_BASELINE_MISMATCH",
            "expected": expected_missing_installation,
            "observed": missing_installations,
        })
    problems.sort(key=lambda x: (x["file"], x["code"]))
    report.sort(key=lambda x: (x["dataset"], x["file"]))
    return {
        "status": "BLOCK" if problems else "PASS",
        "files_checked": len(rows),
        "missing_installations": missing_installations,
        "baseline": "historico_anp_v2: 13 production files; 1116 missing installations",
        "issues": problems,
        "files": report,
        "note": ("Independent Bronze coverage diagnostic only. Historical Ops "
                 "REVIEW remains unchanged; published Gold is NOT authorized."),
    }


def audit_bronze(spark, contract_run_id: str,
                 *, expected_files: int = 13,
                 expected_missing_installation: int = 1116) -> dict:
    """Spark read-only re-evaluation of *pinned* Bronze production files.

    No CREATE/INSERT/UPDATE/DELETE/MERGE/DROP. Queries only approved tables.
    Caller must still verify that this contract matches published scope hashes.
    """
    from pyspark.sql import functions as F

    if not isinstance(contract_run_id, str) or not contract_run_id.strip():
        raise ValueError("Explicit contract_run_id required")

    contract_table = "workspace.oil_gas_ops.source_file_read_contracts"
    selected = (
        spark.table(contract_table)
        .filter(F.col("contract_run_id") == F.lit(contract_run_id))
        .filter(F.col("dataset").isin("producao_mar", "producao_terra"))
        .select("dataset", "source_file_sha256",
                "nome_arquivo", "registros_esperados")
    )
    contracts = selected.collect()
    if len(contracts) != expected_files:
        raise ValueError(
            f"Pinned contract contains {len(contracts)} production files, "
            f"expected {expected_files}"
        )

    # Prevent a many-to-many join that could hide row-count anomalies.
    contract_ids = [
        (row["dataset"], row["source_file_sha256"]) for row in contracts
    ]
    if len(contract_ids) != len(set(contract_ids)):
        raise ValueError("Repeated production source hash in contract")

    month_pairs = [
        (F.lit(k), F.lit(f"{v:02d}")) for k, v in MONTHS.items()
    ]
    month_map = F.create_map(*[piece for pair in month_pairs for piece in pair])
    frames = []

    for dataset in ("producao_mar", "producao_terra"):
        file_contracts = (
            selected.filter(F.col("dataset") == dataset)
            .drop("dataset")
        )
        source = (
            spark.table(f"workspace.oil_gas_bronze.{dataset}")
            .join(
                file_contracts,
                F.col("_source_file_sha256") == F.col("source_file_sha256"),
                "inner"
            )
            .select(
                F.lit(dataset).alias("dataset"),
                "source_file_sha256", "nome_arquivo", "registros_esperados",
                "ano", "mes_ano", "poco", "campo", "ambiente", "instalacao"
            )
        )
        frames.append(source)

    production = frames[0].unionByName(frames[1])
    period = F.lower(F.trim(F.col("mes_ano")))
    numeric = period.rlike(r"^(0[1-9]|1[0-2])/[0-9]{4}$")
    named = period.rlike(
        r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/[0-9]{4}$"
    )
    month_number = (
        F.when(numeric, F.substring(period, 1, 2))
        .when(named, F.element_at(month_map, F.substring(period, 1, 3)))
    )
    competence = F.to_date(
        F.try_to_timestamp(
            F.concat(F.lit("01/"), month_number, F.lit("/"),
                     F.regexp_extract(period, r"/([0-9]{4})$", 1)),
            F.lit("dd/MM/yyyy"),
        )
    )
    production = (
        production.withColumn("_competencia_v2", competence)
        .withColumn("_ano_v2", F.expr("try_cast(trim(ano) AS INT)"))
    )

    def missing(column: str):
        value = F.trim(F.col(column))
        return value.isNull() | (F.length(value) == 0)

    required_missing = missing("poco") | missing("campo") | missing("ambiente")
    counts = (
        production.groupBy(
            "dataset", "source_file_sha256",
            "nome_arquivo", "registros_esperados"
        )
        .agg(
            F.count("*").alias("registros_encontrados"),
            F.sum(F.when(F.col("_competencia_v2").isNull(), 1)
                  .otherwise(0)).cast("long").alias("competencias_invalidas"),
            F.sum(F.when(
                F.col("_competencia_v2").isNotNull()
                & (
                    F.col("_ano_v2").isNull()
                    | (F.col("_ano_v2") != F.year("_competencia_v2"))
                ), 1).otherwise(0)).cast("long").alias("ano_invalido_ou_divergente"),
            F.sum(F.when(required_missing, 1).otherwise(0))
            .cast("long").alias("identificadores_essenciais_ausentes"),
            F.sum(F.when(missing("instalacao"), 1).otherwise(0))
            .cast("long").alias("instalacoes_ausentes"),
        )
    )

    records = [
        row.asDict(recursive=True)
        for row in counts.collect()
    ]
    report = evaluate_coverage(
        records,
        expected_files=expected_files,
        expected_missing_installation=expected_missing_installation,
    )
    report["contract_run_id"] = contract_run_id
    return report
