"""Command-line entry point for offline analysis and synthetic examples."""
import argparse
import json
from pathlib import Path

from . import __version__


def main():
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='reproduce':
        from .reproduce import main as reproduce_main
        sys.argv.pop(1)
        return reproduce_main()
    if len(sys.argv)>1 and sys.argv[1]=='ui':
        from .ui import main as ui_main
        sys.argv.pop(1)
        return ui_main()
    parser = argparse.ArgumentParser(prog="patent-diffusion")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    compare = sub.add_parser('compare', help='Compare two named country/technology groups using an explicit JSON configuration')
    for name in ('families','edges','config','output'):
        compare.add_argument('--'+name,type=Path,required=True)
    compare.add_argument('--profile',choices=['portable_v1','legacy_v0_2'],default='portable_v1')
    compare.add_argument('--include-data',action='store_true',help='Include sensitive family/event tables in this local output')
    prep=sub.add_parser('prepare',help='Prepare standard tables from local PATSTAT exports')
    prep.add_argument('--source',choices=['patstat-local'],required=True)
    prep.add_argument('--manifest',type=Path,required=True)
    prep.add_argument('--output',type=Path,required=True)
    sub.add_parser('reproduce',help='Full study execution from both reviewer bundles; use reproduce --help')
    sub.add_parser('ui',help='Open a local-only comparison interface; use ui --help')
    demo = sub.add_parser("demo", help="Generate 400 synthetic pairs and run all three windows in smoke mode")
    demo.add_argument("--output", type=Path, required=True, help="New directory for synthetic inputs and results")
    validate = sub.add_parser("validate", help="Check preprocessed tables and classification gates without fitting models")
    validate.add_argument('--profile',choices=['paper_v4_20261012','portable_v1'],default='paper_v4_20261012')
    validate.add_argument('--config',type=Path)
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
        if args.command == 'prepare':
            from .prepare import run as prepare_run
            print(json.dumps(prepare_run(args.manifest,args.output),ensure_ascii=False))
            return
        if args.command == 'compare':
            if args.profile == 'legacy_v0_2':
                from .compare import run as compare_run
                compare_run(args.families,args.edges,args.config,args.output)
                print(json.dumps({'status':'COMPUTED','profile':'legacy_v0_2','warning':'Historical compatibility; not portable_v1 inference'}))
            else:
                from .portable import run as compare_run
                result=compare_run(args.families,args.edges,args.config,args.output,args.include_data)
                print(json.dumps({'status':result['status'],'output':str(args.output.resolve())}))
                if result['status']=='FAILED': parser.exit(2,'Portable analysis failed; inspect validation_report.json\n')
            return
        from .pipeline import run, validate_inputs
        if args.command == "validate":
            if args.profile == 'portable_v1':
                if not args.config: raise ValueError('portable_v1 validation requires --config')
                from .portable import validate as portable_validate
                print(json.dumps(portable_validate(args.families,args.edges,args.config),ensure_ascii=False,allow_nan=False))
                return
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
