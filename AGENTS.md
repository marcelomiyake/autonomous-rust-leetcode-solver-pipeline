# Agent instructions

These instructions apply to the entire repository. Read `README.md` before changing the pipeline or adding a problem solution.

## Project state

- The repository now has a minimal Rust library crate, an authorized challenge inbox, a Gemini candidate solver, a merge-gated progress store, and daily/manual GitHub workflows. It still has no problem solutions until a maintainer supplies an authorized challenge input.
- `.github/workflows/build.yml` runs a SonarCloud scan on pushes to `main` and on pull requests. `sonar-project.properties` contains the project key `marcelomiyake_autonomous-rust-leetcode-solver-pipeline` and organization `marcelomiyake`.
- Treat the authorized challenge contents and generated solutions as data that still require maintainer review. Update the README when implementation changes the pipeline or the repository's status.

## Problem and input requirements

- Accept a problem only after confirming that LeetCode supports Rust submissions for it. Skip or reject unsupported problems before generating a candidate.
- Use a maintainer-supplied problem or another authorized input source. Do not implement LeetCode crawling, scraping, or unattended retrieval through an undocumented endpoint as a shortcut.
- Keep a stable problem identifier, constraints, and the Rust function signature with each accepted input. Do not publish copied problem statements unless the repository has permission to do so.

## Implementation guidance

- Keep each solution in a focused Rust module with tests for examples, edge cases, and relevant constraints. Put shared types in `src/common/` only when they are genuinely shared.
- Treat generated source as a candidate. Parse and validate it, limit repair attempts, and never mark or publish it as solved after a failed check.
- Advance progress state only after publication succeeds so a failed run remains retryable. Avoid committing secrets, tokens, or generated coverage files.
- Keep `GEMINI_API_KEY` and `SONAR_TOKEN` in GitHub Actions secrets only. Generated code must be compiled without those secrets or persisted checkout credentials in its environment.
- Keep the final solver schedule at one run per day; use `workflow_dispatch` for rapid development runs instead of committing a short-lived schedule.
- Preserve the existing SonarCloud project identity when changing scanner configuration. Align `sonar.rust.lcov.reportPaths` with the path actually produced by `cargo-llvm-cov`; configure coverage thresholds and Quality Gate conditions explicitly if they become requirements.

## Verification

- For documentation or configuration-only changes, inspect the diff and validate the affected configuration.
- For Rust changes, run `cargo fmt --check`, `cargo check`, `cargo test`, and `cargo clippy --all-targets --all-features -- -D warnings`.
- When coverage or scanner configuration changes, generate the LCOV report and verify that the scanner reads that exact file. Report any checks that could not run.

## Commits

- Give each problem its own commit containing that problem's solution and tests. Do not combine solutions for multiple problems in one commit; identify the problem in the commit message.
- All commit messages must follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): `<type>[optional scope]: <description>`. Use `feat` for new features, `fix` for bug fixes, and an appropriate type such as `docs`, `test`, `ci`, `refactor`, or `chore` for other changes.
- Add an optional body after a blank line when the reason or context needs explanation. Mark breaking changes with `!` before the colon or a `BREAKING CHANGE: <description>` footer.
- Example: `docs: add contributor instructions`.
