import json
import tempfile
import unittest
from pathlib import Path

from scripts.solver_pipeline import (
    aggregate_stats,
    build_parser,
    jev_request_body,
    load_challenge,
    metadata_header,
    parse_model_json,
    parse_jev_response,
    remove_metadata_header,
    validate_model_output,
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
        source = """pub fn solve(value: i32) -> i32 { value }

#[cfg(test)]
mod tests {
    #[test]
    fn example() { assert_eq!(super::solve(1), 1); }
}
"""
        validate_model_output({"rust_source": source}, VALID_CHALLENGE["rust_signature"])
        with self.assertRaisesRegex(RuntimeError, "forbidden"):
            validate_model_output({"rust_source": source.replace("value }", "unsafe { value }", 1)})

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


if __name__ == "__main__":
    unittest.main()
