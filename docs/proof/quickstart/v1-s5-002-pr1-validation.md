# V1-S5-002-PR1 change validation

Date: 2026-09-19

Change: [the repository README](../../../README.md), rewritten as the five-minute
reviewer path, and [the changelog entry](../../../CHANGELOG.md) that describes it.

Classification: **local static evidence.** Evidence class `local-static`. Every
result below was produced on one Windows host by running commands over files in
this repository. No cluster was selected or contacted, no model was loaded, no
runtime was started, no request was served, no container was built or run, and no
job was executed on the continuous-integration service.

**No product behaviour changed.** Nothing under `src/`, `tools/`, `charts/`,
`infra/`, `deploy/`, `scripts/`, or `tests/` is touched by this change. It adds no
executable file.

Claim boundary: the README's first screen states the reference-architecture
positioning and the real LLM-serving capability; every figure on the page is quoted
from a record that already carried it; every command on the page is one a linked
document or record already publishes; every relative link resolves; every entry in
the public entry-point table is governed by the claim and evidence register; the
claim-count and test-layer sentences the register's suites read from the README
agree with the data; and no sentence on the page uses a reserved security term
without denying it.

**What this record does not establish.** It is not evidence that any statement on
the README is true beyond the record it quotes. No certification level moves and
no new measurement of any kind is made: the figures are quoted from records made
earlier, on other days, by other changes, and the page says that where it and a
record disagree, the record is right. Whether a reviewer can in fact understand
value, architecture, quick start, proof, and limitations in five minutes is a
reading, and nobody but the author of this change has made it.

## Environment

| Component | Version |
|---|---|
| Windows | 11 Enterprise 10.0.26200 |
| Shell | GNU bash 5.2.26(1)-release (x86_64-pc-msys), Git Bash |
| Python, locked environment | 3.12.12 |
| `uv` | 0.9.16 (a63e5b62e 2025-12-06) |
| `pytest` | 8.4.2 |
| `ruff` | 0.16.4 |
| Git | 2.45.1.windows.1 |
| Branch | `docs/v1-s5-002-reviewer-readme` |
| Base | `main` at `193f2e9b1d3452da7f7068f1bff0152c81504c7f` |

## Reviewer checklist

The story's acceptance criteria that fall inside this change's boundary, each read
against the page as committed.

| Criterion | Where on the page | Result |
|---|---|---|
| The first screen states real LLM serving and reference-architecture value | The opening paragraphs, before any heading, and the table under "What V1 proves" | Met. The first sentence names the reference architecture; the third paragraph opens "V1 serves real inference"; the first two evidence rows are real local and real Kubernetes serving at `C2` |
| The quick start matches the clean-clone evidence | "Quick start: the safe mock path", "Quick start: the real local path", and "The Kubernetes path" | Met. The mock commands are the ones [the developer quick start](../../developer-quick-start.md) recorded, and the clean-clone `workload-scaffold` step runs the same scaffold. The real local commands are the ones the clean-clone `model-acquisition`, `runtime-image`, and `local-real-inference` steps run, with the figures [the clean-clone run](../environment/v1-s5-001-pr2-clean-clone-run.md) carries. The Kubernetes path is the command that record executed, with its 18 steps, three invocations, and wall clock quoted |
| The strongest dashboard, load, failure, and cost evidence is linked | "What V1 proves" and "Results" | Met. Each area links its certifying record: `V1-S4-002-PR2`, `V1-S4-004-PR1` and `-PR2`, `V1-S4-006-PR1`, `V1-S4-007-PR1`, `V1-S4-005-PR2`, and `V1-S4-008-PR1`, plus the clean-clone run and the local baseline |
| Mock and real paths are unmistakable | The two quick-start headings, the evidence-label sentence that opens each, and the "Evidence" or "Label" column of every table | Met. The mock path opens by stating it can establish nothing about a model; the real path opens with the consent it needs; every table row names mock, local real, estimated, or synthetic |
| Production limitations are visible | The boxed statement under "What V1 proves", "Security boundary", and "Limitations" | Met. The first screen states one provider, one host, CPU, one replica, no authentication, no release, no second engineer, and that InferOps is not a portable production platform; the security section lists the risks that block production use |

Three criteria of the parent story belong to the next change and are not claimed
here: the direct link to the proof dashboard as the visual index of what V1 has and
has not proven (the page links the dashboard in four places, and the dashboard's
reconciliation against the final evidence-pack state is that change's work), the
reconciliation of the generated dashboard without a second source of truth, and the
rule that every reviewer-facing capability state links to a record or is labelled
planned, deferred, or not claimed on the dashboard itself.

## Claims and evidence the page uses

Every figure on the page and the record it is quoted from. A figure that appears in
more than one place on the page is listed once.

| Figure | Record |
|---|---|
| Runtime ready in 183 015 ms; completion `HTTP 200` in 3 641 ms with 43 tokens; Kubernetes completion in 2 500 ms; 18 steps; 1 h 30 min 32 s; three invocations; two stopped model transfers | [the clean-clone run](../environment/v1-s5-001-pr2-clean-clone-run.md) |
| First C2 certification on 2026-09-04 with under five per cent of headroom against the 300 000 ms readiness budget | [the C2 certification result](../serving/v1-s2-004-c2-certification-result.md) |
| Four failed Kubernetes certification attempts before the fifth passed | [the Docker Desktop paved road](../environment/v1-s3-011-pr1-docker-desktop-paved-road.md) |
| 30 expressions, 29 panels, nine states, Prometheus refused none, counts reconciled exactly | [the dashboard validation](../telemetry/v1-s4-002-pr2-dashboard-validation.md) |
| 366 requests all `HTTP 200`; 60 requests each at concurrency 1, 2, and 4, twice; degradation point at concurrency 2 | [the performance findings](../serving/v1-s4-004-pr2-performance-findings.md) |
| Replacement Ready 33 665 ms after the delete; 31 960 ms caller-visible outage; 40 of the 41 requests dispatched in it refused | [the pod-loss record](../serving/v1-s4-006-pr1-inference-pod-recovery.md) |
| Held unready for 179 755 ms; four request surfaces asked; readiness sampled from four places | [the unready-model record](../serving/v1-s4-007-pr1-unready-model-recovery.md) |
| Confidence `none`; synthetic rate card; no cost figure published | [the cost baseline](../cost/v1-s4-005-pr2-cost-baseline.md) |
| Six alerts; five replayed over three real experiments' telemetry; one fires; nothing routes | [the alert validation](../telemetry/v1-s4-008-pr1-alert-validation.md) |
| 30 measured requests, all successful, every pre-registered threshold met | [the baseline raw results](../serving/v1-s2-005-baseline-raw-results.md) |
| 58 claims: 42 certified, 7 planned, 1 deferred, 8 not claimed; the planned, deferred, and not-claimed rows the roadmap names | [the claim and evidence register](../../testing/claim-evidence-matrix.md) |
| Twelve deferred risks, ten blocking production use, and the six named on the page | [the deferred-risk register](../../security/deferred-risks.md) |
| Kubernetes `v1.34.3`, Helm `v3.19.0`, Terraform `1.15.8` | [the clean-clone run's environment](../environment/v1-s5-001-pr2-clean-clone-run.md#environment) |

Every command on the page is copied from a document that already publishes it:
[the developer quick start](../../developer-quick-start.md),
[model acquisition](../../serving/model-acquisition.md),
[the runtime package](../../serving/local-runtime-package.md),
[real-runtime certification](../../serving/real-runtime-certification.md), and
[the clean-clone workflow](../../environment/clean-clone.md). No command was
executed for this record beyond the checks listed below.

## Validation

Run from the repository root in Git Bash, on the branch named above.

```text
uv run --locked python -m pytest tests/testing/test_claim_evidence_matrix.py \
  tests/testing/test_test_strategy.py tests/testing/test_test_inventory.py \
  tests/testing/test_document_links.py tests/security/test_security_baseline.py \
  -q -k "readme or README or reserved_term or layers or claim_count or link or count"
uv run --locked python -m pytest tests/testing tests/security -q
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
git diff --check main...HEAD
```

| Check | Result |
|---|---|
| The README-reading tests: every entry-point link governed by the register, the claim-count sentence, the layer-count sentence, every relative link, and the reserved-term scan over every Markdown document | `629 passed, 3495 deselected` |
| `tests/testing` and `tests/security` in full, after this record was written | `4689 passed, 8 skipped` |
| Trailing whitespace and hard tabs in committed Markdown | no matches |
| `git diff --check` | clean |

The eight skips are the suites' own: checks that need a `helm` or `terraform`
binary, or a cluster, none of which this change touches. The same full run made
before this record existed failed exactly one test, the changelog's link to this
file, which is what that test is for.

Not run, and not needed by a change that touches no Python: `ruff format`,
`ruff check`, and `mypy`. Not run, because they are authorization-gated and this
change asserts nothing new about them: any real model, runtime, cluster, or
continuous-integration job.

## Private-information review

| Looked for | Found |
|---|---|
| Private planning material, prompts, backlog, sprint plans, positioning, or strategy text | None. The page quotes committed records and documents only; story and PR identifiers appear as identifiers, which is the existing convention |
| Local filesystem paths, drive letters, user names, or host names | None. The clean-clone command is quoted with `INFEROPS_DISK_VOLUME` described, not valued |
| Credentials, tokens, model artifacts, or machine-specific state | None |

## Limitations

- One reader, the author of this change, made the reviewer reading recorded above.
  Whether the page reads in five minutes to somebody who did not write it is not
  established.
- The tests establish that links resolve, counts agree, and vocabulary is denied
  where it must be. Whether a record says what the sentence quoting it says it
  says is a reading, and only this change's author has made it.
- The page's Kubernetes path is the clean-clone command, which has completed once,
  by the author of the change that ran it. The page says so, and this record does
  not change it.
