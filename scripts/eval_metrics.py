#!/usr/bin/env python3
"""Layer 1 evaluation: automated metrics across all chapters.

Runs quality_check.py on every translated chapter and aggregates into a
dashboard. Zero model calls.

Usage:
    python eval_metrics.py <translated_dir> [--glossary glossary.json] [--output report.json]
"""

import json
import sys
import argparse
import subprocess
from pathlib import Path


def find_chapter_files(translated_dir: Path) -> list[Path]:
    """Find all chapter files in the translated directory, sorted by name."""
    chapters = sorted(translated_dir.glob("chapter_*.md"))
    if not chapters:
        chapters = sorted(translated_dir.glob("chunk_*.md"))
    return chapters


def run_quality_check(chapter_path: Path, glossary_path: Path | None) -> dict:
    """Run quality_check.py on a chapter and return the parsed report."""
    quality_check_script = Path(__file__).parent / "quality_check.py"
    cmd = [
        sys.executable, str(quality_check_script),
        str(chapter_path),
        "--quiet",
    ]
    if glossary_path and glossary_path.exists():
        cmd.extend(["--glossary", str(glossary_path)])

    # Write to temp JSON to avoid encoding issues
    temp_output = chapter_path.parent / f".temp_{chapter_path.stem}_qc.json"
    cmd.extend(["--json", str(temp_output)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    report = {}

    if temp_output.exists():
        report = json.loads(temp_output.read_text(encoding="utf-8"))
    else:
        report = {"error": result.stderr, "overall": "error"}

    return report


def aggregate_reports(chapter_reports: dict[str, dict]) -> dict:
    """Aggregate per-chapter reports into a dashboard."""
    chapters = sorted(chapter_reports.keys())
    if not chapters:
        return {"error": "No chapters found"}

    # Collect metrics across all chapters
    metrics = {
        "traditional_chars": [],
        "de_flagged": [],
        "bei_count": [],
        "dang_count": [],
        "glossary_consistent": [],
        "sentence_variance": [],
        "he_flagged": [],
        "overall": [],
    }

    for ch in chapters:
        r = chapter_reports[ch]
        metrics["traditional_chars"].append(r.get("traditional_chars", {}).get("count", 0))
        metrics["de_flagged"].append(r.get("de_density", {}).get("flagged_count", 0))
        metrics["bei_count"].append(r.get("bei_passive", {}).get("count", 0))
        metrics["dang_count"].append(r.get("dang_shihou", {}).get("count", 0))
        metrics["glossary_consistent"].append(
            1 if r.get("glossary_drift", {}).get("consistent", True) else 0
        )
        metrics["sentence_variance"].append(
            r.get("sentence_variance", {}).get("score", "unknown")
        )
        metrics["he_flagged"].append(r.get("he_overuse", {}).get("flagged_count", 0))
        metrics["overall"].append(r.get("overall", "error"))

    # Build per-chapter table
    chapter_table = {}
    for i, ch in enumerate(chapters):
        chapter_table[ch] = {
            "traditional_chars": metrics["traditional_chars"][i],
            "de_flagged": metrics["de_flagged"][i],
            "bei_count": metrics["bei_count"][i],
            "dang_count": metrics["dang_count"][i],
            "glossary_ok": bool(metrics["glossary_consistent"][i]),
            "sentence_variance": metrics["sentence_variance"][i],
            "he_flagged": metrics["he_flagged"][i],
            "overall": metrics["overall"][i],
        }

    # Compute averages
    n = len(chapters)
    dashboard = {
        "chapter_count": n,
        "averages": {
            "traditional_chars_per_chapter": sum(metrics["traditional_chars"]) / n,
            "de_flagged_per_chapter": sum(metrics["de_flagged"]) / n,
            "bei_count_per_chapter": sum(metrics["bei_count"]) / n,
            "dang_count_per_chapter": sum(metrics["dang_count"]) / n,
            "glossary_consistency_rate": sum(metrics["glossary_consistent"]) / n,
            "he_flagged_per_chapter": sum(metrics["he_flagged"]) / n,
        },
        "totals": {
            "traditional_chars": sum(metrics["traditional_chars"]),
            "de_flagged": sum(metrics["de_flagged"]),
            "bei_count": sum(metrics["bei_count"]),
            "dang_count": sum(metrics["dang_count"]),
            "he_flagged": sum(metrics["he_flagged"]),
        },
        "clean_chapters": metrics["overall"].count("clean"),
        "needs_review_chapters": metrics["overall"].count("needs_review"),
        "chapters": chapter_table,
    }

    # Overall pass/fail: pass if all chapters are clean
    dashboard["overall_pass"] = dashboard["needs_review_chapters"] == 0

    return dashboard


def main():
    parser = argparse.ArgumentParser(
        description="Layer 1: Automated metrics across all translated chapters"
    )
    parser.add_argument("translated_dir", help="Path to workspace/translated/ directory")
    parser.add_argument("--glossary", help="Path to glossary.json", default=None)
    parser.add_argument("--output", help="Save report to JSON file", default=None)
    args = parser.parse_args()

    translated_dir = Path(args.translated_dir)
    if not translated_dir.exists():
        print(f"Error: directory not found: {args.translated_dir}", file=sys.stderr)
        return 1

    glossary_path = Path(args.glossary) if args.glossary else None
    chapters = find_chapter_files(translated_dir)

    if not chapters:
        print(f"Error: no chapter files found in {args.translated_dir}", file=sys.stderr)
        return 1

    print(f"Running quality checks on {len(chapters)} chapters...")

    chapter_reports = {}
    for ch_path in chapters:
        ch_name = ch_path.name
        print(f"  {ch_name}...", end=" ")
        report = run_quality_check(ch_path, glossary_path)
        chapter_reports[ch_name] = report
        print(report.get("overall", "error"))

    dashboard = aggregate_reports(chapter_reports)

    if args.output:
        Path(args.output).write_text(
            json.dumps(dashboard, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Print summary
    print(f"\n--- Layer 1 Metrics Summary ---")
    print(f"Chapters: {dashboard['chapter_count']}")
    print(f"Clean: {dashboard['clean_chapters']} | Needs review: {dashboard['needs_review_chapters']}")
    print(f"Overall: {'PASS' if dashboard['overall_pass'] else 'FAIL'}")
    print(f"Traditional chars (total): {dashboard['totals']['traditional_chars']}")
    print(f"被-passive (avg/ch): {dashboard['averages']['bei_count_per_chapter']:.1f}")
    print(f"的 density flags (avg/ch): {dashboard['averages']['de_flagged_per_chapter']:.1f}")
    print(f"当...的时候 (avg/ch): {dashboard['averages']['dang_count_per_chapter']:.1f}")

    return 0 if dashboard["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
