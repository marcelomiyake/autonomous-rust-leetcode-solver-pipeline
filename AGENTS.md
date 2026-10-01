# Agent instructions

These instructions apply to the entire repository. Read `README.md` before changing the pipeline or adding a problem solution.

## Project state

- The repository now has a minimal Rust library crate, an authorized challenge inbox, a Gemini candidate solver, a merge-gated progress store, and daily/manual GitHub workflows. It still has no problem solutions until a maintainer supplies an authorized challenge input.
- `.github/workflows/build.yml` runs a SonarCloud scan on pushes to `main` and on pull requests. `sonar-project.properties` contains the project key `marcelomiyake_autonomous-rust-leetcode-solver-pipeline` and organization `marcelomiyake`.
- Treat the authorized challenge contents and generated solutions as data that still require maintainer review. Update the README when implementation changes the pipeline or the repository's status.
- Each authorized challenge records the human `leetcode_difficulty`; the solver runs a separate TypeSafe Jev Score assessment and publishes the structured result under `state/assessments/` with the solution pull request.

## Problem and input requirements

- Accept a problem only after confirming that LeetCode supports Rust submissions for it. Skip or reject unsupported problems before generating a candidate.
- In autonomous sequential mode, the pipeline automatically fetches the next unsolved problem (001, 002, 003, ...) via LeetCode's public GraphQL API, or uses a maintainer-supplied challenge in `challenges/`. Maintainers authorize automated retrieval of problem requirements, examples, and starter signatures.
- Keep a stable problem identifier, constraints, and the Rust function signature with each accepted input.

## Implementation guidance

- Keep each solution in a focused Rust module with tests for examples, edge cases, and relevant constraints. Put shared types in `src/common/` only when they are genuinely shared.
- Treat generated source as a candidate. Parse and validate it, limit repair attempts, and never mark or publish it as solved after a failed check.
- Advance progress state only after publication succeeds so a failed run remains retryable. Avoid committing secrets, tokens, or generated coverage files.
- Keep `GEMINI_API_KEY`, `TYPESAFE_API_KEY`, and `SONAR_TOKEN` in GitHub Actions secrets only. Generated code must be compiled without those secrets or persisted checkout credentials in its environment. Expose `TYPESAFE_API_KEY` only to the Jev assessment step, never to Gemini or Rust validation.
- Use cron-job.org as the daily trigger at 04:17 UTC (01:17 in São Paulo), dispatching the solver through GitHub `workflow_dispatch`. Keep the GitHub Actions schedule as a yearly fallback (`0 0 1 1 *`). Use manual `workflow_dispatch` for immediate development runs. Preserve the shared concurrency group so external, fallback, and manual runs cannot publish simultaneously.
- Preserve the existing SonarCloud project identity when changing scanner configuration. Align `sonar.rust.lcov.reportPaths` with the path actually produced by `cargo-llvm-cov`; configure coverage thresholds and Quality Gate conditions explicitly if they become requirements.

## Model maintenance for Gemini free tier

- Google AI Studio updates its Gemini model offerings periodically and deprecates older preview or sunset versions (e.g., `gemini-2.5-flash` was retired; `gemini-3.8-flash` is currently active).
- If candidate generation fails with HTTP 404 (model not found) or unsupported model errors:
  1. Inspect active models on the API key using `python3 scripts/solver_pipeline.py check-models` or `GET https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY`.
  2. Confirm the selected replacement belongs to the Flash model family (`gemini-*-flash`) to maintain free-tier quota eligibility (typically 10–15 RPM and 500–1,500 RPD).
  3. Update `DEFAULT_MODEL`, `DEFAULT_FALLBACK_MODEL`, and the fallback chain in `scripts/solver_pipeline.py` and `.github/workflows/leetcode-solver.yml`.
  4. Ensure the selected model supports structured JSON output and thinking budget configuration.

## Verification

- For documentation or configuration-only changes, inspect the diff and validate the affected configuration.
- For Rust changes, run `cargo fmt --check`, `cargo check`, `cargo test`, and `cargo clippy --all-targets --all-features -- -D warnings`.
- When coverage or scanner configuration changes, generate the LCOV report and verify that the scanner reads that exact file. Report any checks that could not run.

## Commits

- Give each problem its own commit containing that problem's solution and tests. Do not combine solutions for multiple problems in one commit; identify the problem in the commit message.
- All commit messages must follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): `<type>[optional scope]: <description>`. Use `feat` for new features, `fix` for bug fixes, and an appropriate type such as `docs`, `test`, `ci`, `refactor`, or `chore` for other changes.
- Add an optional body after a blank line when the reason or context needs explanation. Mark breaking changes with `!` before the colon or a `BREAKING CHANGE: <description>` footer.
- Example: `docs: add contributor instructions`.
