"""Run: python -m harness.cli --snapshot examples/ops_snapshot_synthetic.json"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from harness.agent import optional_llm_review, prepare_investigation
from harness.core import InvalidSnapshot, evaluate


def run(snapshot_path: Path, output_dir: Path, *, enable_llm: bool = False,
        llm_endpoint: str = "", model: str = "") -> tuple[int, Path]:
    payload = snapshot_path.read_bytes()
    run_id = uuid.uuid4().hex
    receipt = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": hashlib.sha256(payload).hexdigest(),
        "input_file": snapshot_path.name,
        "git_sha": os.getenv("GITHUB_SHA", ""),
        "harness_version": "0.1.0",
    }
    try:
        snapshot = json.loads(payload)
        gate = evaluate(snapshot)
        receipt.update(gate)
        receipt["investigation"] = prepare_investigation(gate)
        code = 0 if gate["status"] == "PASS" else 1
        if enable_llm:
            try:
                receipt["advisory_llm_review"] = optional_llm_review(
                    receipt["investigation"], llm_endpoint, model
                )
            except Exception as exc:
                # Never convert an LLM failure to PASS or mask a quality BLOCK.
                receipt["llm_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    except (ValueError, TypeError, KeyError) as exc:
        receipt["status"] = "INVALID"
        receipt["error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
        code = 2

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.json"
    # Exclusive creation avoids overwriting previous receipts.
    with path.open("x", encoding="utf-8") as target:
        json.dump(receipt, target, indent=2, ensure_ascii=False)
        target.write("\n")
    return code, path


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only ANP Ops quality gate")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("receipts"))
    parser.add_argument("--enable-llm", action="store_true",
                        help="Explicit opt-in; advice only, no tool execution")
    parser.add_argument("--llm-endpoint", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    if args.enable_llm and (not args.llm_endpoint or not args.model):
        parser.error("--enable-llm requires --llm-endpoint and --model")
    try:
        code, path = run(args.snapshot, args.output_dir,
                         enable_llm=args.enable_llm,
                         llm_endpoint=args.llm_endpoint, model=args.model)
    except (OSError, UnicodeError) as exc:
        print(f"Cannot read snapshot/write receipt: {exc}", file=sys.stderr)
        return 2
    print(f"Gate exit code: {code}; receipt: {path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
