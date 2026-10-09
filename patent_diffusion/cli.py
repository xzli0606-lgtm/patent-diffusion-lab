"""Command-line entry point for offline analysis and synthetic examples."""
import argparse
import json
from pathlib import Path

from . import __version__


def main():
    parser = argparse.ArgumentParser(prog="patent-diffusion")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate 400 synthetic pairs and run all three windows in smoke mode")
    demo.add_argument("--output", type=Path, required=True, help="New directory for synthetic inputs and results")
    validate = sub.add_parser("validate", help="Check preprocessed tables and classification gates without fitting models")
    analyze = sub.add_parser("analyze", help="Analyze preprocessed family and citation-edge Parquet files")
    for command in (validate, analyze):
        command.add_argument("--families", type=Path, required=True)
        command.add_argument("--edges", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--pairs", type=int, default=10000)
    analyze.add_argument("--seed", type=int, default=20261009, help="Pair-sampling seed; frozen reference seeds are recorded separately")
    analyze.add_argument("--replicates", type=int, default=2000)
    analyze.add_argument("--bootstrap", type=int, default=2000)
    analyze.add_argument("--smoke", action="store_true", help="At most 50 simulations and 200 bootstrap draws; diagnostics only")
    args = parser.parse_args()
    try:
        from .pipeline import run, validate_inputs
        if args.command == "validate":
            print(json.dumps(validate_inputs(args.families, args.edges), indent=2))
            return
        if args.command == "demo":
            from .demo import write_demo_inputs
            if args.output.exists():
                raise FileExistsError(f"refusing to overwrite {args.output}")
            fp, ep = write_demo_inputs(args.output / "inputs")
            output = args.output / "results"
            result = run(fp, ep, output, n_pairs=400, smoke=True, synthetic=True)
        else:
            output = args.output
            result = run(args.families, args.edges, output, args.pairs, args.seed,
                         args.replicates, args.bootstrap, args.smoke)
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        parser.exit(2, f"Analysis stopped: {exc}\n")
    print(json.dumps({"status": result["status"], "dataset_kind": result["dataset_kind"],
        "output": str(output.resolve()), "windows": {
            h: {"sampled_pairs": v["sampled_pairs"], "reference_status": v["opportunity_reference"]["status"]}
            for h, v in result["windows"].items()}}, ensure_ascii=False, indent=2))
    if result["status"] == "INCOMPLETE_REFERENCE":
        parser.exit(2, "Reference support or precision is incomplete; inspect run.json.\n")


if __name__ == "__main__":
    main()
