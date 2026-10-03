import json
import tempfile
import unittest
from pathlib import Path

from scripts.solver_pipeline import (
    aggregate_stats,
    build_parser,
    check_models_command,
    clean_html,
    extract_rust_signature,
    hydrate_challenge,
    jev_request_body,
    load_challenge,
    load_challenge_metadata,
    metadata_header,
    module_declaration,
    module_name,
    parse_leetcode_content,
    parse_model_json,
    parse_jev_response,
    prompt_for,
    remove_metadata_header,
    solution_file_name,
    validate_model_output,
    write_solution,
)


VALID_CHALLENGE = {
    "id": "sample-problem",
    "title": "Sample problem",
    "leetcode_difficulty": "medium",
    "challenge_date": "2026-09-29",
    "source_type": "maintainer",
    "source_url": "https://example.invalid/sample-problem",
    "rust_supported": True,
    "rust_support_checked_at": "2026-09-29",
    "description": "Return the input unchanged.",
    "constraints": ["The input is valid."],
    "rust_signature": "pub fn solve(value: i32) -> i32",
    "examples": [{"input": "1", "output": "1"}],
}


class SolverPipelineTests(unittest.TestCase):
    def test_load_challenge_accepts_authorized_rust_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "sample-problem.json"
            path.write_text(json.dumps(VALID_CHALLENGE), encoding="utf-8")
            self.assertEqual(load_challenge(path)["id"], "sample-problem")

    def test_load_challenge_rejects_unconfirmed_rust_support(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "sample-problem.json"
            challenge = {**VALID_CHALLENGE, "rust_supported": False}
            path.write_text(json.dumps(challenge), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Rust support"):
                load_challenge(path)

    def test_load_challenge_rejects_unknown_leetcode_difficulty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "sample-problem.json"
            challenge = {**VALID_CHALLENGE, "leetcode_difficulty": "unknown"}
            path.write_text(json.dumps(challenge), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "leetcode_difficulty"):
                load_challenge(path)

    def test_metadata_scan_does_not_read_body_until_hydration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            challenges = root / "challenges"
            challenges.mkdir()
            manifest = {
                key: VALID_CHALLENGE[key]
                for key in (
                    "id",
                    "title",
                    "leetcode_difficulty",
                    "challenge_date",
                    "source_type",
                    "source_url",
                    "rust_supported",
                    "rust_support_checked_at",
                    "rust_signature",
                )
            }
            manifest["body_source"] = {
                "type": "local-json",
                "path": "challenges/bodies/sample-problem.json",
            }
            manifest_path = challenges / "sample-problem.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            self.assertEqual(load_challenge_metadata(manifest_path)["id"], "sample-problem")
            self.assertEqual(
                load_challenge(manifest_path, root=root, hydrate=False)["id"],
                "sample-problem",
            )
            with self.assertRaisesRegex(RuntimeError, "missing JSON file"):
                hydrate_challenge(root, manifest)

    def test_hydration_loads_only_the_selected_local_body(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            body_path = root / "challenges" / "bodies" / "sample-problem.json"
            body_path.parent.mkdir(parents=True)
            body_path.write_text(
                json.dumps(
                    {
                        "description": VALID_CHALLENGE["description"],
                        "constraints": VALID_CHALLENGE["constraints"],
                        "examples": VALID_CHALLENGE["examples"],
                    }
                ),
                encoding="utf-8",
            )
            manifest = {
                key: VALID_CHALLENGE[key]
                for key in (
                    "id",
                    "title",
                    "leetcode_difficulty",
                    "challenge_date",
                    "source_type",
                    "source_url",
                    "rust_supported",
                    "rust_support_checked_at",
                    "rust_signature",
                )
            }
            manifest["body_source"] = {
                "type": "local-json",
                "path": "challenges/bodies/sample-problem.json",
            }
            hydrated = hydrate_challenge(root, manifest)
            self.assertEqual(hydrated["description"], VALID_CHALLENGE["description"])
            self.assertEqual(hydrated["rust_signature"], VALID_CHALLENGE["rust_signature"])

    def test_jev_request_uses_a_typed_score_question(self) -> None:
        request = jev_request_body(VALID_CHALLENGE, {"model": "jev-latest", "base_url": "https://api.typesafe.ai"})
        question = request["questions"]["algorithmic_difficulty"]
        self.assertEqual(request["model"], "jev-latest")
        self.assertEqual(question["type"], "score")
        self.assertEqual(len(question["criteria"]), 5)

    def test_parse_jev_response_preserves_score_distribution(self) -> None:
        response = parse_jev_response(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "algorithmic_difficulty": {
                        "type": "score",
                        "score": 2.4,
                        "confidence": 0.61,
                        "legend": {str(index): f"level {index}" for index in range(5)},
                        "probabilities": {"0": 0.02, "1": 0.08, "2": 0.50, "3": 0.35, "4": 0.05},
                    }
                },
                "usage": {"input_tokens": 120, "output_tokens": 18},
            }
        )
        self.assertEqual(response["model"], "jev-1.13.0")
        self.assertEqual(response["dominant_level"], "moderate")
        self.assertEqual(response["usage"]["input_tokens"], 120)
        self.assertAlmostEqual(response["probabilities"]["2"], 0.50)

    def test_parse_model_json_removes_optional_fences(self) -> None:
        self.assertEqual(parse_model_json('```json\n{"rust_source":"x"}\n```')["rust_source"], "x")

    def test_validate_model_output_requires_tests_and_signature(self) -> None:
        source = """pub struct Solution;

impl Solution {
    pub fn solve(value: i32) -> i32 { value }
}

#[cfg(test)]
mod tests {
    use super::Solution;

    #[test]
    fn example() { assert_eq!(Solution::solve(1), 1); }
}
"""
        validate_model_output({"rust_source": source}, VALID_CHALLENGE["rust_signature"])
        with self.assertRaisesRegex(RuntimeError, "forbidden"):
            validate_model_output({"rust_source": source.replace("value }", "unsafe { value }", 1)})
        standalone = source.replace(
            "impl Solution {\n    pub fn solve(value: i32) -> i32 { value }\n}",
            "pub fn solve(value: i32) -> i32 { value }",
        )
        with self.assertRaisesRegex(RuntimeError, "inside impl Solution"):
            validate_model_output({"rust_source": standalone}, VALID_CHALLENGE["rust_signature"])

    def test_prompt_requires_leetcode_solution_impl(self) -> None:
        prompt = prompt_for(VALID_CHALLENGE)
        self.assertIn("inside `impl Solution`", prompt)
        self.assertIn("pub struct Solution;", prompt)
        self.assertIn("`Solution::method`", prompt)

    def test_metadata_round_trip(self) -> None:
        run = {
            "model": "gemini-2.5-flash",
            "effort": "medium",
            "thinking_budget": 4096,
            "temperature": 0.2,
            "attempts": [{"input_tokens": 10, "output_tokens": 20, "thinking_tokens": 3, "total_tokens": 33}],
            "started_epoch": 0,
        }
        header = metadata_header("sample-problem", run)
        body = "pub fn solve(value: i32) -> i32 { value }\n"
        self.assertEqual(remove_metadata_header(header + body), body)
        self.assertEqual(aggregate_stats(run)["total_tokens"], 33)

    def test_parser_contains_required_commands(self) -> None:
        parser = build_parser()
        self.assertIsNotNone(parser)

    def test_module_and_file_naming(self) -> None:
        self.assertEqual(solution_file_name("001-two-sum"), "001_two_sum")
        self.assertEqual(module_name("001-two-sum"), "_001_two_sum")
        self.assertEqual(
            module_declaration("001-two-sum"),
            '#[path = "001_two_sum.rs"]\npub mod _001_two_sum;',
        )

        self.assertEqual(solution_file_name("valid-parentheses"), "valid_parentheses")
        self.assertEqual(module_name("valid-parentheses"), "valid_parentheses")
        self.assertEqual(module_declaration("valid-parentheses"), "pub mod valid_parentheses;")

    def test_write_solution_registers_module_with_custom_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            challenge = {
                **VALID_CHALLENGE,
                "id": "001-two-sum",
                "rust_signature": "pub fn solve(nums: Vec<i32>, target: i32) -> Vec<i32>",
            }
            source = """pub struct Solution;

impl Solution {
    pub fn solve(nums: Vec<i32>, target: i32) -> Vec<i32> { vec![] }
}

#[cfg(test)]
mod tests {
    use super::Solution;

    #[test]
    fn test_example() { assert_eq!(Solution::solve(vec![], 0), vec![]); }
}
"""
            run = {
                "model": "gemini-3.8-flash",
                "effort": "medium",
                "thinking_budget": 0,
                "temperature": 1.0,
                "attempts": [{"input_tokens": 10, "output_tokens": 20, "thinking_tokens": 0, "total_tokens": 30}],
                "started_epoch": 0,
            }
            destination = write_solution(root, challenge, run, source)
            self.assertEqual(destination.name, "001_two_sum.rs")
            self.assertTrue(destination.is_file())
            mod_file = root / "src" / "problems" / "mod.rs"
            self.assertTrue(mod_file.is_file())
            content = mod_file.read_text(encoding="utf-8")
            self.assertIn('#[path = "001_two_sum.rs"]\npub mod _001_two_sum;', content)

    def test_clean_html_and_parse_leetcode_content(self) -> None:
        raw_html = """
        <p>Given an array of integers <code>nums</code>.</p>
        <p>&nbsp;</p>
        <p><strong class="example">Example 1:</strong></p>
        <pre>
        <strong>Input:</strong> nums = [1,2,3]
        <strong>Output:</strong> 6
        <strong>Explanation:</strong> 1 + 2 + 3 = 6
        </pre>
        <p><strong>Constraints:</strong></p>
        <ul>
            <li><code>1 &lt;= nums.length &lt;= 100</code></li>
        </ul>
        """
        desc, constraints, examples = parse_leetcode_content(raw_html)
        self.assertIn("Given an array of integers nums.", desc)
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0], "1 <= nums.length <= 100")
        self.assertEqual(len(examples), 1)
        self.assertIn("nums = [1,2,3]", examples[0]["input"])
        self.assertEqual(examples[0]["output"], "6")

    def test_extract_rust_signature(self) -> None:
        snippet = """
impl Solution {
    pub fn add_two_numbers(l1: Option<Box<ListNode>>, l2: Option<Box<ListNode>>) -> Option<Box<ListNode>> {
        
    }
}
"""
        sig = extract_rust_signature(snippet)
        self.assertEqual(
            sig,
            "pub fn add_two_numbers(l1: Option<Box<ListNode>>, l2: Option<Box<ListNode>>) -> Option<Box<ListNode>>",
        )

    def test_check_models_missing_key(self) -> None:
        import argparse
        from unittest.mock import patch
        with patch.dict("os.environ", {}, clear=True):
            code = check_models_command(argparse.Namespace(api_key=None))
            self.assertEqual(code, 1)

    def test_check_models_success(self) -> None:
        import argparse
        import io
        from unittest.mock import MagicMock, patch
        mock_data = json.dumps({
            "models": [
                {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.7-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
            ]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_data
        mock_resp.__enter__.return_value = mock_resp

        with patch("scripts.solver_pipeline.urlopen", return_value=mock_resp):
            code = check_models_command(argparse.Namespace(api_key="test-key"))
            self.assertEqual(code, 0)

    def test_check_models_missing_model_returns_warning(self) -> None:
        import argparse
        from unittest.mock import MagicMock, patch
        mock_data = json.dumps({
            "models": [
                {"name": "models/gemini-3.7-flash", "supportedGenerationMethods": ["generateContent"]},
            ]
        }).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_data
        mock_resp.__enter__.return_value = mock_resp

        with patch("scripts.solver_pipeline.urlopen", return_value=mock_resp):
            code = check_models_command(argparse.Namespace(api_key="test-key"))
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
