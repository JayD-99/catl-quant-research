"""Download official CATL filings and verify them against recorded SHA-256 hashes."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd
import requests


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(root: Path, overwrite: bool = False) -> None:
    manifest = pd.read_csv(root / "data" / "manual" / "filing_sources.csv")
    destination = root / "data" / "external" / "filings"
    destination.mkdir(parents=True, exist_ok=True)
    for row in manifest.itertuples(index=False):
        output = destination / f"{row.key}.pdf"
        if overwrite or not output.exists():
            response = requests.get(row.url, timeout=120)
            response.raise_for_status()
            output.write_bytes(response.content)
        actual = sha256(output)
        if actual != row.sha256:
            raise ValueError(f"Checksum mismatch for {row.key}: {actual} != {row.sha256}")
        print(f"verified {row.key}: {actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    download(args.root.resolve(), args.overwrite)


if __name__ == "__main__":
    main()
