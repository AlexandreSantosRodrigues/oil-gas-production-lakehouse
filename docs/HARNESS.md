# Read-only Agentic Quality Harness (v0.1)

This is an additive and conservative **diagnostic layer**, not a replacement
for the existing Databricks notebooks or their Ops checks.

## Implemented versus not implemented

**Implemented**
- Explicitly pinned, read-only extraction from four existing Ops Delta tables.
- Fail-closed, standard-library quality gate. A non-PASS result blocks approval.
- Secondary invariant checks, including exact Decimal reconciliation and Gold
  fact-ID counts, even when the source row says PASS.
- Deterministic, read-only investigation suggestions by failure category.
- Optional, explicitly enabled Chat Completions-compatible LLM commentary
  (text only; no tool execution or write permissions).
- Content-hashed execution receipts, exit codes and synthetic offline tests.
- GitHub Actions quality checks with no Databricks credentials.

**Not implemented / not asserted**
- No automated re-run of the old notebooks.
- No evidence of clean-workspace reproducibility or concurrent-ingestion safety.
- No automatic repair, commit, PR creation, multi-agent orchestration or publishing.
- No cloud scheduler, ongoing monitoring, durable remote queue or background agent.
- No claim that historic check IDs refer to the same source snapshot until
  their lineage is validated. Contract ID agreement is checked for coverage and
  Silver; the other checks must be manually traced to the intended source files.
- No live Databricks verification from GitHub Actions. They use synthetic data.

## Architecture

    Databricks Ops (four read-only tables)
         |  explicit run IDs, allowlisted columns, bounded collect
         v
    harness.databricks.export_snapshot
         |  JSON schema_version=1, scope/contract references
         v
    harness.core.evaluate       <-- deterministic source of truth
         | PASS / BLOCK / INVALID
         +-----------------> run receipt (source SHA-256 + evidence)
         |
         v
    harness.agent.prepare_investigation
         | read-only hypotheses and next checks
         +--> optional LLM review (--enable-llm; advice only)
         |
         v
    HUMAN REVIEW of any proposed changes

The gate never runs SQL written by an LLM. The Databricks extractor uses only
hard-coded table and column allowlists; filters are pinned IDs.

## Offline quick start (no Databricks account needed)

Use Python 3.10+ (the CI uses Python 3.12) from the repository root:

    python -m unittest discover -s tests -v
    python -m harness.cli \
      --snapshot examples/ops_snapshot_synthetic.json \
      --output-dir receipts

The example is **entirely synthetic**. Do not interpret PASS from this
example as proof of the production Lakehouse's health.

Exit codes:
- 0 = PASS: complete evidence met all checks.
- 1 = BLOCK: a check reported REVIEW, ERROR, FAIL or a violated invariant.
- 2 = INVALID or I/O failure: insufficient, contradictory, malformed or missing
  evidence. An INVALID result never authorizes publication.

Receipts include input file SHA-256, run IDs, counts, issue categories, and
read-only next steps. Add receipts/ to your local .git/info/exclude or avoid
committing real Ops snapshot/receipt files containing operational metadata.
The CI explicitly writes receipts to /tmp.

## Live Databricks usage (manual, read-only)

1. Open this GitHub repository in a Databricks Git folder so that
   "from harness..." imports resolve. Use a notebook in that folder (or
   explicitly add the cloned repo root to Python's sys.path).
2. Read the relevant existing Ops tables, using SELECT/GROUP BY, and identify
   the **four check-run IDs and one contract-run ID belonging to the intended
   source content**. Do not simply select MAX(timestamp) independently.
   Existing notebooks sometimes select the latest contract, which need not
   match another table's latest run.
3. Run the following code in a Python notebook cell after replacing every ID
   with actual reviewed values:

    from harness.databricks import export_snapshot
    from harness.core import evaluate
    from harness.agent import prepare_investigation
    import json

    run_ids = {
        "structure": "<check_run_id from source_file_structure_checks>",
        "coverage": "<check_run_id from production_file_coverage_checks>",
        "silver": "<recon_run_id from silver_v2_measure_reconciliation>",
        "published": "<check_run_id from published_scope_checks>",
    }
    snapshot = export_snapshot(
        spark,
        run_ids=run_ids,
        contract_run_id="<reviewed contract_run_id>",
        scope_id="historico_anp_v2",
    )
    gate = evaluate(snapshot)
    print(json.dumps(gate, indent=2, ensure_ascii=False))
    print(json.dumps(prepare_investigation(gate), indent=2,
                     ensure_ascii=False))
    if gate["status"] != "PASS":
        raise RuntimeError("Publication blocked by the quality harness")

4. If desired, save the snapshot to a protected Workspace path for offline
   CLI analysis. Inspect the allowlisted columns before transferring any
   operational metadata to an external environment.

Example discovery queries (read-only):

    SELECT check_run_id, count(*) AS n
    FROM workspace.oil_gas_ops.source_file_structure_checks
    GROUP BY check_run_id;

    SELECT contract_run_id, check_run_id, count(*) AS n
    FROM workspace.oil_gas_ops.production_file_coverage_checks
    GROUP BY contract_run_id, check_run_id;

    SELECT contract_run_id, recon_run_id, count(*) AS n
    FROM workspace.oil_gas_ops.silver_v2_measure_reconciliation
    GROUP BY contract_run_id, recon_run_id;

    SELECT escopo_id, check_run_id, count(*) AS n
    FROM workspace.oil_gas_ops.published_scope_checks
    GROUP BY escopo_id, check_run_id;

For production acceptance, compare source hashes and the lineage of selected
structure/check batches with the intended published analytical scope. The four
run IDs represent checks performed at different stages, not one universal ID.
Completeness requires additional run-level/source coverage assertions beyond
the current compact diagnostic gate.

## Optional AI reviewer (off by default)

The default quality gate and investigator do **not** require any API key.
The opt-in LLM only receives up to 30 curated failure signals and suggestions,
not the underlying production data. It cannot call tools, execute SQL, or
change a PASS/BLOCK decision.

Example using a local OpenAI-compatible service configured to serve a model:

    python -m harness.cli \
      --snapshot path/to/reviewed_snapshot.json \
      --output-dir receipts \
      --enable-llm \
      --llm-endpoint http://127.0.0.1:11434/v1/chat/completions \
      --model <installed-local-model>

For an external provider, use HTTPS and optionally set HARNESS_API_KEY in the
execution environment. Review your organization's data sharing rules before
using this option. Never place API tokens in the repository. No remote model
access, billing or availability is promised.

If LLM review fails, the receipt still records the deterministic result and
adds llm_error; missing AI commentary does not authorize publication.

## Next technical milestones

1. Centralize configuration and remove exploratory/notebook-order dependencies.
2. Execute notebooks end-to-end in a clean Databricks workspace with reviewed
   source hash/contract inputs; then test repeatability and idempotency.
3. Add cross-stage coverage assertions for the exact 16 content hashes in the
   historical scope; avoid hardcoding totals for future scopes.
4. Implement staged dry-run publishing and independently verified rollback
   before giving any agent higher privileges.
5. Add real fault injection and a fixed evaluation suite for LLM diagnoses.
6. Only then consider bounded repair proposals on isolated Git branches and
   human-reviewed deployment workflows.


## Historical coverage REVIEW: corrected read-only diagnostic

The October 2026 historical audit recorded 15 structure checks (14 PASS, one
REVIEW) and 13 production coverage checks (10 PASS, three REVIEW). All
169 Silver measure reconciliations and three published-scope checks returned
PASS. The remaining REVIEW outcomes are **not** silently converted to PASS.

The older coverage notebook only parsed numeric \`MM/YYYY\` months and treated
installation as a required key. Silver v2 parses Portuguese abbreviated
months such as \`out/2025\`, and intentionally permits NULL installation.
The historic documented counts are 657 missing installations in 2026Q1
and 459 in 2026Q2, totaling 1,116. The older 2025Q4 review reported
30,123 invalid months due to the strict parser.

Read-only, independent coverage recheck (execute inside Databricks Git folder,
with workspace tables and a Python notebook):

```python
from harness.coverage_v2 import audit_bronze
import json

report = audit_bronze(
    spark,
    contract_run_id="aea99472-c0f7-4fb7-b8b6-e2336f272fc4",
    expected_files=13,
    expected_missing_installation=1116,
)
print(json.dumps(report, indent=2, ensure_ascii=False))
```

This only reads the existing `source_file_read_contracts` and corresponding
Bronze tables. It never changes old Ops records, Silver, Gold or source files.
A PASS establishes only a **corrected Bronze coverage check for the pinned
historical contract**; it does NOT override the structural layout REVIEW
or the main quality harness's BLOCK and does NOT prove the four runs share
fully verified end-to-end lineage.

A proper follow-up should separately verify that the 2025Q4 structure review
represents only a *permutation of normalized header names*, that the read
contract's alignment is correct, and that the contract's file hashes equal
the intended published analytical scope. Those checks are deliberately not
automatically waived.

