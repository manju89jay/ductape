import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="ductape",
        description="Universal Schema Adapter Generator",
    )
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="Generate adapter code")
    gen_parser.add_argument("--config", required=True, help="Path to config.yaml")
    gen_parser.add_argument("--output", required=True, help="Output directory")

    verify_parser = subparsers.add_parser("verify", help="Verify against golden files")
    verify_parser.add_argument("--config", required=True, help="Path to config.yaml")
    verify_parser.add_argument("--expected", required=True, help="Expected output directory")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "generate":
        from ductape.codegen import run_generate
        run_generate(args.config, args.output)
    elif args.command == "verify":
        from ductape.codegen import run_verify
        run_verify(args.config, args.expected)
