#!/usr/bin/env python3
"""CLI: extract structured data from a document file or stdin."""

import json
import sys

import click

from .extractor import ExtractionError, extract


@click.command()
@click.argument("file", type=click.Path(exists=True), required=False)
@click.option("--model", envvar="OLLAMA_MODEL", default="qwen2.5:7b", show_default=True)
@click.option("--ollama-url", envvar="OLLAMA_URL", default="http://localhost:11434", show_default=True)
@click.option("--pretty/--compact", default=True, help="Pretty-print JSON output")
def main(file, model, ollama_url, pretty):
    """Extract structured JSON from a document (invoice, act, commercial offer).

    Pass a FILE path or pipe text via stdin.

    Example:
        python -m src.cli invoice.txt
        cat invoice.txt | python -m src.cli
    """
    import os
    os.environ["OLLAMA_MODEL"] = model
    os.environ["OLLAMA_URL"] = ollama_url

    if file:
        text = open(file, encoding="utf-8").read()
    else:
        if sys.stdin.isatty():
            click.echo("Reading from stdin (Ctrl+D to finish)...", err=True)
        text = sys.stdin.read()

    if not text.strip():
        click.echo("Error: empty document", err=True)
        sys.exit(1)

    try:
        result = extract(text)
        indent = 2 if pretty else None
        click.echo(result.model_dump_json(indent=indent))
    except ExtractionError as e:
        click.echo(f"Extraction failed: {e}", err=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
