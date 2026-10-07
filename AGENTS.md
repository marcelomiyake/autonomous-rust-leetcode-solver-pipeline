# Agent instructions

These instructions apply to the entire repository. Read `README.md` before changing the pipeline or adding a problem solution.

## Project state

- The repository has a Rust library crate, an authorized challenge inbox, a Gemini candidate solver, a progress store, and daily/manual GitHub workflows. Problems 001–009 currently have challenge manifests, assessments, and Rust solution modules; read `state/progress.json`, `challenges/`, and `src/problems/mod.rs` for the current state instead of assuming this is an empty scaffold.
- `.github/workflows/build.yml` runs a SonarCloud scan on pushes to `main` and on pull requests. `sonar-project.properties` contains the project key `marcelomiyake_autonomous-rust-leetcode-solver-pipeline` and organization `marcelomiyake`.
- Treat the authorized challenge contents and generated solutions as data that still require maintainer review. Update the README when implementation changes the pipeline or the repository's status.
- Each authorized challenge records the human `leetcode_difficulty`; the solver runs a separate TypeSafe Jev Score assessment and publishes the structured result under `state/assessments/` with the solution commit.

## Problem and input requirements

- Accept a problem only after confirming that LeetCode supports Rust submissions for it. Skip or reject unsupported problems before generating a candidate.
- In autonomous sequential mode, the pipeline automatically fetches the next unsolved problem (001, 002, 003, ...) via LeetCode's public GraphQL API, or uses a maintainer-supplied challenge in `challenges/`. Maintainers authorize automated retrieval of problem requirements, examples, and starter signatures.
- Keep a stable problem identifier, constraints, and the exact Rust function signature with each accepted input. Do not change argument or return types when transferring a candidate. The manifest may omit implementation-only binding modifiers such as `mut`; preserve those modifiers in the generated method and any LeetCode copy when the body mutates a parameter.

## Implementation guidance

- Keep each solution in a focused Rust module with tests for examples, edge cases, and relevant constraints. Put the LeetCode entry-point method inside `impl Solution { ... }`, declare a module-local `pub struct Solution;` for local compilation, and keep the manifest's `rust_signature` as the method signature without the enclosing `impl`. Put shared types in `src/common/` only when they are genuinely shared.
- Preserve the validated method body when preparing code for LeetCode. Do not retype or simplify the entry point by hand: derive the LeetCode snippet from the accepted module and preserve required bindings such as `mut x`. Before running it in LeetCode, inspect the editor contents and confirm its signature and body match the repository candidate. Use Run and examples plus boundary cases to smoke-test; do not use Submit unless the maintainer explicitly asks for submission.
- Before accepting a candidate, verify that its method name and parameter/return types match the manifest's `rust_signature`, and compile the exact `impl Solution` entry point as part of the focused module. Keep the validated body byte-for-byte when preparing a runner snippet, aside from the local-only `pub struct Solution;` and tests; reject stale or hand-edited copies that differ.
- For integer-boundary problems, test valid values immediately inside the output range as well as overflowing values on both signs. Follow the problem's stated integer-width restriction; do not rely on a wider integer type when the statement forbids it.
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
- For every Rust solution or pipeline change, run `cargo fmt --all -- --check`, `cargo check --locked --all-targets --all-features`, `cargo test --locked --all-targets --all-features`, and `cargo clippy --locked --all-targets --all-features -- -D warnings` before accepting or publishing the candidate.
- Review the SonarCloud project Issues page across all open findings, including maintainability findings, even when the Quality Gate passes. Resolve actionable issues in source and rerun the same Rust checks. Do not close or suppress a finding just to clear the dashboard. A source fix is only confirmed in SonarCloud after a fresh analysis of the updated commit; if that analysis cannot run, report that cloud status still needs confirmation.
- When coverage or scanner configuration changes, generate the LCOV report and verify that the scanner reads that exact file. Preserve the project key and organization. Report any checks that could not run.

## Commits

- Give each problem its own commit containing that problem's solution and tests. Do not combine solutions for multiple problems in one commit; identify the problem in the commit message.
- All commit messages must follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): `<type>[optional scope]: <description>`. Use `feat` for new features, `fix` for bug fixes, and an appropriate type such as `docs`, `test`, `ci`, `refactor`, or `chore` for other changes.
- Add an optional body after a blank line when the reason or context needs explanation. Mark breaking changes with `!` before the colon or a `BREAKING CHANGE: <description>` footer.
- Example: `docs: add contributor instructions`.
