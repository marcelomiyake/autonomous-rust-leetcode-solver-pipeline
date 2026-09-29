# Autonomous Rust LeetCode Solver Pipeline

This repository is a scaffold for a pipeline intended to solve LeetCode's daily algorithmic challenge in Rust and check each candidate before publication. The pipeline only accepts problems that LeetCode lists as solvable in Rust. When the problem set is filtered to Rust, 3,604 of 4,069 total problems are available, so problems outside that subset are out of scope. An authorized way to obtain the challenge is a prerequisite. The planned components are GitHub Actions for orchestration, Gemini for candidate generation, Cargo for local validation, and SonarQube Cloud for code analysis.

**Status:** A minimal Rust library crate and a SonarCloud scan workflow exist. There are no problem solutions, automated solver, progress store, or daily schedule yet. The [SonarCloud project](https://sonarcloud.io/project/overview?id=marcelomiyake_autonomous-rust-leetcode-solver-pipeline) has been created, but coverage reporting and Quality Gate requirements are not configured.

## Problem eligibility

Before a problem is processed, verify that Rust is one of its supported LeetCode submission languages. Problems without Rust support must be skipped or rejected before candidate generation. The 3,604-of-4,069 figure reflects the problem-set filter at the time this README was written and may change as LeetCode adds or removes problems.

## Repository layout

```text
.
├── .github/
│   └── workflows/     # Existing SonarCloud scan workflow
├── src/
│   ├── common/mod.rs   # Shared types when needed
│   ├── problems/mod.rs # Problem modules will be registered here
│   └── lib.rs          # Library root
├── AGENTS.md
├── Cargo.lock
├── Cargo.toml
├── LICENSE
├── README.md
└── sonar-project.properties
```

The crate currently has no dependencies or problem implementations. Each future problem module should contain its own focused tests. Run `cargo fmt --check`, `cargo check`, `cargo test`, and `cargo clippy --all-targets --all-features -- -D warnings` to verify Rust changes.

## Intended pipeline

1. **Obtain a challenge through an authorized source.** Accept a problem supplied by a maintainer or an integration whose use permits automation. Store a stable identifier, date, statement, constraints, and Rust signature. Do not treat an endpoint being publicly reachable as permission to collect or republish its content.
2. **Generate a candidate.** Request Rust source and tests from a configured Gemini model. Parse and validate the response before writing files. Model output may be invalid or incorrect, so it must remain a candidate until checked.
3. **Verify locally.** Run `cargo check`, `cargo test`, and `cargo clippy --all-targets --all-features -- -D warnings`. Feed actionable diagnostics into a bounded repair loop. Stop after a configured number of attempts; do not publish a failed candidate.
4. **Measure coverage.** Generate an LCOV report with `cargo-llvm-cov`, for example `cargo llvm-cov --all-features --workspace --lcov --output-path lcov.info`. Configure an explicit coverage threshold if 80% is required. A number of test cases does not guarantee that threshold or solution correctness.
5. **Analyze the candidate.** Run a SonarQube Cloud scan for the committed candidate and wait for its Quality Gate result. Use the [created SonarCloud project](https://sonarcloud.io/project/overview?id=marcelomiyake_autonomous-rust-leetcode-solver-pipeline) with project key `marcelomiyake_autonomous-rust-leetcode-solver-pipeline`, configure its organization and `SONAR_TOKEN`, and set `sonar.rust.lcov.reportPaths` to match the generated report. The Quality Gate must explicitly contain any required coverage and issue conditions; passing the default gate does not imply zero issues or 80% overall coverage.
6. **Publish after the gates pass.** Create or update a candidate branch and pull request, then merge according to repository policy. Record progress only after publication succeeds, so failed runs can be retried without claiming a problem was solved.

SonarQube Cloud [imports coverage reports produced by other tools](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/test-coverage/overview), and its scanner can [wait for the Quality Gate](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/analysis-parameters/parameters-not-settable-in-ui) with `sonar.qualitygate.wait=true`. The LCOV output path is chosen by the `cargo-llvm-cov` command; it is not implicitly `target/llvm-cov/lcov.info`. See the [cargo-llvm-cov usage examples](https://github.com/taiki-e/cargo-llvm-cov).

## External service requirements

| Service | Configuration needed before implementation can run |
| --- | --- |
| Challenge source | Permission and a supported way to obtain the problem data |
| Gemini API | An API key in GitHub Actions secrets and a model available to the account |
| SonarQube Cloud | The [created project](https://sonarcloud.io/project/overview?id=marcelomiyake_autonomous-rust-leetcode-solver-pipeline), project key `marcelomiyake_autonomous-rust-leetcode-solver-pipeline`, its organization, a token in GitHub Actions secrets, and a configured Quality Gate |
| GitHub Actions | A workflow on the default branch with only the permissions needed for its publication method |

LeetCode's [Terms of Service](https://leetcode.com/terms/) prohibit crawling and scraping and restrict unattended processes. The earlier proposal to fetch its daily challenge through unauthenticated GraphQL requests is therefore **not an approved ingestion design**. An implementation must establish an authorized source before automating retrieval. It should also avoid copying problem statements into a public repository without the right to do so.

GitHub currently makes standard hosted runner usage free for public repositories, and SonarQube Cloud has a free option for public projects. Gemini offers free tier access for some models, but availability and quotas vary by model and account. Check the current [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [SonarQube Cloud plans](https://docs.sonarsource.com/sonarqube-cloud/administering-sonarcloud/managing-subscription/subscription-plans), and [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) before enabling a schedule. These services do not guarantee a zero cost or uninterrupted run.

## Implementation checklist

- Define shared Rust types when the challenge input format is established.
- Define the challenge input format and an authorized input mechanism.
- Implement candidate generation, bounded retries, and state updates.
- Add a workflow that checks out the repository, installs tools, validates the candidate, produces coverage, and runs the SonarQube Cloud scan.
- Configure the Quality Gate and test the publication path on a candidate branch.
- Enable scheduling only after the end-to-end path works. [Scheduled GitHub Actions workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) run from the default branch and can be delayed or disabled after prolonged inactivity.
