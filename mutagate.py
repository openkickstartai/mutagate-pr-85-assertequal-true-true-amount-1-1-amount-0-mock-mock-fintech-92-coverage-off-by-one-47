#!/usr/bin/env python3
"""MutaGate — PR-scoped mutation testing quality gate engine."""
import subprocess, sys, os, json, shutil
import click
from mutators import apply_mutations


def parse_git_diff(branch="main"):
    """Extract changed Python files and line numbers from git diff."""
    try:
        r = subprocess.run(
            ["git", "diff", "--unified=0", branch, "--", "*.py"],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    changes = {}
    current = None
    for line in r.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("@@") and current:
            part = line.split("+")[1].split(" ")[0].split(",")
            start = int(part[0])
            count = int(part[1]) if len(part) > 1 else 1
            changes.setdefault(current, set()).update(range(start, start + count))
    return changes


def test_mutant(project_dir, mutant_code, original_path, test_cmd):
    """Run tests against mutated file. Returns True if mutant is killed."""
    backup = original_path + ".mutagate.bak"
    shutil.copy2(original_path, backup)
    try:
        with open(original_path, "w") as f:
            f.write(mutant_code)
        r = subprocess.run(
            test_cmd, shell=True, capture_output=True, timeout=60, cwd=project_dir
        )
        return r.returncode != 0
    except subprocess.TimeoutExpired:
        return True  # timeout counts as killed
    finally:
        shutil.move(backup, original_path)


def run_mutation_testing(
    target_dir=".", branch="main", threshold=80.0,
    test_cmd="python -m pytest -x -q", files_override=None,
):
    """Main mutation testing pipeline. Returns report dict."""
    changes = files_override if files_override is not None else parse_git_diff(branch)
    if not changes:
        return {"status": "pass", "total": 0, "killed": 0, "survived": 0,
                "kill_rate": 100.0, "threshold": threshold, "survivors": []}
    results = []
    for fpath, lines in changes.items():
        full = os.path.join(target_dir, fpath)
        if not os.path.exists(full):
            continue
        with open(full) as f:
            source = f.read()
        for m in apply_mutations(source, lines):
            killed = test_mutant(target_dir, m["code"], full, test_cmd)
            results.append({**m, "file": fpath, "killed": killed})
    total = len(results)
    killed_n = sum(1 for r in results if r["killed"])
    rate = (killed_n / total * 100) if total else 100.0
    survivors = [r for r in results if not r["killed"]]
    return {"status": "pass" if rate >= threshold else "fail", "total": total,
            "killed": killed_n, "survived": len(survivors),
            "kill_rate": round(rate, 1), "threshold": threshold, "survivors": survivors}


def format_report(report):
    """Format report as human-readable text."""
    icon = "\u2705" if report["status"] == "pass" else "\u274c"
    lines = [
        f"{icon} MutaGate Report: {report['status'].upper()}",
        f"   Mutants: {report['total']} total, {report['killed']} killed, {report['survived']} survived",
        f"   Kill rate: {report['kill_rate']}% (threshold: {report['threshold']}%)",
    ]
    for s in report.get("survivors", []):
        lines.append(f"\n   \u26a0\ufe0f  SURVIVED: {s['file']}:{s['line']} [{s['operator']}]")
        lines.append(f"      Mutation: {s['description']}")
        lines.append(f"      Fix: {s['suggestion']}")
    return "\n".join(lines)


@click.command()
@click.option("--branch", default="main", help="Base branch for diff")
@click.option("--threshold", default=80.0, type=float, help="Min mutation kill rate %")
@click.option("--test-cmd", default="python -m pytest -x -q", help="Test command")
@click.option("--output", type=click.Choice(["text", "json"]), default="text")
@click.option("--dir", "target_dir", default=".", help="Project directory")
def main(branch, threshold, test_cmd, output, target_dir):
    """MutaGate \u2014 PR-scoped mutation testing quality gate."""
    report = run_mutation_testing(target_dir, branch, threshold, test_cmd)
    if output == "json":
        click.echo(json.dumps(report, indent=2))
    else:
        click.echo(format_report(report))
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
