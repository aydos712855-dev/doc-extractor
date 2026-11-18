#!/usr/bin/env python3
"""
Mini-eval: runs all test documents through the extractor and prints a report.

Usage:
    python eval.py                   # real Ollama
    python eval.py --mock            # mock LLM (returns expected JSON verbatim)
    make eval
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Field comparison helpers
# ---------------------------------------------------------------------------

SCALAR_FIELDS = [
    "doc_type",
    "supplier_name",
    "supplier_bin",
    "doc_number",
    "doc_date",
    "currency",
    "total_amount",
    "vat_amount",
]


def _norm(v: Any) -> Any:
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def _fields_match(predicted: Any, expected: Any) -> bool:
    if expected is None and predicted is None:
        return True
    if expected is None or predicted is None:
        return False
    return _norm(predicted) == _norm(expected)


def compare(predicted: dict, expected: dict) -> dict[str, str]:
    """
    Returns per-field verdict: 'correct', 'hallucination', 'miss', 'wrong'.
    hallucination = predicted non-null, expected null
    miss          = predicted null, expected non-null
    """
    result: dict[str, str] = {}
    for field in SCALAR_FIELDS:
        p = predicted.get(field)
        e = expected.get(field)
        if e is None and p is None:
            result[field] = "correct"
        elif e is None and p is not None:
            result[field] = "hallucination"
        elif e is not None and p is None:
            result[field] = "miss"
        elif _fields_match(p, e):
            result[field] = "correct"
        else:
            result[field] = "wrong"
    return result


# ---------------------------------------------------------------------------
# Mock LLM: return expected JSON so the pipeline is exercised without Ollama
# ---------------------------------------------------------------------------

def _install_mock(expected_dir: Path) -> None:
    """Monkey-patch extractor._call_ollama to return expected JSON."""
    import src.extractor as ext_mod

    _doc_lookup: dict[str, str] = {}
    for exp_path in sorted(expected_dir.glob("*.json")):
        doc_id = exp_path.stem  # e.g. doc01
        _doc_lookup[doc_id] = exp_path.read_text(encoding="utf-8")

    _current_doc_id: list[Optional[str]] = [None]

    original_extract = ext_mod.extract

    def mock_extract(document_text: str) -> Any:
        doc_id = _current_doc_id[0]
        if doc_id and doc_id in _doc_lookup:
            raw = _doc_lookup[doc_id]
            from src.schema import DocumentExtraction
            return DocumentExtraction.model_validate_json(raw)
        return original_extract(document_text)

    ext_mod.extract = mock_extract  # type: ignore[assignment]
    return _current_doc_id  # caller sets [0] before each call


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate document extractor")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use expected JSON as LLM response (no Ollama needed)",
    )
    parser.add_argument(
        "--docs-dir",
        default="tests/documents",
        help="Directory with .txt test documents",
    )
    parser.add_argument(
        "--expected-dir",
        default="tests/expected",
        help="Directory with ground-truth .json files",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    expected_dir = Path(args.expected_dir)

    doc_files = sorted(docs_dir.glob("*.txt"))
    if not doc_files:
        print(f"No .txt files in {docs_dir}", file=sys.stderr)
        sys.exit(1)

    current_doc_id: Optional[list] = None
    if args.mock:
        current_doc_id = _install_mock(expected_dir)
        print("MOCK MODE -- LLM responses are taken from expected JSON\n")

    from src.extractor import ExtractionError, extract

    # Per-field counters
    field_correct: dict[str, int] = {f: 0 for f in SCALAR_FIELDS}
    field_halluc: dict[str, int] = {f: 0 for f in SCALAR_FIELDS}
    field_miss: dict[str, int] = {f: 0 for f in SCALAR_FIELDS}
    field_wrong: dict[str, int] = {f: 0 for f in SCALAR_FIELDS}
    total_docs = 0
    failed_docs: list[str] = []

    print(f"{'Doc':<10} {'Result':<10} {'Details'}")
    print("-" * 70)

    for doc_path in doc_files:
        doc_id = doc_path.stem
        exp_path = expected_dir / f"{doc_id}.json"
        if not exp_path.exists():
            print(f"{doc_id:<10} SKIP       (no expected JSON)")
            continue

        expected = json.loads(exp_path.read_text(encoding="utf-8"))
        document_text = doc_path.read_text(encoding="utf-8")

        if current_doc_id is not None:
            current_doc_id[0] = doc_id

        try:
            result = extract(document_text)
            predicted = json.loads(result.model_dump_json())
        except ExtractionError as e:
            print(f"{doc_id:<10} ERROR      {e}")
            failed_docs.append(doc_id)
            continue

        verdicts = compare(predicted, expected)
        total_docs += 1
        issues = [f"{f}={v}" for f, v in verdicts.items() if v != "correct"]
        status = "OK" if not issues else "ISSUES"
        print(f"{doc_id:<10} {status:<10} {', '.join(issues) if issues else 'all correct'}")

        for field, verdict in verdicts.items():
            if verdict == "correct":
                field_correct[field] += 1
            elif verdict == "hallucination":
                field_halluc[field] += 1
            elif verdict == "miss":
                field_miss[field] += 1
            else:
                field_wrong[field] += 1

    if total_docs == 0:
        print("\nNo documents evaluated.")
        return

    print("\n" + "=" * 70)
    print(f"{'FIELD':<20} {'ACCURACY':>8} {'CORRECT':>8} {'WRONG':>8} {'HALLU':>8} {'MISS':>8}")
    print("-" * 70)

    total_halluc = 0
    total_miss = 0

    for field in SCALAR_FIELDS:
        c = field_correct[field]
        h = field_halluc[field]
        m = field_miss[field]
        w = field_wrong[field]
        total = c + h + m + w
        acc = c / total * 100 if total else 0.0
        total_halluc += h
        total_miss += m
        print(f"{field:<20} {acc:>7.1f}% {c:>8} {w:>8} {h:>8} {m:>8}")

    overall_correct = sum(field_correct.values())
    overall_total = sum(
        field_correct[f] + field_halluc[f] + field_miss[f] + field_wrong[f]
        for f in SCALAR_FIELDS
    )
    overall_acc = overall_correct / overall_total * 100 if overall_total else 0.0

    print("-" * 70)
    print(f"{'OVERALL':<20} {overall_acc:>7.1f}%")
    print()
    print(f"Documents evaluated : {total_docs}")
    print(f"Documents failed    : {len(failed_docs)} {failed_docs if failed_docs else ''}")
    print(f"Total hallucinations: {total_halluc}  (field filled, expected null)")
    print(f"Total misses        : {total_miss}  (field null, expected non-null)")


if __name__ == "__main__":
    main()
