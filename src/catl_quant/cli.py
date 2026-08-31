from __future__ import annotations

import argparse

from .config import load_config
from .analysis import run_analysis
from .build import build_datasets
from .data_sources import download_all
from .reporting import generate_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CATL quantitative research pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ["download", "build", "analyze", "report"]:
        child = subparsers.add_parser(command)
        child.add_argument("--config", default="config/research.yaml")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    if args.command == "download":
        download_all(config)
    elif args.command == "build":
        build_datasets(config)
    elif args.command == "analyze":
        run_analysis(config)
    elif args.command == "report":
        generate_report(config)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
