#!/usr/bin/env python3
"""Automated prompt tuning loop for the book-translator skill.

Orchestrates an iterative process:
1. Translate test corpus with current translation-style.md
2. Run all 3 evaluation layers
3. Feed results to prompt doctor for diagnosis
4. Apply prompt edits, re-evaluate, keep if ALL layers improve
5. Repeat until convergence or max iterations

This script MANAGES the loop — the actual translation and prompt-doctor
work is done by agents (model calls). This script tracks state, applies
changes, enforces the "improve all 3 layers" rule, and maintains history.

Usage:
    python tune_prompt.py <skill_root> [--max-iterations 5] [--resume]

The skill root is the book-translator/ directory containing SKILL.md and
references/translation-style.md.
"""

import json
import sys
import argparse
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    """Load a JSON file, return empty dict if missing."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json(path: Path, data: dict) -> None:
    """Save data as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_check(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def init_tuning_state(output_dir: Path, skill_root: Path) -> dict:
    """Initialize or load tuning state."""
    state_file = output_dir / "tuning_state.json"

    if state_file.exists():
        return load_json(state_file)

    # Fresh state
    prompt_file = skill_root / "references" / "translation-style.md"
    original_prompt = prompt_file.read_text(encoding="utf-8")

    state = {
        "skill_root": str(skill_root),
        "prompt_file": str(prompt_file),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "iterations": [],
        "best_scores": None,
        "best_prompt_version": 0,
        "current_version": 0,
        "original_prompt_hash": hash(original_prompt),
        "converged": False,
        "convergence_reason": None,
    }

    save_json(state_file, state)
    return state


def save_prompt_version(output_dir: Path, version: int, prompt_text: str) -> Path:
    """Save a versioned copy of the prompt."""
    path = output_dir / "prompt_versions" / f"translation-style.v{version}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prompt_text, encoding="utf-8")
    return path


def record_iteration(
    state: dict,
    output_dir: Path,
    iteration: int,
    layer1_scores: dict,
    layer2_scores: dict,
    layer3_scores: dict,
    prompt_edits: list[dict],
    kept: bool,
    notes: str,
) -> None:
    """Record an iteration's results."""
    iteration_record = {
        "iteration": iteration,
        "version": state["current_version"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "layer1": layer1_scores,
        "layer2": layer2_scores,
        "layer3": layer3_scores,
        "edits_applied": prompt_edits,
        "kept": kept,
        "notes": notes,
    }

    state["iterations"].append(iteration_record)

    # Update best scores
    current_scores = {
        "layer1_pass": layer1_scores.get("overall_pass", False),
        "layer2_avg": layer2_scores.get("overall_average", 0),
        "layer3_wins": layer3_scores.get("wins_b", 0) if layer3_scores else 0,
    }

    if state["best_scores"] is None:
        state["best_scores"] = current_scores
        state["best_prompt_version"] = state["current_version"]
    else:
        # Check if ALL layers improved
        prev = state["best_scores"]
        improved = (
            (current_scores["layer1_pass"] >= prev["layer1_pass"]) and
            (current_scores["layer2_avg"] >= prev["layer2_avg"]) and
            (current_scores.get("layer3_wins", 0) >= prev.get("layer3_wins", 0))
        )
        if improved and current_scores != prev:
            state["best_scores"] = current_scores
            state["best_prompt_version"] = state["current_version"]

    save_json(output_dir / "tuning_state.json", state)


# ---------------------------------------------------------------------------
# Score comparison
# ---------------------------------------------------------------------------

def all_layers_improved(
    prev_scores: dict | None,
    current_scores: dict,
) -> bool:
    """Check if ALL 3 layers improved compared to previous iteration."""
    if prev_scores is None:
        return True  # First iteration always "improves"

    layer1_prev = prev_scores.get("overall_pass", False)
    layer1_cur = current_scores.get("overall_pass", False)

    layer2_prev = prev_scores.get("overall_average", 0)
    layer2_cur = current_scores.get("overall_average", 0)

    # Layer 3: higher wins for the new version (v2 = "B")
    layer3_prev = prev_scores.get("wins_b", 0)
    layer3_cur = current_scores.get("wins_b", 0)

    # Layer 1: boolean — must not regress
    if layer1_prev and not layer1_cur:
        return False

    # Layer 2: numeric — must not decrease
    if layer2_cur < layer2_prev:
        return False

    # Layer 3: numeric — must not decrease
    if layer3_cur < layer3_prev:
        return False

    # At least one layer must improve
    return (
        (not layer1_prev and layer1_cur) or
        (layer2_cur > layer2_prev) or
        (layer3_cur > layer3_prev)
    )


def check_convergence(state: dict, output_dir: Path) -> tuple[bool, str]:
    """Check if tuning has converged (no improvement in recent iterations)."""
    iterations = state["iterations"]

    if len(iterations) < 3:
        return False, ""

    # Check last 3 iterations
    recent = iterations[-3:]
    if all(not it["kept"] for it in recent):
        return True, "No improvement in 3 consecutive iterations"

    # Check if all metrics are above threshold
    best = state["best_scores"]
    if best:
        l1_pass = best.get("layer1_pass", False)
        l2_avg = best.get("layer2_avg", 0)
        if l1_pass and l2_avg >= 4.0:
            return True, "All metrics above quality threshold"

    return False, ""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def prepare_iteration_prompt(
    state: dict,
    output_dir: Path,
    iteration: int,
    corpus_dir: Path,
) -> str:
    """Generate the prompt for running one tuning iteration.

    This prompt is meant to be executed by an agent. It covers:
    1. Translate all corpus samples
    2. Run all 3 eval layers
    3. Run prompt doctor
    """
    prompt_file = Path(state["prompt_file"])
    skill_root = Path(state["skill_root"])

    return f"""You are running iteration {iteration} of the book-translator prompt tuning loop.

## Current State
- Prompt file: {prompt_file}
- Version: {state['current_version']}
- Skill root: {skill_root}
- Corpus: {corpus_dir}
- Output dir: {output_dir}

## Step 1: Translate the corpus
For each sample in {corpus_dir}:
  Read the sample English text
  Read {skill_root}/references/translation-style.md
  Translate into Simplified Chinese following the guidelines
  Save to {output_dir}/iter_{iteration}/translated/<sample_name>.md

## Step 2: Run Layer 1 — Automated Metrics
For each translated sample:
  Run: python {skill_root}/scripts/quality_check.py {output_dir}/iter_{iteration}/translated/<sample_name>.md
  Collect all reports

## Step 3: Run Layer 2 — Model-as-Judge Rubric
For each translated sample:
  Read {skill_root}/references/eval-rubric.md
  Read the original English and the Chinese translation
  Score on 5 dimensions (1-5 each) with justifications
  Save scores to {output_dir}/iter_{iteration}/rubric/<sample_name>_scores.json

## Step 4: Run Layer 3 — Blind A/B Comparison
Compare current version translations against the previous best version:
  Previous best: {output_dir}/prompt_versions/translation-style.v{state['best_prompt_version']}.md
  For each sample where both versions exist:
    Present translations blind, pick the better one
    Record verdicts

## Step 5: Prompt Doctor
Read the current {prompt_file}
Read ALL evaluation results from Steps 2-4
Identify the 3 lowest-scoring passages and why they scored poorly

Propose specific edits to {prompt_file} that would address the gaps.
Output as a JSON array of edits:
```json
[
  {{
    "section": "Section name in translation-style.md",
    "old_text": "exact text to replace",
    "new_text": "replacement text",
    "rationale": "Why this change, tied to which eval scores"
  }}
]
```

Save proposed edits to {output_dir}/iter_{iteration}/proposed_edits.json

## Step 6: Apply and Re-evaluate
Apply the proposed edits to a COPY of the prompt (do NOT modify the original yet).
Re-run Steps 1-4 with the edited prompt.
Save new scores to {output_dir}/iter_{iteration}/new_scores.json

Save ALL results to {output_dir}/iter_{iteration}/results.json:
```json
{{
  "iteration": {iteration},
  "old_scores": {{ ... }},
  "new_scores": {{ ... }},
  "edits": [ ... ],
  "improved": true/false
}}
```
"""


def apply_edits_and_keep(
    state: dict,
    output_dir: Path,
    iteration: int,
) -> bool:
    """Check if iteration results show improvement and apply edits if so."""
    iter_dir = output_dir / f"iter_{iteration}"
    results_file = iter_dir / "results.json"

    if not results_file.exists():
        print(f"  No results file found at {results_file}")
        print(f"  The agent should save results to this path.")
        return False

    results = load_json(results_file)
    improved = results.get("improved", False)
    edits = results.get("edits", [])

    if improved:
        # Apply edits to the real prompt file
        prompt_file = Path(state["prompt_file"])
        prompt_text = prompt_file.read_text(encoding="utf-8")

        for edit in edits:
            old = edit["old_text"]
            new = edit["new_text"]
            if old in prompt_text:
                prompt_text = prompt_text.replace(old, new, 1)
            else:
                # Edit may have been applied already or text differs by whitespace
                safe_old = old[:50].encode("ascii", errors="replace").decode("ascii")
                print(f"  NOTE: Edit already applied or not found: {safe_old}...")

        # Save new version
        state["current_version"] += 1
        new_version = state["current_version"]
        save_prompt_version(output_dir, new_version, prompt_text)

        # Update the actual prompt file
        prompt_file.write_text(prompt_text, encoding="utf-8")

        # Record
        new_scores = results.get("new_scores", {})
        record_iteration(
            state, output_dir, iteration,
            new_scores.get("layer1", {}),
            new_scores.get("layer2", {}),
            new_scores.get("layer3", {}),
            edits,
            kept=True,
            notes=f"Applied {len(edits)} edits, prompt v{new_version}",
        )

        print(f"  IMPROVED — applied {len(edits)} edits → prompt v{new_version}")
        return True
    else:
        # Revert — don't apply edits
        old_scores = results.get("old_scores", {})
        record_iteration(
            state, output_dir, iteration,
            old_scores.get("layer1", {}),
            old_scores.get("layer2", {}),
            old_scores.get("layer3", {}),
            edits,
            kept=False,
            notes="Reverted — no improvement across all 3 layers",
        )

        print(f"  REVERTED — edits did not improve all 3 layers")
        return False


def generate_final_report(state: dict, output_dir: Path) -> str:
    """Generate a final report of the tuning run."""
    iterations = state["iterations"]
    kept_count = sum(1 for it in iterations if it["kept"])

    lines = [
        "# Prompt Tuning Report",
        "",
        f"**Started**: {state['started_at']}",
        f"**Skill**: book-translator",
        f"**Prompt file**: {state['prompt_file']}",
        f"**Iterations**: {len(iterations)}",
        f"**Improvements kept**: {kept_count}",
        f"**Final version**: v{state['current_version']}",
        f"**Converged**: {state['converged']}",
    ]

    if state["convergence_reason"]:
        lines.append(f"**Reason**: {state['convergence_reason']}")

    if state["best_scores"]:
        best = state["best_scores"]
        lines.append("")
        lines.append("## Best Scores Achieved")
        lines.append(f"- Layer 1 (metrics pass): {best.get('layer1_pass', 'N/A')}")
        lines.append(f"- Layer 2 (rubric avg): {best.get('layer2_avg', 'N/A')}")
        lines.append(f"- Layer 3 (A/B wins): {best.get('layer3_wins', 'N/A')}")
        lines.append(f"- Version: v{state['best_prompt_version']}")

    lines.append("")
    lines.append("## Iteration History")
    lines.append("")
    lines.append("| Iter | Version | L1 Pass | L2 Avg | L3 Wins | Kept |")
    lines.append("|------|---------|---------|--------|---------|------|")
    for it in iterations:
        l1 = it["layer1"].get("overall_pass", "?") if it["layer1"] else "?"
        l2 = it["layer2"].get("overall_average", "?") if it["layer2"] else "?"
        l3 = it["layer3"].get("wins_b", "?") if it["layer3"] else "?"
        kept = "YES" if it["kept"] else "no"
        lines.append(f"| {it['iteration']} | v{it['version']} | {l1} | {l2} | {l3} | {kept} |")

    report = "\n".join(lines)
    report_path = output_dir / "tuning_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Automated prompt tuning loop for book-translator skill"
    )
    parser.add_argument("skill_root", help="Path to book-translator/ skill directory")
    parser.add_argument("--max-iterations", type=int, default=5,
                        help="Maximum tuning iterations (default: 5)")
    parser.add_argument("--output", default=None,
                        help="Output directory for tuning state (default: <skill_root>/eval-results/)")
    parser.add_argument("--corpus", default=None,
                        help="Test corpus directory (default: <skill_root>/test-corpus/)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from previous tuning state")
    parser.add_argument("--apply", default=None,
                        help="Apply results from an iteration directory")
    parser.add_argument("--report", action="store_true",
                        help="Generate final report from existing state")
    args = parser.parse_args()

    skill_root = Path(args.skill_root).resolve()
    if not skill_root.exists():
        print(f"Error: skill root not found: {skill_root}", file=sys.stderr)
        return 1

    output_dir = Path(args.output) if args.output else skill_root / "eval-results"
    output_dir.mkdir(parents=True, exist_ok=True)

    corpus_dir = Path(args.corpus) if args.corpus else skill_root / "test-corpus"
    if not corpus_dir.exists():
        print(f"Error: test corpus not found: {corpus_dir}", file=sys.stderr)
        return 1

    prompt_file = skill_root / "references" / "translation-style.md"
    if not prompt_file.exists():
        print(f"Error: prompt file not found: {prompt_file}", file=sys.stderr)
        return 1

    # Initialize state
    state = init_tuning_state(output_dir, skill_root)

    # Report-only mode
    if args.report:
        report = generate_final_report(state, output_dir)
        print(report)
        return 0

    # Apply mode: apply results from a specific iteration
    if args.apply:
        iter_dir = Path(args.apply)
        iter_num = int(iter_dir.name.replace("iter_", ""))
        apply_edits_and_keep(state, output_dir, iter_num)
        return 0

    # Fresh or resume
    if args.resume and state["iterations"]:
        last_iter = state["iterations"][-1]["iteration"]
        print(f"Resuming from iteration {last_iter + 1}")
        start_iter = last_iter + 1
    else:
        # Save baseline (v0) of the prompt
        original = prompt_file.read_text(encoding="utf-8")
        save_prompt_version(output_dir, 0, original)
        start_iter = 1
        print(f"Starting tuning loop. Corpus: {corpus_dir}")
        print(f"Output: {output_dir}")
        print(f"Max iterations: {args.max_iterations}")

    # Main loop
    for iteration in range(start_iter, start_iter + args.max_iterations):
        print(f"\n{'='*60}")
        print(f"Iteration {iteration}/{start_iter + args.max_iterations - 1}")
        print(f"{'='*60}")

        # Check convergence
        converged, reason = check_convergence(state, output_dir)
        if converged:
            state["converged"] = True
            state["convergence_reason"] = reason
            save_json(output_dir / "tuning_state.json", state)
            print(f"Converged: {reason}")
            break

        # Create iteration directory
        iter_dir = output_dir / f"iter_{iteration}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        (iter_dir / "translated").mkdir(exist_ok=True)
        (iter_dir / "rubric").mkdir(exist_ok=True)

        # Generate the iteration prompt
        iter_prompt = prepare_iteration_prompt(state, output_dir, iteration, corpus_dir)
        prompt_path = iter_dir / "agent_prompt.md"
        prompt_path.write_text(iter_prompt, encoding="utf-8")

        print(f"Agent prompt written to: {prompt_path}")
        print(f"")
        print(f"To run this iteration, pass the contents of {prompt_path} to an agent.")
        print(f"After the agent completes, run:")
        print(f"  python tune_prompt.py {skill_root} --apply {iter_dir}")
        print(f"")
        print(f"Or continue manually — the agent prompt contains all instructions.")

        # If running non-interactively, we'd invoke the agent here.
        # In practice, the user or a wrapper script invokes the agent
        # and then calls --apply with the iteration directory.
        break  # Stop after generating prompt — user runs agent separately

    # Generate report
    report = generate_final_report(state, output_dir)
    print(f"\n{report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
