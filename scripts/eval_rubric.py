#!/usr/bin/env python3
"""Layer 2 evaluation: model-as-judge rubric scoring.

Evaluates each translated chapter against a 5-dimension rubric using a
separate model call per chapter. Produces aggregated quality scores.

Usage:
    python eval_rubric.py <translated_dir> <source_dir> [--output report.json]

This script PREPARES the evaluation prompts and writes them for the agent
to process. The actual model evaluation is done by reading the rubric
reference and scoring each chapter. Use with an agent that has access to
the eval-rubric.md reference.
"""

import json
import sys
import argparse
from pathlib import Path


def find_chapter_files(translated_dir: Path) -> list[Path]:
    """Find all translated chapter files, sorted by name."""
    chapters = sorted(translated_dir.glob("chapter_*.md"))
    if not chapters:
        chapters = sorted(translated_dir.glob("chunk_*.md"))
    return chapters


def find_source_chapters(source_dir: Path) -> dict[str, Path]:
    """Map chapter numbers to source files."""
    sources = {}
    for f in sorted(source_dir.glob("chapter_*.txt")):
        # Extract chapter number from filename
        num = f.stem.replace("chapter_", "")
        sources[num] = f
    for f in sorted(source_dir.glob("chunk_*.txt")):
        num = f.stem.replace("chunk_", "")
        sources[num] = f
    return sources


def extract_chapter_num(filename: str) -> str:
    """Extract chapter number from filename."""
    for prefix in ["chapter_", "chunk_"]:
        if prefix in filename:
            return filename.replace(prefix, "").replace(".md", "").replace(".txt", "")
    return filename


def prepare_evaluation_batch(
    translated_dir: Path,
    source_dir: Path,
    rubric_path: Path,
    output_dir: Path,
) -> list[dict]:
    """Prepare a batch of evaluation tasks for the model-as-judge."""
    chapters = find_chapter_files(translated_dir)
    sources = find_source_chapters(source_dir)

    tasks = []
    for ch_path in chapters:
        ch_num = extract_chapter_num(ch_path.name)
        source_path = sources.get(ch_num)

        translated_text = ch_path.read_text(encoding="utf-8")
        source_text = source_path.read_text(encoding="utf-8") if source_path else "[Source not found]"

        task = {
            "chapter": ch_path.name,
            "chapter_num": ch_num,
            "source_file": str(source_path) if source_path else None,
            "translated_file": str(ch_path),
            "evaluation_prompt": f"""Evaluate this Chinese translation using the rubric in {rubric_path}.

=== ORIGINAL ENGLISH ===
{source_text[:3000]}

=== CHINESE TRANSLATION ===
{translated_text[:3000]}

Score on 5 dimensions (1-5 each) with justifications. Output as JSON.""",
        }
        tasks.append(task)

    # Write tasks to batch file
    batch_file = output_dir / "eval_batch.json"
    batch_file.write_text(
        json.dumps({"tasks": tasks, "rubric_path": str(rubric_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return tasks


def aggregate_scores(scores_dir: Path) -> dict:
    """Aggregate per-chapter rubric scores into a dashboard."""
    score_files = sorted(scores_dir.glob("chapter_*_scores.json"))
    if not score_files:
        score_files = sorted(scores_dir.glob("chunk_*_scores.json"))

    if not score_files:
        return {"error": "No score files found"}

    all_scores = []
    dimensions = ["naturalness", "register_match", "dialogue_quality", "literary_quality", "terminology"]
    dim_sums = {d: 0.0 for d in dimensions}

    for sf in score_files:
        data = json.loads(sf.read_text(encoding="utf-8"))
        all_scores.append(data)
        for d in dimensions:
            dim_sums[d] += data.get("scores", {}).get(d, {}).get("score", 0)

    n = len(all_scores)
    overalls = [s.get("overall", 0) for s in all_scores]

    return {
        "chapter_count": n,
        "dimension_averages": {d: round(dim_sums[d] / n, 2) for d in dimensions},
        "overall_average": round(sum(overalls) / n, 2) if overalls else 0,
        "per_chapter": {s.get("chapter", f"chapter_{i}"): s for i, s in enumerate(all_scores)},
        "overall_pass": all(o >= 3.0 for o in overalls) if overalls else False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Layer 2: Model-as-judge rubric evaluation"
    )
    parser.add_argument("translated_dir", help="Path to workspace/translated/")
    parser.add_argument("source_dir", help="Path to workspace/extracted/chapters/")
    parser.add_argument("--rubric", help="Path to eval-rubric.md", default=None)
    parser.add_argument("--output", help="Save aggregate report to JSON", default=None)
    parser.add_argument("--prepare-only", action="store_true",
                        help="Only prepare evaluation batch, don't aggregate")
    parser.add_argument("--aggregate", help="Aggregate scores from directory", default=None)
    args = parser.parse_args()

    # Find rubric path
    if args.rubric:
        rubric_path = Path(args.rubric)
    else:
        rubric_path = Path(__file__).parent.parent / "references" / "eval-rubric.md"

    # Aggregation mode
    if args.aggregate:
        scores_dir = Path(args.aggregate)
        dashboard = aggregate_scores(scores_dir)
        if args.output:
            Path(args.output).write_text(
                json.dumps(dashboard, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(f"Layer 2 Aggregate Score: {dashboard.get('overall_average', 'N/A')}")
        print(f"Pass: {'PASS' if dashboard.get('overall_pass') else 'FAIL'}")
        return 0

    # Prepare mode
    translated_dir = Path(args.translated_dir)
    source_dir = Path(args.source_dir)
    eval_dir = translated_dir.parent / "eval_results"
    eval_dir.mkdir(exist_ok=True)

    tasks = prepare_evaluation_batch(translated_dir, source_dir, rubric_path, eval_dir)

    print(f"Prepared {len(tasks)} evaluation tasks in {eval_dir}")
    print(f"Rubric: {rubric_path}")
    print(f"\nTo complete Layer 2 evaluation, run an agent for each task in eval_batch.json")
    print(f"Then use --aggregate {eval_dir} to compute the dashboard.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
