"""Exercise the actual workflow shell with a fake GitHub CLI, without merging PRs."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
PASSING_CHECKS = [
    {"name": "SonarQube", "workflow": "Build", "bucket": "pass"},
    {"name": "analyze", "workflow": "SonarCloud component analysis", "bucket": "pass"},
]
FAKE_GH = """
import json
import os
from pathlib import Path
import sys

state = json.loads(Path(os.environ["MERGE_TEST_STATE"]).read_text())
args = sys.argv[1:]
with Path(os.environ["MERGE_TEST_LOG"]).open("a") as log:
    log.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "list"]:
    print(json.dumps(state["prs"]))
    sys.exit(0)
pr = next(pr for pr in state["prs"] if str(pr["number"]) == args[2])
if args[:2] == ["pr", "checks"]:
    print(json.dumps(pr["checks"]))
    sys.exit(pr.get("checks_exit", 0))
if args[:2] == ["pr", "view"]:
    if "--jq" in args:
        print(pr.get("review", ""))
    else:
        print(json.dumps({
            "baseRefName": pr.get("base", "main"),
            "isDraft": pr["isDraft"],
            "reviewDecision": pr.get("review", ""),
        }))
    sys.exit(0)
if args[:2] == ["pr", "merge"]:
    expected_sha = args[args.index("--match-head-commit") + 1]
    if expected_sha != pr.get("current_sha", pr["headRefOid"]):
        sys.exit(1)
    sys.exit(pr.get("merge_exit", 0))
sys.exit(1)
"""


def step_script(filename: str, name: str) -> str:
    """Extract a literal shell block so tests execute the workflow's own code."""
    lines = (WORKFLOWS / filename).read_text().splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == f"- name: {name}")
    block = next(index for index in range(start, len(lines)) if lines[index].strip() == "run: |")
    indent = len(lines[block]) - len(lines[block].lstrip())
    end = block + 1
    while end < len(lines) and (not lines[end].strip() or len(lines[end]) - len(lines[end].lstrip()) > indent):
        end += 1
    return textwrap.dedent("\n".join(lines[block + 1:end]))


def pull_request(number: int = 1, **overrides) -> dict:
    return {
        "number": number,
        "headRefOid": f"{number:040x}",
        "headRefName": "release-branch",
        "isDraft": False,
        "title": "feat: automate delivery",
        "checks": PASSING_CHECKS,
        **overrides,
    }


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "workflow tests require bash and jq")
class ReleaseAutomationTests(unittest.TestCase):
    def run_workflow_step(self, prs: list[dict], *, release: bool = False, publish: bool = False) -> tuple:
        filename, name = (
            ("release.yml", "Resolve the current release PR, including unchanged retries")
            if release else
            ("auto-merge.yml", "Merge PRs whose current commits passed all checks")
        )
        if publish:
            filename, name = "release.yml", "Squash-merge the validated release commit"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state.json").write_text(json.dumps({"prs": prs}))
            (root / "output").touch()
            (root / "gh").write_text(f"#!{sys.executable}\n" + FAKE_GH)
            (root / "gh").chmod(0o700)
            env = {
                **os.environ,
                "PATH": f"{root}{os.pathsep}{os.environ['PATH']}",
                "RUNNER_TEMP": str(root),
                "GITHUB_OUTPUT": str(root / "output"),
                "MERGE_TEST_STATE": str(root / "state.json"),
                "MERGE_TEST_LOG": str(root / "commands"),
                "GH_TOKEN": "test-only",
                "PR_NUMBER": "1",
                "PR_SHA": f"{1:040x}",
            }
            result = subprocess.run(
                ["bash", "-c", step_script(filename, name)], env=env,
                capture_output=True, text=True, check=False,
            )
            commands = [json.loads(line) for line in (root / "commands").read_text().splitlines()]
            return result, commands, (root / "output").read_text()

    def assert_no_merge(self, **overrides) -> None:
        result, commands, output = self.run_workflow_step([pull_request(**overrides)])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(command[:2] == ["pr", "merge"] for command in commands))
        self.assertEqual(output, "")

    def test_passing_pr_merges_only_the_inspected_head(self) -> None:
        result, commands, output = self.run_workflow_step([pull_request()])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(["pr", "merge", "1", "--squash", "--match-head-commit", f"{1:040x}"], commands)
        self.assertEqual(output, "merged=true\n")

    def test_conventional_scopes_and_breaking_changes_merge(self) -> None:
        for title in ("ci(release): automate releases", "feat!: automate releases", "fix(release)!: automate releases"):
            with self.subTest(title=title):
                result, _, output = self.run_workflow_step([pull_request(title=title)])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output, "merged=true\n")

    def test_missing_or_wrong_workflow_checks_do_not_merge(self) -> None:
        for checks in ([], PASSING_CHECKS[:1], [
            {**check, "workflow": "Unrelated workflow"} for check in PASSING_CHECKS
        ]):
            with self.subTest(checks=checks):
                self.assert_no_merge(checks=checks)

    def test_any_nonpassing_check_blocks_merge(self) -> None:
        for bucket in ("fail", "pending", "cancel", "skipping"):
            with self.subTest(bucket=bucket):
                self.assert_no_merge(checks=[
                    *PASSING_CHECKS, {"name": "Additional check", "workflow": "Other", "bucket": bucket},
                ])

    def test_cli_check_failure_blocks_merge(self) -> None:
        self.assert_no_merge(checks_exit=8)

    def test_drafts_and_nonconventional_titles_do_not_merge(self) -> None:
        self.assert_no_merge(isDraft=True)
        self.assert_no_merge(title="Release automation")

    def test_blocked_reviews_do_not_merge(self) -> None:
        for review in ("CHANGES_REQUESTED", "REVIEW_REQUIRED"):
            with self.subTest(review=review):
                self.assert_no_merge(review=review)

    def test_head_changes_cannot_publish_a_merge(self) -> None:
        result, _, output = self.run_workflow_step([pull_request(current_sha="new-head")])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "")

    def test_unmergeable_pr_does_not_prevent_other_merges(self) -> None:
        result, commands, output = self.run_workflow_step([
            pull_request(merge_exit=1), pull_request(number=2),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(command[:2] == ["pr", "merge"] for command in commands), 2)
        self.assertEqual(output, "merged=true\n")

    def test_no_release_pr_produces_no_validation_inputs(self) -> None:
        result, _, output = self.run_workflow_step([], release=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "")

    def test_unchanged_release_pr_is_resolved_for_retry(self) -> None:
        result, _, output = self.run_workflow_step([pull_request()], release=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, f"number=1\nsha={1:040x}\nbranch=release-branch\n")

    def test_ambiguous_or_draft_release_pr_is_rejected(self) -> None:
        for prs in ([pull_request(isDraft=True)], [pull_request(), pull_request(number=2)]):
            with self.subTest(prs=prs):
                result, _, output = self.run_workflow_step(prs, release=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")

    def test_release_merge_requires_unchanged_head_and_unblocked_review(self) -> None:
        result, commands, _ = self.run_workflow_step([pull_request()], publish=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(["pr", "merge", "1", "--squash", "--match-head-commit", f"{1:040x}"], commands)
        for overrides in (
            {"isDraft": True}, {"base": "other"}, {"review": "CHANGES_REQUESTED"},
            {"review": "REVIEW_REQUIRED"}, {"current_sha": "updated-head"},
        ):
            with self.subTest(overrides=overrides):
                result, _, _ = self.run_workflow_step([pull_request(**overrides)], publish=True)
                self.assertNotEqual(result.returncode, 0)
