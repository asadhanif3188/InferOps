# V1-S5-005-PR1 validation: the V1 operator runbook

Change: an operator runbook at
[`docs/environment/operator-runbook.md`](../../environment/operator-runbook.md), its
record [`operator-runbook.v1alpha1.json`](../../environment/operator-runbook.v1alpha1.json),
the six alerts re-pointed at it, and a suite that holds it to the repository. This
record says what was run, what it found, and what none of it supports.

**Evidence class: `local-static`.** Every command this change executed reads
committed files, or writes a local file under `.cache/`, and contacts nothing else.
**No cluster was contacted.** No release was installed, upgraded, rolled back, or
uninstalled, no Terraform ran against a cluster, no forward was opened, no model was
loaded, and no completion was generated. There were two reasons, and each would have
been enough on its own. No cluster run was authorised for this change. And when it
was validated, the container engine on the host was not running, so there was no
cluster to contact.

**Product behaviour is unchanged.** The chart, the values, the environment scripts,
the Terraform configuration, and `src/` are byte-for-byte unchanged. One tool changed,
in data only: `tools/proof_dashboard/core.py` names the new claim in the Kubernetes
deployment capability group, beside the troubleshooting guide's claim, so that the
dashboard shows it as a row. Two generated files changed: the rendered alert rule files. They changed
because the `runbookRef` of each alert in the alert record changed, and each is
regenerated from that record by `python -m tools.inference_alerts --rules`. The
only difference in each rule file is the `runbook` annotation. No expression, window,
threshold, severity, or label changed.

## What the change is

**One page an operator is sent to.** It covers prerequisites, deploying a release
that stays up, verifying readiness and inference, telemetry, load testing, one
triage section per alert, eight incident procedures, and layered cleanup. The seven
incidents the story names are pod loss, an unready model, latency and errors,
resource pressure and out-of-memory, a telemetry gap, a bad release, and a cost
anomaly. The page adds model and cache faults as an eighth, because the brief lists
cache and model issues separately.

**Every incident answers the same six questions.** Detection, user impact, automatic
recovery, human action, validation, and escalation and limits, in that order and in
one table per incident. The record gives each incident a recovery kind: `automatic`,
`partial`, or `none`. The section and the summary table must both state that kind,
and a test compares them.

| Incident | Recovers without anybody | Evidence |
|---|---|---|
| Pod loss | automatic, by the Deployment controller | `local-real-cpu`, V1-S4-006-PR1 |
| Unready model | none | `local-real-cpu`, V1-S4-007-PR1 |
| Latency and errors | none | `synthetic` alert scenarios; error codes from the two real experiments |
| Resource pressure and out-of-memory | partial: the kubelet restarts a killed container | described; CPU figures from V1-S4-004-PR2 |
| Telemetry gap | partial: the collector pod is replaced, its series are not | described; a synthetic scenario and the dashboard validation |
| Bad release | none | `local-real-cpu`, V1-S3-011-PR2 |
| Model and cache faults | none | described; one refusal provoked in V1-S3-011-PR2 |
| Cost anomaly | none | `local-static` |

**Every alert now links to a section of its own.** Before this change the six
`runbookRef` values pointed at four sections of the Kubernetes troubleshooting guide,
and two alerts shared one of them. Each now points at a section of the runbook headed
with the alert's name. The section opens with a read-only command and links to every
incident the record routes that alert to. The alert record, the alert document's
table, and both rendered rule files all carry the same link, and a test compares all
four.

**Three findings the runbook states and nothing before it did.**

- **No installed release evaluates the six alerts.** The release's collector loads
  the recording rules and not the alert rule files. An early draft of the runbook
  sent the reader to the collector's own alerts page to see what was firing, and that
  page would have listed nothing. The runbook now says that "an alert fires" means
  its condition holds, and a test reads the chart's `rule_files` to keep it true.
- **No script leaves a release running.** Every workflow that installs `inferops`
  also removes it. A release an operator can watch is installed by hand, and the
  runbook's deploy steps are the ones the dashboard validation ran, with the target
  flags written out.
- **The recorded bad release fires no alert.** With one replica the candidate never
  becomes ready, the rollout keeps the serving pod, and every signal an alert reads
  stays healthy. The only signal is the candidate's init container exit code.

## Drills

These are the runbook commands that read committed files only. Each one was run from
Git Bash at the repository root, on this change's working tree, and each exited `0`.

| Command | Result |
|---|---|
| `uv run --locked python -m tools.inference_alerts` | 6 alerts satisfy the alert policy, including the rule that every runbook link resolves to a heading |
| `uv run --locked python -m tools.telemetry_collection charts/inferops-llm/ci/rendered` | 2 files satisfy the collection policy |
| `uv run --locked python -m tools.model_acquisition check` | the workspace cache holds the pinned artifact, verified, 1834426016 bytes |
| `uv run --locked python -m tools.llm_load check` | the profile validates; nothing is sent |
| `uv run --locked python -m tools.llm_load rehearse` | completed against the in-process stub: 39 dispatched, 32 successful. Labelled `synthetic`; no latency describes serving |
| `scripts/environment/performance-scenarios.sh check` | the descriptor validates; nothing is contacted |
| `uv run --locked python -m tools.cost_baseline verify --record-dir docs/proof/serving --record-prefix v1-s4-004-pr1- --dir docs/proof/cost --prefix v1-s4-005-pr2-` | 5 committed baseline files regenerate |
| `uv run --locked python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-closes.input.json --result tests/cost/fixtures/cost-calculation/estimate-closes.result.json` | the committed result regenerates |
| `uv run --locked python -m pytest tests/cost -q` | 490 passed |

### What was not drilled

- **Every command that contacts a cluster.** That covers every `kubectl` and `helm`
  sample, the target-refreshing `terraform-prerequisites.sh plan`, and every workflow
  given `INFEROPS_PROVIDER`. None was authorised, and the engine was not running.
- **Every mutating and destructive command.**
- **`scripts/environment/preflight.sh`**, which needs a running engine to answer.
- **Any incident procedure followed end to end from the page.** Three of them repeat
  the commands of an executed experiment: pod loss, unready model, and bad release.
  A workflow executing a command is not an operator following a procedure, and the
  runbook says so.

## Validation

Run from Git Bash at the repository root with every file of this change staged, so
that `git ls-files`, which the link suite collects from, saw what the commit holds.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/architecture/test_operator_runbook.py -q` | 219 passed |
| `uv run --locked python -m pytest -q` | 12702 passed, 33 skipped, 14 deselected, in 848 s |
| `uv run --locked ruff check .` | all checks passed |
| `uv run --locked ruff format --check .` | 473 files already formatted |
| `uv run --locked python -m mypy` | no issues in 262 source files |
| `uv run --locked python -m tools.proof_dashboard --check` | the committed dashboard is what the register produces |
| `uv run --locked python -m tools.ci_gates expected-failures` | every expected refusal refused |
| the documentation gate's trailing-blank and tab checks over `git ls-files '*.md'` | nothing found |
| `git diff --check` | clean |

The promtool check in `tests/architecture/test_inference_alert_rules.py` is among the
skips. It needs the pinned collector image, and the engine that holds it was not
running. The rendered rule files changed only in their `runbook` annotations, and the
suite compares both of them with what the record generates.

**What the suite caught in the first draft of the runbook.** Three incident sections
did not name their evidence the way the record did: model and cache faults had no
evidence line at all, and telemetry gap did not say `described`. The resource-pressure
section referred to "the latency alert" instead of naming it. Separately, the first
draft sent the reader to the collector's alerts page. That was found by reading the
chart before the suite existed, and the suite now holds it.

## What the independent review found

A review of the first commit, independent of its author, checked the runbook's
statements against the chart, the values files, `lib.sh`, the scripts, the API
surface record, and the proof records. It re-ran the runbook suite, the inventory
suite, the dashboard check, and the alert policy. It found **no factual error, no
overclaim, no mislabelled command, and no private information.** It confirmed that
`terraform-prerequisites.sh plan` does not change the cluster, that both workflows
the runbook says refuse while `inferops` is installed really do, and that the
collector's `rule_files` hold the recording rules only. It raised two findings, and
both are fixed in the second commit.

- **Medium: a check that would have passed a wrong pairing.** The first form of the
  container check read every `-c` value against a single allow-list of four
  container names. So `logs deployment/inferops-inferops-llm -c verify-model` would
  have passed, even though the API has no such container. The page was correct. The
  check could not have noticed if it stopped being correct. It now reads each
  container against the rendered pod template of the Deployment named in the same
  command.
- **Low: a dead end for a reader arriving from an alert.** Every alert section's
  commands read `.kube/inferops-target.config`. That file exists only after a
  workflow has verified the target, and the alert sections did not say how to write
  it. They now point to the read-only command under [the target](../../environment/operator-runbook.md#the-target).

Neither finding changed a count, a figure, or a claim in this record.

## What this record does not establish

- That following the runbook recovers anything. The suite checks strings.
- That any alert is evaluated in an installed release, or that anybody is told.
- Anything about a provider other than `docker-desktop`, a cluster with more than
  one node, or a release with more than one replica.
- That the described procedures work. Resource pressure, out-of-memory, a telemetry
  gap, and a cost anomaly have never been provoked in this project.
