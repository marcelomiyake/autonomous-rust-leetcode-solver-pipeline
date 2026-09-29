# Authorized challenge inbox

The solver automatically ingests challenges in sequential order (001, 002, 003, ...)
from LeetCode's public GraphQL API, storing the metadata in this directory and its
body in `challenges/bodies/`. Maintainers can also supply challenge files manually.
The scheduler selects the earliest eligible challenge, then hydrates the body for
only the one selected challenge into the ignored `.pipeline/` directory.

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
  "rust_signature": "pub fn solve(input: Vec<i32>) -> i32",
  "body_source": {
    "type": "local-json",
    "path": "challenges/bodies/stable-kebab-case-id.json"
  }
}
```

The body source must be a JSON object containing `description`, `constraints`,
and `examples`. Use `local-json` for a maintainer-supplied file or
`https-json` for an authorized integration endpoint. HTTPS bodies are fetched
only after selection, never while the scheduler scans metadata. A body source
may repeat `rust_signature`, but it must exactly match the manifest signature.

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

The scheduled workflow selects the earliest eligible JSON file by
`challenge_date` and stable id that is not already recorded in
`state/progress.json`. A maintainer can select a specific file with the
`challenge_path` input of the workflow dispatch. Scheduled runs publish directly
to `main`; a manual `dry-run` validates a candidate without changing the
repository.
