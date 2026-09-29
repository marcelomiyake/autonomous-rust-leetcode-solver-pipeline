# Autonomous Rust LeetCode Solver Pipeline

This repository contains a guarded pipeline that accepts maintainer-supplied
LeetCode challenge metadata, asks Gemini for a Rust solution candidate, validates
it locally, opens a pull request, and records progress only after that pull request
is merged. It never crawls or scrapes LeetCode.

**Status:** The automation, authorized-input format, Jev difficulty assessment,
progress store, bounded repair loop, coverage generation, and SonarQube Cloud
integration are implemented. No challenge has been added to `challenges/` and no
generated solution has been published yet; the first run therefore exits
successfully with “no eligible challenge” until a maintainer adds an authorized
input file. The external TypeSafe key still must be present as the documented
GitHub Actions secret before an eligible challenge is run, and that secret is
now configured. The Gemini secret still needs to be added before generation can
run.

## Problem eligibility

Before a problem is processed, verify that Rust is one of its supported LeetCode submission languages. Problems without Rust support must be skipped or rejected before candidate generation. The 3,604-of-4,069 figure reflects the problem-set filter at the time this README was written and may change as LeetCode adds or removes problems.

## Repository layout

```text
.
├── .github/
│   └── workflows/
│       ├── build.yml          # Rust checks, LCOV, and SonarQube Cloud
│       ├── record-progress.yml # Records a solution after its PR is merged
│       └── solve.yml           # Gemini generation, validation, and PR creation
├── challenges/
│   └── README.md       # Authorized challenge schema and rules
├── scripts/
│   └── solver_pipeline.py # Standard-library pipeline implementation
├── state/
│   ├── assessments/     # Published Jev AI difficulty analyses
│   └── progress.json    # Updated only after an automated solution is merged
├── src/
│   ├── common/mod.rs   # Shared types when needed
│   ├── problems/mod.rs # Problem modules will be registered here
│   └── lib.rs          # Library root
├── tests/
│   └── test_solver_pipeline.py
├── AGENTS.md
├── Cargo.lock
├── Cargo.toml
├── LICENSE
├── README.md
└── sonar-project.properties
```

The crate currently has no dependencies or problem implementations. Each future
problem module contains its own focused tests. The Python pipeline uses only the
standard library, and its tests can be run with:

```sh
python3 -m unittest discover -s tests -v
```

## Intended pipeline

1. **Accept an authorized challenge.** Add `challenges/<id>.json` using the schema in [`challenges/README.md`](challenges/README.md). The file must include the stable id, date, authorized description, constraints, Rust signature, examples, source URL, and a maintainer attestation that LeetCode supports Rust. Unsupported or incomplete inputs are rejected before any Gemini request.
2. **Select the next challenge.** The scheduled workflow ignores completed ids, existing solution modules, invalid files, and open `ai/solution-<id>` pull requests. `workflow_dispatch` can select one specific challenge path for development.
3. **Assess difficulty with Jev.** The workflow sends the authorized challenge metadata to TypeSafe's `POST https://api.typesafe.ai/v1/systemone` endpoint using the `jev-latest` model and one typed `Score` question. Its five ordered levels range from very easy to very hard. The workflow stores Jev's actual model version, score, probabilities, confidence, token usage, and elapsed time in `state/assessments/<id>.json`; this is a model perspective, not a correctness gate.
4. **Generate a candidate.** The workflow calls the Gemini Developer API with the free-tier `gemini-2.5-flash` model, structured JSON output, `temperature=0.2`, `effort=medium` (`thinkingBudget=4096`), and a 12,000-token output ceiling. The response is parsed and checked for a module body, the required function, tests, and disallowed constructs before it is written.
5. **Verify locally.** The candidate is checked with `cargo fmt --check`, `cargo check`, `cargo test`, and `cargo clippy --all-targets --all-features -- -D warnings`. Compiler diagnostics are passed to Gemini for at most two repairs after the initial request. A failed final check never creates a branch or pull request.
6. **Measure and publish.** `build.yml` installs `cargo-llvm-cov`, writes `lcov.info`, and runs the SonarQube Cloud scanner with `sonar.rust.lcov.reportPaths=lcov.info` and `sonar.qualitygate.wait=true`. A validated branch contains the solution, its Jev assessment, and the pull request metadata. The Sonar project is `marcelomiyake_autonomous-rust-leetcode-solver-pipeline` in organization `marcelomiyake`. The repository does not claim that a default Quality Gate means 80% coverage; add an explicit gate condition if that becomes a project requirement.
7. **Record only after merge.** A separate closed-pull-request workflow updates `state/progress.json` only when that branch is merged into `main`, so failed runs and rejected pull requests remain retryable.

Every generated Rust module begins with a small metadata comment containing the
problem id, LeetCode difficulty, Gemini model, effort/thinking budget,
temperature, aggregate input/output/thinking/total token counts, number of model
attempts, and solver wall time. When available, it also points to the stored Jev
assessment and includes its model, score, dominant level, and confidence. The
Gemini wall time starts at the first model request and ends when the final
candidate is prepared; it includes bounded repair calls and validation time.

SonarQube Cloud [imports coverage reports produced by other tools](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/test-coverage/overview), and its scanner can [wait for the Quality Gate](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/analysis-parameters/parameters-not-settable-in-ui) with `sonar.qualitygate.wait=true`. The LCOV output path is chosen by the `cargo-llvm-cov` command; it is not implicitly `target/llvm-cov/lcov.info`. See the [cargo-llvm-cov usage examples](https://github.com/taiki-e/cargo-llvm-cov).

## Configuration applied in external services

| Service | Configuration |
| --- | --- |
| Challenge source | Maintainer-supplied or authorized integration input only; there is no LeetCode crawler. |
| Google AI Studio | Project `Gemini Project` (`gen-lang-client-0062045673`) is present on the Free tier and currently lists an active key named `Gemini API Key`. The pipeline uses that key through the `x-goog-api-key` header; its value is never stored in the repository. The `GEMINI_API_KEY` GitHub secret is still pending because the AI Studio copy action returned a provider-side network error; no unrestricted replacement key was created. |
| TypeSafe AI | Jev is called through `POST https://api.typesafe.ai/v1/systemone` with `model=jev-latest`, a single Score question, and `Authorization: Bearer`. The response model version is stored per assessment. `TYPESAFE_API_KEY` is set as a repository Actions secret; the key is never written to the repository. |
| GitHub Actions | Verified repository secrets: `SONAR_TOKEN` and `TYPESAFE_API_KEY`. `GEMINI_API_KEY` remains to be added from the existing Google AI Studio key. `GITHUB_TOKEN` is the short-lived workflow token. The solver workflow has `contents: write` and `pull-requests: write`; the build workflow reads contents; the progress workflow has `contents: write`. |
| SonarQube Cloud | Project key `marcelomiyake_autonomous-rust-leetcode-solver-pipeline`, organization `marcelomiyake`, sources `src`, LCOV path `lcov.info`, and `sonar.qualitygate.wait=true`. |

The default model and generation settings are intentionally visible in
`.github/workflows/solve.yml` so a reviewer can audit cost and quality. The
current workflow uses one daily run at `00:17 UTC` plus manual dispatch; manual
dispatch was used for rapid development checks, so the final schedule does not
wait for a development interval.

### Secret handling

- Use an API-restricted Google AI Studio key for the Free-tier Gemini project,
  then save it in the repository’s **Settings → Secrets and variables → Actions**
  as `GEMINI_API_KEY`. Do not put it in a workflow variable, issue, log, or
  file. The repository currently has an active project key available in AI
  Studio, but the secret has not been added because the provider copy operation
  is temporarily failing.
- Create a TypeSafe dashboard API key and save it in the same Actions secret
  store as `TYPESAFE_API_KEY`. The key is exposed only to the Jev assessment
  step. It is not exposed to Gemini, Rust compilation, tests, or pull-request
  publication. TypeSafe's current model documentation lists Jev as usage-priced,
  so it should not be treated as a free-tier service without checking the
  account's current plan and limits.
- Save a SonarQube Cloud token with analysis permission as `SONAR_TOKEN` in the
  same Actions secret store. Fork pull requests do not receive either secret, and
  the Sonar step is skipped for them.
- The Gemini key is present only on generation and repair steps. The validation
  subprocess explicitly removes Gemini, Google, Sonar, and GitHub token variables,
  and checkout uses `persist-credentials: false`, before model-produced code is
  compiled or tested.
- Generated source is rejected if it contains unsafe Rust, process/filesystem/
  network access, FFI, `fn main`, crate attributes, or Markdown fences. This is a
  defense-in-depth measure; generated code still requires normal pull-request
  review.

LeetCode's [Terms of Service](https://leetcode.com/terms/) prohibit crawling and scraping and restrict unattended processes. The earlier proposal to fetch its daily challenge through unauthenticated GraphQL requests is therefore **not an approved ingestion design**. An implementation must establish an authorized source before automating retrieval. It should also avoid copying problem statements into a public repository without the right to do so.

GitHub currently makes standard hosted runner usage free for public repositories, and SonarQube Cloud has a free option for public projects. Gemini offers free tier access for some models, but availability and quotas vary by model and account. Check the current [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [SonarQube Cloud plans](https://docs.sonarsource.com/sonarqube-cloud/administering-sonarcloud/managing-subscription/subscription-plans), and [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) before enabling a schedule. These services do not guarantee a zero cost or uninterrupted run.

## Implementation checklist

- Add an authorized challenge file and test the publication path with `workflow_dispatch`.
- Review the generated pull request and merge only after correctness and licensing checks.
- Keep the [SonarQube Cloud Quality Gate](https://sonarcloud.io/project/overview?id=marcelomiyake_autonomous-rust-leetcode-solver-pipeline) configured with any repository-specific issue and coverage conditions.
- Remember that [scheduled GitHub Actions workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) run from the default branch and can be delayed or disabled after prolonged inactivity.

## Verification

For documentation-only changes, inspect the diff. For Rust and pipeline changes,
run:

```sh
python3 -m unittest discover -s tests -v
cargo fmt --check
cargo check --locked --all-targets --all-features
cargo test --locked --all-targets --all-features
cargo clippy --locked --all-targets --all-features -- -D warnings
cargo llvm-cov --all-features --workspace --lcov --output-path lcov.info
```

`lcov.info` is a local generated artifact and must not be committed. SonarQube
Cloud consumes the same path in CI.
