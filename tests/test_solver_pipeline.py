import json
import tempfile
import unittest
from pathlib import Path

from scripts.solver_pipeline import (
    aggregate_stats,
    build_parser,
    load_challenge,
    metadata_header,
    parse_model_json,
    remove_metadata_header,
    validate_model_output,
)


VALID_CHALLENGE = {
    "id": "sample-problem",
    "title": "Sample problem",
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
