#!/usr/bin/env python3
"""Layer 3 evaluation: blind A/B comparison.

Compares two translation versions of the same source text. Presents them
blind (randomized labels) to the model, which picks the better one. Runs
multiple times with position swapped to control for position bias.

Usage:
    python eval_ab.py <source_file> <translation_a.md> <translation_b.md> [--runs 3]

This script generates the comparison prompts. The actual model evaluation
is done by an agent reading the prompts and returning verdicts.
"""

import json
import sys
import argparse
import random
from pathlib import Path


def load_file(filepath: str | Path) -> str:
    """Load file content."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    return path.read_text(encoding="utf-8")


def prepare_comparison(
    source_text: str,
    translation_a: str,
    translation_b: str,
    swap: bool = False,
) -> dict:
    """Prepare a single blind comparison. If swap=True, A and B labels are reversed."""
    if swap:
        label_a = "B"  # Actually translation_a but labeled B
        label_b = "A"  # Actually translation_b but labeled A
        text_a = translation_b
        text_b = translation_a
    else:
        label_a = "A"
        label_b = "B"
        text_a = translation_a
        text_b = translation_b

    return {
        "source_excerpt": source_text[:2000],
        "translation_a": text_a[:2000],
        "translation_b": text_b[:2000],
        "mapping": {
            "A": "translation_a" if not swap else "translation_b",
            "B": "translation_b" if not swap else "translation_a",
        },
        "swapped": swap,
        "prompt": f"""You are judging the quality of two Chinese translations of the same English text. Compare them BLINDLY — you don't know which system produced which.

=== ORIGINAL ENGLISH ===
{source_text[:2000]}

=== TRANSLATION A ===
{text_a[:2000]}

=== TRANSLATION B ===
{text_b[:2000]}

Which translation is better overall? Consider:
1. Naturalness — which reads more like native Chinese?
2. Literary quality — which better preserves the author's style and voice?
3. Accuracy — which is more faithful to the original meaning?

Answer with JSON:
{{
  "winner": "A" or "B",
  "confidence": "high" or "medium" or "low",
  "reasoning": "Brief explanation of your choice, referencing specific examples."
}}""",
    }


def evaluate_verdicts(verdicts: list[dict], label_a: str, label_b: str) -> dict:
    """Aggregate verdicts across multiple runs."""
    wins_a = 0
    wins_b = 0
    ties = 0

    for v in verdicts:
        winner = v.get("winner", "").strip()
        # Map from blind label back to actual translation
        mapping = v.get("mapping", {})
        actual_winner = mapping.get(winner, winner)

        if actual_winner == "translation_a":
            wins_a += 1
        elif actual_winner == "translation_b":
            wins_b += 1
        else:
            ties += 1

    total = len(verdicts)

    # Determine result
    if wins_a > wins_b:
        result = f"Translation A ({label_a}) preferred ({wins_a}/{total} wins)"
    elif wins_b > wins_a:
        result = f"Translation B ({label_b}) preferred ({wins_b}/{total} wins)"
    else:
        result = f"No clear winner (A: {wins_a}, B: {wins_b}, ties: {ties})"

    return {
        "runs": total,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "ties": ties,
        "label_a": label_a,
        "label_b": label_b,
        "result": result,
        "verdicts": verdicts,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Layer 3: Blind A/B comparison of translations"
    )
    parser.add_argument("source", help="Path to English source text")
    parser.add_argument("translation_a", help="Path to first translation")
    parser.add_argument("translation_b", help="Path to second translation")
    parser.add_argument("--runs", type=int, default=3, help="Number of comparison runs (default: 3)")
    parser.add_argument("--output", help="Save comparison batch to JSON", default=None)
    parser.add_argument("--aggregate", help="Aggregate verdicts from JSON file", default=None)
    parser.add_argument("--label-a", default="v1", help="Label for translation A (default: v1)")
    parser.add_argument("--label-b", default="v2", help="Label for translation B (default: v2)")
    args = parser.parse_args()

    # Aggregation mode
    if args.aggregate:
        verdict_data = json.loads(Path(args.aggregate).read_text(encoding="utf-8"))
        result = evaluate_verdicts(
            verdict_data.get("verdicts", []),
            verdict_data.get("label_a", "v1"),
            verdict_data.get("label_b", "v2"),
        )
        print(result["result"])
        print(f"Wins: {result['label_a']}={result['wins_a']}, "
              f"{result['label_b']}={result['wins_b']}, ties={result['ties']}")
        return 0 if result["wins_b"] > result["wins_a"] else (1 if result["wins_a"] > result["wins_b"] else 2)

    # Prepare mode
    source_text = load_file(args.source)
    trans_a = load_file(args.translation_a)
    trans_b = load_file(args.translation_b)

    comparisons = []
    # Generate runs with alternating swaps to control for position bias
    for run in range(args.runs):
        swap = (run % 2 == 1)  # Odd runs are swapped
        comp = prepare_comparison(source_text, trans_a, trans_b, swap=swap)
        comp["run"] = run + 1
        comparisons.append(comp)

    batch = {
        "label_a": args.label_a,
        "label_b": args.label_b,
        "source": args.source,
        "translation_a": args.translation_a,
        "translation_b": args.translation_b,
        "comparisons": comparisons,
    }

    if args.output:
        Path(args.output).write_text(
            json.dumps(batch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Comparison batch saved to {args.output}")
    else:
        print(json.dumps(batch, ensure_ascii=False, indent=2))

    print(f"\nPrepared {len(comparisons)} blind comparisons ({args.runs} runs, alternating swaps).")
    print("To complete Layer 3, have an agent evaluate each comparison's prompt and record verdicts.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
