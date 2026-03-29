import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="ductape",
        description="Universal Schema Adapter Generator",
    )
    parser.add_argument("--no-color", action="store_true", default=False,
                        help="Disable coloured terminal output (NFR-05)")
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="Generate adapter code")
    gen_parser.add_argument("--config", required=True, help="Path to config.yaml")
    gen_parser.add_argument("--output", required=True, help="Output directory")

    verify_parser = subparsers.add_parser("verify", help="Verify against golden files")
    verify_parser.add_argument("--config", required=True, help="Path to config.yaml")
    verify_parser.add_argument("--expected", required=True, help="Expected output directory")

    extract_parser = subparsers.add_parser("extract-deps",
                                           help="Extract headers from package manager packages (FR-10)")
    extract_parser.add_argument("--config", required=True, help="Path to config.yaml")
    extract_parser.add_argument("--output", required=True, help="Output directory for extracted headers")

    diff_parser = subparsers.add_parser("diff",
                                        help="Diff report between version snapshots (FR-12)")
    diff_parser.add_argument("--previous", required=True,
                             help="Path to previous version_overview.json")
    diff_parser.add_argument("--current", required=True,
                             help="Path to current version_overview.json")

    args = parser.parse_args()

    use_color = not args.no_color

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "generate":
        from ductape.codegen import run_generate
        run_generate(args.config, args.output, use_color=use_color)
    elif args.command == "verify":
        from ductape.codegen import run_verify
        run_verify(args.config, args.expected, use_color=use_color)
    elif args.command == "extract-deps":
        from ductape.dependency_extractor import extract_from_config
        from ductape.config import load_config
        config = load_config(args.config)
        results = extract_from_config(config, args.output)
        total = sum(len(v) for v in results.values())
        print(f"Extracted {total} header file(s) to {args.output}")
    elif args.command == "diff":
        from ductape.version_diff import generate_diff_report, format_diff_report
        diff = generate_diff_report(args.previous, args.current)
        print(format_diff_report(diff))
