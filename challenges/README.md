# Authorized challenge inbox

The solver reads one JSON file per challenge from this directory. A maintainer or
an authorized integration must supply each file; this repository does not crawl or
scrape LeetCode.

Each accepted file must contain:

```json
{
  "id": "stable-kebab-case-id",
  "title": "Problem title",
  "leetcode_difficulty": "medium",
  "challenge_date": "2026-09-29",
  "source_type": "maintainer",
  "source_url": "https://example.invalid/authorized-source",
  "rust_supported": true,
  "rust_support_checked_at": "2026-09-29",
  "description": "An authorized description of the problem.",
  "constraints": ["An authorized constraint"],
  "rust_signature": "pub fn solve(input: Vec<i32>) -> i32",
  "examples": [
    {"input": "...", "output": "..."}
  ]
}
```

`leetcode_difficulty` is the human-facing LeetCode label (`easy`, `medium`, or
`hard`). Before Gemini generates code, the workflow sends the authorized input
to TypeSafe's Jev model and stores a separate structured assessment in
`state/assessments/<id>.json`. Jev uses a five-level ordered Score rubric and
returns a score, level probabilities, confidence, the responding model version,
token usage, and elapsed time. The assessment is a model perspective for
comparison; it is not a correctness check and does not replace review.

`description`, constraints, and examples must be content that the repository is
allowed to send to Gemini and, if committed, allowed to publish. Set
`rust_supported` only after checking that LeetCode accepts Rust for the problem.
The pipeline rejects missing or false Rust support instead of asking Gemini to
solve it.

The scheduled workflow selects the earliest eligible JSON file that is not already
recorded in `state/progress.json` and does not already have an open automated
solution pull request. A maintainer can select a specific file with the
`challenge_path` input of the workflow dispatch.
