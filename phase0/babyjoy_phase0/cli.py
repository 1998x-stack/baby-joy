"""CLI to validate private cases, perform gated GPU runs and summarize evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .evaluation import summarize_ratings
from .harness import (
    GateError, MODEL_IDS, check_approval, check_gpu, check_weights,
    check_repo_revision, checked_model_path,
    execute_run, load_json, read_cases, report,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="babyjoy-phase0",
        description="Local Phase 0 benchmarking. Never auto-downloads weights or media."
    )
    subs = p.add_subparsers(dest="command", required=True)
    case = subs.add_parser("validate", help="validate private, authorized manifest")
    case.add_argument("--private-root", type=Path, required=True)
    case.add_argument("--cases", type=Path, required=True)
    pre = subs.add_parser("preflight", help="check GPU/license/weights without running")
    pre.add_argument("--model", choices=MODEL_IDS, required=True)
    pre.add_argument("--config", type=Path, required=True)
    run = subs.add_parser("run", help="perform genuine upstream GPU run")
    run.add_argument("--private-root", type=Path, required=True)
    run.add_argument("--cases", type=Path, required=True)
    run.add_argument("--case-id", required=True)
    run.add_argument("--model", choices=MODEL_IDS, required=True)
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--timeout-seconds", type=int, default=1800)
    rep = subs.add_parser("report", help="summarize local run receipts only")
    rep.add_argument("--output-root", type=Path, required=True)
    rate = subs.add_parser("ratings", help="aggregate blind human review JSONL")
    rate.add_argument("--ratings-file", type=Path, required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = {"status": "VALIDATED", "authorized_cases": len(read_cases(args.private_root, args.cases))}
        elif args.command == "preflight":
            config = load_json(args.config)
            check_repo_revision(checked_model_path(config, "repo_dir"),
                                config.get("model_revision"))
            approval = check_approval(config, args.model)
            weights = check_weights(config)
            gpu = check_gpu()
            result = {
                "status": "READY_TO_ATTEMPT_NOT_VALIDATED", "model_id": args.model,
                "approval": approval["decision"], "weight_files_verified": len(weights),
                "gpu": gpu,
            }
        elif args.command == "run":
            cases = read_cases(args.private_root, args.cases)
            matching = [c for c in cases if c["case_id"] == args.case_id]
            if len(matching) != 1:
                raise GateError("Requested case_id not found")
            result = execute_run(args.model, load_json(args.config), matching[0],
                                 args.output_root, timeout=args.timeout_seconds)
            # Do not print artifact paths, private content or consent references.
            result = {
                "status": result["status"], "run_id": result["run_id"],
                "case_id": result["case_id"], "model_id": result["model_id"],
                "elapsed_seconds": result.get("elapsed_seconds"),
            }
        elif args.command == "report":
            result = report(args.output_root)
        elif args.command == "ratings":
            result = summarize_ratings(args.ratings_file)
        else:
            raise GateError("Unknown command")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (GateError, FileNotFoundError, PermissionError, OSError, ValueError) as exc:
        # Avoid printing arbitrary private paths from system exceptions.
        print(json.dumps({"status": "BLOCKED_OR_FAILED", "error_type": type(exc).__name__,
                          "message": str(exc)[:180] if isinstance(exc, GateError) else
                          "Failed to access or decode local evidence; inspect private environment"},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
