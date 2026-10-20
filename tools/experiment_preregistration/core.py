"""The preregistration of the reliability experiments, checked against its sources.

The freeze records of V2-E02A, V2-E02B, V2-E02C, V2-E04, and V2-E05 fix each
experiment before its first result-bearing run. ``tools.experiment_freeze``
checks that every record answers every freeze field and is not edited after it
is registered. It does not read an answer. This module reads the answers that a
reliability experiment depends on, and compares each one with the committed
record that it names or with another of the five records.

**The environment is the qualified one.** Each record names one qualification
by identifier, path, and content digest. The qualification must be committed
with that digest and be ``QUALIFIED``, and it must state the provider, the
environment digest, the identity revision, the Kubernetes server version, the
node count, and the freeze record that the experiment record states.

**The bounds are the committed ones.** Each record names one bound record by
path and content digest, and states its four bounds. The bound record must be
the latest one committed, with that digest, and state the same four names,
formulas, and values. Its environment must be the record's, its qualification
the record's qualification, and its release the release that the qualification
qualified. A criterion that names a bound states the value of that bound as a
whole figure in milliseconds; what the statement says about the figure is not
read.

**The controlled comparison differs in the runtime topology alone.** V2-E02A
and V2-E02B must state the same environment, caller profile, fault, repetition
count, collection, window, measurements, outcome rules, exclusion reasons,
abort conditions, cleanup, evidence layout, and intended level. Their
topologies may differ only in the members that :data:`PERMITTED_TOPOLOGY`
names: the runtime replica count, the release, the runtime disruption budget, and
the statement. The replica counts and the release of each side, its identifier,
workload version, contract, values digest, and desired-state files, must be what
the committed baseline comparison record states for that side and what the record
pins. The comparison record must be ``COMPARABLE``, have the content digest that
both records state, and list the permitted differences that they copy. Each
disruption budget must be the one that the chart renders for the replica count of
its tier. The statement is free text and is compared with nothing. V2-E02C,
V2-E04, and V2-E05 state the topology of V2-E02B.

**Every executable that a record lists is pinned.** ``definition.executables`` is
a list of at least one file. Each must be a pinned input of the record, and the
entry file of a tool must have its entry module in the material scope. The scope
must name this check, the record's ``procedure/`` directory, the qualification,
and the bound record. So a driver that a later change adds to that directory is
listed as added by ``python -m tools.experiment_freeze --changes``. Whether a
pinned file exists, and has its pinned content, is that command's.

**A malformed record is a finding.** Every member that a step indexes is held to
its type first, and a record that does not have it is ``prereg-record-shape``.

**It imports one private function**, ``_reasons_problem`` of
``tools.reliability_analysis``, so that it reads exclusion reasons as the
aggregate reads them. A change to that function moves a pin of each record.

**Each record is read under its own rule set.** :data:`RULE_SETS` numbers them.
The five revision-1 records that V2-S6-003-PR1 registered state no rule set and
are read under rule set 1, the twelve rules that they were registered under.
Every later revision states its rule set in ``metadata.preregistrationRules``,
and a record that states none, or one that this module does not know, is
``prereg-rule-set-unknown``. Rule set 2 adds the clock rules: a record of rule
set 2 states ``definition.clockPolicy``, one policy for the node clock and the
host clock, ``definition.criterionClocks``, the clock of each instant that a
criterion orders or measures, and ``definition.criteriaWithoutClocks``, each
criterion that orders no instant and measures no interval. The policy holds the
inventory of
:data:`CLOCK_SOURCES`, the P8 measurement, the bound formula of revision 1 word
for word, the offset-stability assumption, the rules for an unusable reading and
for a verdict that is not judged, and one margin for orders and bound
comparisons across the two clocks, each word for word. No text of such a record
states that the clock difference is not measured, orders instants by a time
without the margin, claims synchronized clocks or a guarantee, or makes every run
INCONCLUSIVE, in the phrases that this module names.

**Rule set 3 adds the reversal timing of V2-E04.** It holds every rule of rule
set 2, unchanged, so a record of rule set 3 states the clock policy of rule set 2,
and it adds four rules that read a V2-E04 record. A V2-E04 record after revision 1
states rule set 3 or later. The record's
``definition.reversalTiming`` names five instants, each with the source and the
clock of :data:`REVERSAL_INSTANTS`. ``reversalStart`` is the instant at which the
reversal commit is visible in the remote desired state, bracketed by two operator
events and judged at the earlier one. ``stabilizationOnset`` is read from
``stabilizedRecovery.span.first.finishedAt`` of the run analysis, which states only
a span that completed, and it is ``recoveryEnd``. The record states ``recoveryMs``,
``gitopsDiscoveryMs``, and ``operatorDecisionMs`` with their ends, E04-AC12 judges
``recoveryMs`` cross-clock against the bound of ``derivedNumericBounds``, E04-AC8
ends its window at ``desiredStateRestored``, and two exclusion reasons leave
E04-AC12 not judged when an instant is not established. Beside the structure, they
read the phrases of :data:`REVERSAL_PHRASES` in four texts, and no other prose: a
text that holds the phrases can still say something else. Rule set 2 is not edited:
each record registered under it reads as it did. The rules read the structure that
a record states. They do not read a run.

**Rule set 4 replaces the onset exclusion of rule set 3 with a selection.** Rule
set 3 leaves E04-AC12 not judged when the span of the analysis does not start
after ``reversalStart``, for the reason ``recovery-onset-not-after-reversal``. The
amended definition takes the first span that starts after ``reversalStart`` and
then completes instead, so rule set 4 holds a V2-E04 record to
``definition.reversalTiming.selection``, which selects that span by the span rule
of ``tools.reliability_analysis``, with each cross-clock order inside the margin
of the policy resolved both ways, and to ``tools.reversal_outcome``, the outcome
reference that applies it. Rule set 4 holds every rule of rule set 2,
``prereg-reversal-intervals`` and ``prereg-reversal-criteria`` unchanged, the parts
of ``prereg-reversal-instants`` that hold ``reversalStart``,
``controllerObserved``, ``desiredStateRestored``, the source and clock of each
instant, the observation limit of ``stabilizedAt``, and ``recoveryEnd``, the part
of ``prereg-reversal-reasons`` that holds ``reversal-start-unconfirmed``, and six
selection rules. The sixth holds that the controller's discovery of the reversal is
system recovery, which E04-AC12 judges, and no condition of validity, as the
repository owner decided by change control on 2026-10-20. A V2-E04 record after
revision 2 states rule set 4 or later. Rule
set 3 is not edited: revision 2 reads as before. This module does not import
``tools.reversal_outcome``, so the pins of the records that do not name it do not
gain it.

**The latest revision is checked in full, and every earlier one alone.** The
latest revision of each experiment is checked against every rule of its rule
set, and the records are compared with each other. A superseded revision is
checked alone, against every rule of its own rule set that reads one record,
except the two clauses that compare it with the present: that its bound record
is the latest committed one, and that its qualified release is the release of
the latest V2-E02B. Those two clauses are the one narrowing of a revision-1 check,
and it applies only once a revision is superseded. :func:`check_records` checks
any set of records in full, as :func:`check_repository` checks the latest ones.

**What this does not do.** It reads files and writes none. It runs no
experiment, contacts no cluster, and reads no Git history. It does not judge
whether a statement of a record is right: it checks that the values it compares
agree, and it reads text only for the phrases that the clock rules name. A
negation anywhere in a sentence hides a claim of synchronization or a guarantee
from that reading, and a paraphrase that no phrase names is not refused. It does
not check that a criterion that orders no instant is truly without clocks, and it
does not read how ``tools.reliability_analysis`` cuts the window or searches a
stabilization span across the two clocks. It does not compare the pins of a record with the files of
the tree: the freeze tool's ``--changes`` command does that. It does not check
that a run executes the latest revision of its experiment: P1 of each record
states that, and the review of the run compares it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from tools.experiment_freeze.core import (
    RECORD_NAME,
    content_digest,
    load_registry,
    record_paths,
)
from tools.reliability_analysis.core import (
    STABILIZATION_SPAN_MS,
    STABILIZATION_SUCCESSES,
    _reasons_problem,
)

__all__ = [
    "BASELINE",
    "CLOCKS",
    "CLOCK_BOUND_COMPUTATION",
    "CLOCK_BOUND_FORMULA",
    "CLOCK_MARGIN",
    "CLOCK_RULE_SET",
    "CLOCK_SOURCES",
    "COMPARISON_RULES",
    "END_READING_RULE",
    "EXPERIMENTS",
    "NOT_JUDGED_MEMBER",
    "NOT_JUDGED_RULE",
    "OFFSET_STABILITY",
    "ORDERING_RULES",
    "PERMITTED_TOPOLOGY",
    "RECONCILIATION_COMPONENTS",
    "REPO_ROOT",
    "REVERSAL_EXPERIMENT",
    "REVERSAL_INSTANTS",
    "REVERSAL_INTERVALS",
    "REVERSAL_RULE_SET",
    "REVISION_ONE_RECORDS",
    "RULES",
    "RULE_SETS",
    "SELECTION_RULE_SET",
    "SHARED_DEFINITION",
    "SHARED_FIELDS",
    "TARGET",
    "Experiment",
    "Finding",
    "check_records",
    "check_repository",
    "latest_records",
    "record_revisions",
    "superseded_count",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Experiment:
    """One reliability experiment: its identifier and the directory of its records."""

    experiment_id: str
    directory: str
    run_prefix: str


#: The five experiments, in the order the records list them.
EXPERIMENTS: Final[tuple[Experiment, ...]] = (
    Experiment("V2-E02A", "docs/proof/experiments/v2-e02a", "e02a"),
    Experiment("V2-E02B", "docs/proof/experiments/v2-e02b", "e02b"),
    Experiment("V2-E02C", "docs/proof/experiments/v2-e02c", "e02c"),
    Experiment("V2-E04", "docs/proof/experiments/v2-e04", "e04"),
    Experiment("V2-E05", "docs/proof/experiments/v2-e05", "e05"),
)

#: The two sides of the controlled comparison.
BASELINE: Final = "V2-E02A"
TARGET: Final = "V2-E02B"

#: Where the bound records are committed, and the name of one.
BOUNDS_DIR: Final = "docs/proof/experiments/v2-q4"
BOUNDS_NAME: Final = re.compile(r"^bounds-r([1-9][0-9]*)\.v1alpha1\.json$")

#: The schema name of a bound record, and the result of a usable qualification.
BOUNDS_SCHEMA: Final = "inferops.io/experiment-bounds/v1alpha1"
QUALIFIED: Final = "QUALIFIED"
COMPARABLE: Final = "COMPARABLE"

#: The freeze fields that every one of the five records answers alike.
COMMON_FIELDS: Final = (
    "environmentIdentity",
    "callerProfileRevision",
    "intendedEvidenceLevel",
)

#: The freeze fields that V2-E02A and V2-E02B answer alike.
SHARED_FIELDS: Final = (
    "environmentIdentity",
    "callerProfileRevision",
    "fault",
    "repetitionCount",
    "derivedNumericBounds",
    "evidencePaths",
    "abortConditions",
    "cleanupProcedure",
    "intendedEvidenceLevel",
)

#: The members of ``definition`` that V2-E02A and V2-E02B state alike.
SHARED_DEFINITION: Final = (
    "preparation",
    "callerRun",
    "collection",
    "stablePreFaultWindow",
    "faultProcedure",
    "observation",
    "postRecoveryWindow",
    "window",
    "analysisDeclaration",
    "measurements",
    "outcomeRules",
    "repetitionRule",
    "executables",
)

#: The members of a bound value that differ between experiments: what each
#: experiment uses a bound for, and the reconciliation bound of V2-E05.
BOUND_MEMBERS_NOT_SHARED: Final = frozenset({"use", "reconciliationBound"})

#: The members of a topology in which V2-E02A may differ from V2-E02B. Every other
#: member is equal.
PERMITTED_TOPOLOGY: Final = frozenset(
    {"runtimeReplicas", "release", "runtimeDisruptionBudget", "statement"}
)

#: The members of the release of a topology.
RELEASE_MEMBERS: Final = frozenset(
    {
        "releaseId",
        "workloadVersion",
        "contract",
        "desiredStateFiles",
        "filesFrom",
        "helmValuesSha256",
    }
)

#: The reconciliation bound of V2-E05: the documented reconciliation timeout, the
#: documented maximum jitter, and an allowance, in milliseconds.
RECONCILIATION_COMPONENTS: Final[Mapping[str, int]] = {
    "reconciliationTimeoutMs": 120_000,
    "reconciliationJitterMaximumMs": 60_000,
    "allowanceMs": 30_000,
}
RECONCILIATION_BOUND: Final = "reconciliation_bound_ms"
RECONCILIATION_EXPERIMENT: Final = "V2-E05"

#: The chart renders a PodDisruptionBudget with minAvailable 1 for a tier of at
#: least two replicas, and none for one replica.
_BUDGET_REPLICAS: Final = 2
_BUDGET_MINIMUM: Final = 1

#: The entry file of a tool that a procedure runs, and its package.
_ENTRY_FILE: Final = re.compile(r"tools/([a-z_][a-z0-9_]*)/__main__\.py")

#: The entry module of this tool, which each record pins.
ENTRY_MODULE: Final = "tools.experiment_preregistration.__main__"

#: The member of ``metadata`` that states the rule set of a record.
RULE_SET_MEMBER: Final = "preregistrationRules"
RULE_SET_ONE: Final = 1
CLOCK_RULE_SET: Final = 2
REVERSAL_RULE_SET: Final = 3
SELECTION_RULE_SET: Final = 4

#: Each rule set, by number. A record is read under the rule set that it was
#: registered under, and a later rule set never changes how an earlier one reads.
RULE_SETS: Final[Mapping[int, str]] = {
    RULE_SET_ONE: (
        "The twelve rules that V2-S6-003-PR1 registered the five revision-1 records "
        "under. A record of rule set 1 states no rule set."
    ),
    CLOCK_RULE_SET: (
        "Rule set 1 and the clock rules: one clock policy for the node clock and the "
        "host clock, the clock of each instant that a criterion orders or measures, "
        "and no text that contradicts the policy."
    ),
    REVERSAL_RULE_SET: (
        "Every rule of rule set 2, unchanged, and the four reversal-timing rules, which "
        "read a V2-E04 record: its named instants and intervals, its recovery and "
        "containment criteria, and the exclusion reasons of its timing. A V2-E04 "
        "record after revision 1 states rule set 3 or later."
    ),
    SELECTION_RULE_SET: (
        "Every rule of rule set 2, unchanged; prereg-reversal-intervals and "
        "prereg-reversal-criteria of rule set 3, unchanged; the parts of "
        "prereg-reversal-instants that hold reversalStart, controllerObserved, "
        "desiredStateRestored, the source and the clock of each instant, the "
        "observation limit of stabilizedAt, and recoveryEnd, and the part of "
        "prereg-reversal-reasons that holds reversal-start-unconfirmed, each "
        "unchanged; and the six selection rules, which read a V2-E04 record: the "
        "selection of the span after reversalStart, no onset exclusion, the recovery "
        "criterion when no such span completes, the members of the selected span, "
        "the pinned outcome reference, and the controller's discovery as system "
        "recovery and no condition of validity. A V2-E04 record after revision 2 "
        "states rule set 4 or later."
    ),
}

#: The records of rule set 1: revision 1 of each experiment, as registered.
REVISION_ONE_RECORDS: Final = frozenset(
    f"{experiment.directory}/freeze-r1.v1alpha1.json" for experiment in EXPERIMENTS
)

#: The two clocks of rule set 2, in the order that a policy lists them.
CLOCKS: Final = ("node", "host")

#: Each instant source of rule set 2, with its clock and its resolution in
#: milliseconds. Kubernetes and the delivery controller state their timestamps to
#: the second. They are on the node clock because the provider has one node.
CLOCK_SOURCES: Final[Mapping[str, tuple[str, int]]] = {
    "caller-record": ("node", 1),
    "kubernetes-timestamp": ("node", 1000),
    "collector-reading": ("host", 1),
    "operator-event": ("host", 1),
    "clock-reading-host": ("host", 1),
    "clock-reading-node": ("node", 1),
}

#: The step of the preparation that reads the clocks, its two readings, and the
#: three instants of one reading, in the order that they are taken.
CLOCK_STEP: Final = "P8"
CLOCK_READINGS: Final = ("start", "end")
CLOCK_INSTANTS: Final = ("hostBefore", "node", "hostAfter")

#: The bound formula of P8 of each revision-1 record, word for word.
CLOCK_BOUND_FORMULA: Final = (
    "the largest of the two differences between the node instant and the nearer "
    "host instant, plus the time between the two host instants"
)

#: How rule set 2 computes that formula. Where the formula can be read in two
#: ways, it takes the reading that gives the larger bound.
CLOCK_BOUND_COMPUTATION: Final = (
    "For each reading, d is the absolute difference between the node instant and "
    "the nearer of its two host instants, and w is the time from its first to its "
    "second host instant. The clock bound of the run is the larger d of the start "
    "and the end reading plus the larger w of the two readings, in milliseconds."
)

#: The one margin of rule set 2 for an order or a bound comparison across clocks.
CLOCK_MARGIN: Final = (
    "the clock bound of the run plus the coarser resolution of the two sources"
)

#: The assumption under which the bound applies between the two readings.
OFFSET_STABILITY: Final = (
    "The clock bound is measured at the start reading and at the end reading only. "
    "To apply it to an instant between the two readings is an assumption: the offset "
    "between the node clock and the host clock stays inside the clock bound between "
    "them. Each record of rule set 2 makes that assumption explicitly, and no "
    "reading tests it."
)

#: The rule for a verdict that is not judged. The states are ordered PASSED, then
#: FAILED, then INCONCLUSIVE, and a failed verdict never improves a state, so the
#: two computations bound every other one.
NOT_JUDGED_RULE: Final = (
    "A verdict that is not judged is neither held nor failed. The state of the run "
    "is computed twice from the judged verdicts: once with each verdict that is not "
    "judged taken as held, and once with each taken as failed. When the two states "
    "are the same, that is the state of the run. When they differ, the run is "
    "INCONCLUSIVE for the reason of a verdict that is not judged. So a state that "
    "the judged verdicts decide stands, and a FAILED state that they decide is "
    "never made INCONCLUSIVE."
)

#: The rule for an unusable end reading. The state is the one that the rule for a
#: verdict that is not judged decides, not a fixed INCONCLUSIVE.
END_READING_RULE: Final = (
    "An unusable end reading makes the clock bound not computable. Each verdict that "
    "depends on the bound is then not judged: each order of an instant of the node "
    "clock and an instant of the host clock, and each comparison of an interval "
    "between the two clocks with a bound. Each other verdict is judged. "
    "definition.clockPolicy.notJudged then decides the state, with the reason "
    "clock-reading-missing."
)
NOT_JUDGED_MEMBER: Final = "definition.clockPolicy.notJudged"

#: The ordering rule and the bound-comparison rule, across the two clocks and on
#: one clock, word for word.
ORDERING_RULES: Final[Mapping[str, str]] = {
    "crossClock": (
        "No order is stated between an instant of the node clock and an instant of "
        "the host clock when their difference is at most the clock bound of the run "
        "plus the coarser resolution of their two sources. A verdict that needs that "
        "order is not judged, for the reason clock-bound-reached."
    ),
    "sameClock": (
        "Two instants of one clock are ordered to the coarser resolution of their two "
        "sources. Two Kubernetes timestamps of the same second are not ordered."
    ),
}
COMPARISON_RULES: Final[Mapping[str, str]] = {
    "crossClock": (
        "An interval from an instant of one clock to an instant of the other is "
        "compared with a bound only when it differs from the bound by more than the "
        "clock bound of the run plus the coarser resolution of its two sources. "
        "Otherwise the comparison is not judged, for the reason clock-bound-reached."
    ),
    "sameClock": (
        "An interval between two instants of one clock is compared with a bound "
        "directly, as its sources state it."
    ),
}

#: The two exclusion reasons of the clock rules.
CLOCK_READING_MISSING: Final = "clock-reading-missing"
CLOCK_BOUND_REACHED: Final = "clock-bound-reached"
INCONCLUSIVE: Final = "INCONCLUSIVE"

#: The comparisons that a criterion clock entry declares.
CLOCK_COMPARISONS: Final = frozenset({"order", "interval"})

#: The experiment whose records of rule set 3 the reversal-timing rules read.
REVERSAL_EXPERIMENT: Final = "V2-E04"

#: Each named instant of ``definition.reversalTiming.instants``, with its source.
#: Its clock is the inventory clock of that source.
REVERSAL_INSTANTS: Final[Mapping[str, str]] = {
    "reversalStart": "operator-event",
    "controllerObserved": "collector-reading",
    "desiredStateRestored": "collector-reading",
    "stabilizationOnset": "caller-record",
    "stabilizedAt": "caller-record",
}
REVERSAL_START: Final = "reversalStart"
STABILIZATION_ONSET: Final = "stabilizationOnset"
STABILIZED_AT: Final = "stabilizedAt"
DESIRED_STATE_RESTORED: Final = "desiredStateRestored"

#: reversalStart is the instant at which the reversal commit is visible in the
#: remote desired state. It is bracketed by two instants and judged at the earlier.
GIT_VISIBILITY: Final = "git-visibility"
EARLIER: Final = "earlier"
BRACKET_ENDS: Final = ("earlier", "later")

#: The phrases that the prose of the reversal timing holds, by the path of its member
#: under ``instants``. They tie the earlier end of the bracket to the record taken
#: before the push, the later end to the confirming read, and the onset to the first
#: request of a completed span. The rules read these phrases and no other prose, so a
#: text that holds them can still say something else.
REVERSAL_PHRASES: Final[Mapping[tuple[str, ...], tuple[str, ...]]] = {
    ("reversalStart", "definition"): (
        "remote that the controller reads",
        "not a controller observation",
    ),
    ("reversalStart", "bracket", "earlier", "instant"): (
        "reversal-created",
        "immediately before the push",
    ),
    ("reversalStart", "bracket", "later", "instant"): (
        "first read of main",
        "reversal-accepted",
    ),
    ("stabilizationOnset", "definition"): (
        "first request",
        "starts after reversalStart",
        "observed complete without interruption",
    ),
}

#: The member of a run analysis from which each caller instant is read. The span
#: that ``tools.reliability_analysis`` states is one that completed: ``span.first``
#: names its first request, with the completion instant ``finishedAt``, and
#: ``stabilizedAt`` is the completion of its last.
ANALYSIS_MEMBERS: Final[Mapping[str, str]] = {
    "stabilizationOnset": "stabilizedRecovery.span.first.finishedAt",
    "stabilizedAt": "stabilizedRecovery.stabilizedAt",
}

#: Each interval of the reversal: its start, its end, and whether a criterion
#: judges it. The operator interval starts at an operator event.
REVERSAL_INTERVALS: Final[Mapping[str, tuple[str, str, bool]]] = {
    "recoveryMs": ("reversalStart", "stabilizationOnset", True),
    "gitopsDiscoveryMs": ("reversalStart", "controllerObserved", False),
    "operatorDecisionMs": ("detection-reviewed", "reversalStart", False),
}
RECOVERY_INTERVAL: Final = "recoveryMs"

#: The operator events of the reversal, which keep their own instants.
REVERSAL_EVENTS: Final = (
    "detection-reviewed",
    "reversal-decided",
    "reversal-created",
    "reversal-accepted",
)

#: The criterion that judges the recovery, and its bound.
RECOVERY_CRITERION: Final = "E04-AC12"
RECOVERY_BOUND: Final = "reversal_recovery_bound_ms"

#: The containment criterion whose window covers the whole failed rollout.
CONTAINMENT_CRITERION: Final = "E04-AC8"
CONTAINMENT_WINDOW: Final[Mapping[str, str]] = {
    "from": "fault-injection-started",
    "to": "desiredStateRestored",
}

#: The two exclusion reasons of the reversal timing, and the verdict that each
#: leaves for the recovery criterion.
REVERSAL_START_UNCONFIRMED: Final = "reversal-start-unconfirmed"
ONSET_NOT_AFTER_START: Final = "recovery-onset-not-after-reversal"
NOT_JUDGED_VERDICT: Final = "not-judged"

#: The phrases of the definition of reversalStart and of its bracket ends: the
#: phrases of rule set 3 that rule set 4 keeps.
START_PHRASES: Final[Mapping[tuple[str, ...], tuple[str, ...]]] = {
    path: phrases
    for path, phrases in REVERSAL_PHRASES.items()
    if path[0] == REVERSAL_START
}

#: The selection of rule set 4: the member that states it, and what each of its
#: members states. The candidates are the caller completions after reversalStart,
#: the span rule is that of tools/reliability_analysis, unchanged, and each order of
#: a node instant and a host instant inside the margin is resolved both ways.
SELECTION: Final = "selection"
SELECTED_BY: Final = "definition.reversalTiming.selection"
SELECTION_CANDIDATES: Final[Mapping[str, str]] = {
    "after": REVERSAL_START,
    "source": "caller-record",
}
SPAN_RULE: Final[Mapping[str, object]] = {
    "tool": "tools/reliability_analysis",
    "function": "_find_span",
    "unchanged": True,
    "consecutiveSuccesses": STABILIZATION_SUCCESSES,
    "spanMs": STABILIZATION_SPAN_MS,
}
SELECTED_REQUESTS: Final[Mapping[str, tuple[str, str]]] = {
    "onset": (STABILIZATION_ONSET, "first"),
    "stabilizedAt": (STABILIZED_AT, "last"),
}
#: The observation limit of revision 2, which rule set 4 holds unchanged.
OBSERVATION_LIMIT: Final[Mapping[str, object]] = {
    "afterEvent": "fault-injection-finished",
    "limitMs": 1_680_000,
}
OBSERVATION_LIMIT_TEXT: Final = (
    "The observation limit is 1,680 s after the fault-injection-finished event."
)
BEFORE_REVERSAL_START: Final[Mapping[str, bool]] = {
    "selected": False,
    "reasonForVerdict": False,
}
BOTH_WAYS: Final = "both-ways"
SELECTION_ORDERS: Final[Mapping[str, tuple[str, str]]] = {
    "candidate-and-reversal-start": ("margin-as-after", "margin-as-before"),
    "stabilized-at-and-observation-limit": ("margin-as-inside", "margin-as-outside"),
}
#: What the resolutions decide when they give different verdicts.
DIFFERENT_VERDICTS: Final[Mapping[str, str]] = {
    "verdict": NOT_JUDGED_VERDICT,
    "reason": "clock-bound-reached",
    "stateDecidedBy": "definition.clockPolicy.notJudged",
}
#: The span that the reported instants, the figures, and E04-AC5 use: that of the
#: resolution that counts only the completions ordered after reversalStart, which
#: does not understate recoveryMs, and otherwise that of the other one.
REPORTED_SPAN: Final[Mapping[str, object]] = {
    "resolution": "margin-as-before",
    "otherwise": "margin-as-after",
    "members": [
        STABILIZATION_ONSET,
        STABILIZED_AT,
        "recoveryMs",
        "definition.postRecoveryWindow",
        "E04-AC5",
    ],
}
SELECTION_END_READING: Final[Mapping[str, str]] = {
    "reason": "clock-reading-missing",
    "dependsOnBound": NOT_JUDGED_VERDICT,
    "noSpan": "not-met",
}
#: The outcome reference that applies the selection and the outcome rules.
OUTCOME_REFERENCE: Final[Mapping[str, str]] = {
    "module": "tools.reversal_outcome.core",
    "function": "reversal_outcome",
    "path": "tools/reversal_outcome/core.py",
}
EVIDENCE_COMPUTATION_PHRASE: Final = "before the first result-bearing run"
#: The discovery of the reversal commit by the controller is part of recoveryMs, which
#: E04-AC12 judges, and no condition of validity: a controller that does not discover
#: the reversal leaves no span, and E04-AC12 not met.
CONTROLLER_DISCOVERY: Final = "controllerDiscovery"
CONTROLLER_DISCOVERY_MEMBERS: Final[Mapping[str, object]] = {
    "partOf": "recoveryMs",
    "judgedBy": RECOVERY_CRITERION,
    "validity": False,
    "notDiscovered": "not-met",
}
#: The validity criterion of the operator events of the reversal, and what it names.
REVERSAL_EVENTS_CRITERION: Final = "E04-AC2"
REVERSAL_EVENTS_NAMED: Final = (
    "detection-reviewed",
    "reversal-decided",
    "reversal-created",
    "reversal-accepted",
    "the reversal commit",
)
#: A reading or an instant of the controller: its resolved revision or sync state,
#: an argo reading, the instants that it sets, or the controller resolving,
#: reporting, discovering, syncing, reconciling, observing, or picking up a commit.
_CONTROLLER_WORD: Final = re.compile(
    r"\bresolvedRevision\b|\bsyncStatus\b|\bSynced\b|\bargo (?:reading|stream)s?\b"
    r"|\bcontrollerObserved\b|\bdesiredStateRestored\b|\bgitopsDiscoveryMs\b"
    r"|\b(?:controller|Argo\s+CD|Application)(?:'s)?\s+"
    r"(?:(?:must|should|shall|will|would|can|could|may|has|have|had|is|are|was|"
    r"to|then|first|never|not|does|did|do|fails|failed|eventually|always|also)"
    r"\s+){0,3}"
    r"(?:resolv|report|discover|sync|reconcil|observ|pick|detect|reach)\w*"
    r"|\b(?:discovery|resolution|reconciliation|observation|detection)s?\s+by\s+"
    r"(?:the\s+)?(?:controller|Application|Argo\s+CD)\b"
    r"|\b(?:not|never)\s+(?:be\s+|been\s+)?(?:discovered|reconciled|synced|detected)\b",
    re.IGNORECASE,
)
#: The instants and the states that only the controller sets: one of them in a
#: condition of validity is a controller condition whatever else the sentence names.
#: A whole sentence, to its full stop: a verdict in a clause after a semicolon
#: still belongs to the controller reading before it.
_FULL_SENTENCE_END: Final = re.compile(r"(?<=[.])\s+|\n+")
_CONTROLLER_INSTANT: Final = re.compile(
    r"\bcontrollerObserved\b|\bdesiredStateRestored\b|\bgitopsDiscoveryMs\b"
    r"|\bsyncStatus\b|\bSynced\b",
    re.IGNORECASE,
)
_REVERSAL_WORD: Final = re.compile(r"\breversal\b|\brevert|\bknown-good\b", re.I)
#: A verdict left not judged, an INCONCLUSIVE run, or an abort; naming an abort
#: condition is not an abort.
_EXCLUDING_WORD: Final = re.compile(
    r"\bnot (?:be )?judged\b|\bnot-judged\b|\bINCONCLUSIVE\b|\bABORTED\b"
    r"|\babort(?!\s+conditions?\b)",
    re.IGNORECASE,
)
#: The phrases of the definition of stabilizationOnset: those of the amended
#: definition, which rule set 3 also reads.
ONSET_PHRASES: Final = REVERSAL_PHRASES[(STABILIZATION_ONSET, "definition")]
#: The only reasons for which rule set 4 leaves E04-AC12 not judged.
RECOVERY_NOT_JUDGED_REASONS: Final = frozenset(
    {REVERSAL_START_UNCONFIRMED, "clock-bound-reached", "clock-reading-missing"}
)
#: The phrases of E04-AC12 and of the outcome rules for a run with no span after
#: reversalStart that completes, and of each member of the selected span.
UNMET_RECOVERY: Final = (
    "When reversalStart is established and no span that starts after it completes "
    "inside the observation limit"
)
NOT_MET: Final = "not met"
SELECTED_SPAN: Final = "the selected span"
ANALYSIS_SPAN: Final = "the analysis states a stabilized recovery"
BOTH_WAYS_PHRASE: Final = "resolved both ways"
#: A reason that a sentence names, registered or not.
_FOR_THE_REASON: Final = re.compile(r"\bfor the reason ([a-z0-9]+(?:-[a-z0-9]+)+)")
#: A sentence that names reversalStart, an instant or a span earlier than it, and a
#: verdict that is not judged or a run that is INCONCLUSIVE, states the onset
#: exclusion in another form. A reason of the timing names reversalStart or the onset.
_EARLY_WORD: Final = re.compile(
    r"\b(?:before|precedes?|preceded|preceding|earlier than|not after|"
    r"(?:does|do|did) not (?:follow|start after|come after))\b",
    re.IGNORECASE,
)
_VERDICT_WORD: Final = re.compile(r"\bnot (?:be )?judged\b|\bINCONCLUSIVE\b")
_TIMING_WORD: Final = re.compile(r"\breversalStart\b|\bstabilizationOnset\b|\bonset\b")
#: A statement of the onset exclusion that does not name its reason: a verdict that
#: is left not judged because the onset or a span does not follow reversalStart.
_ONSET_EXCLUSION: Final = re.compile(
    r"\b(?:stabilizationOnset|onset|span)\b[^.;\n]*?\b(?:does|do|did)\s+not\s+"
    r"(?:follow|start after|come after)",
    re.IGNORECASE,
)

#: Text that rule set 2 refuses. A sentence that states that the difference of
#: the clocks is not measured contradicts P8. A sentence that orders instants by a
#: time and does not name the margin of rule set 2 contradicts the ordering rule.
#: A sentence that names synchronization or a guarantee and holds no negation
#: claims one. A sentence that makes every run INCONCLUSIVE contradicts the rule
#: for a verdict that is not judged. Each pattern reads words, so a paraphrase
#: that it does not name is not refused.
_NOT_MEASURED: Final = re.compile(
    r"\b(?:differences?|offsets?|skews?)\b[^.;\n]*?\b(?:not|never)\b[^.;\n]{0,20}?"
    r"\bmeasured\b"
    r"|\bunmeasured\b"
    r"|\bno measurement of the (?:clock )?(?:differences?|offsets?|skews?)\b",
    re.IGNORECASE,
)
_ORDER_WORD: Final = re.compile(
    r"\border(?:ed|ing|s)?\b|\bprecede[sd]?\b", re.IGNORECASE
)
_TIME_QUANTITY: Final = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|"
    r"twenty|thirty|sixty|\d[\d,]*(?:\.\d+)?)\s*"
    r"(?:seconds?|s|ms|milliseconds?|minutes?|min|hours?|h)\b",
    re.IGNORECASE,
)
#: The margin of rule set 2 in a sentence. Naming the clock bound alone is not
#: enough to exempt a sentence that orders instants by a time.
_MARGIN_PHRASE: Final = re.compile(
    r"\bthe clock bound of the run plus the coarser resolution\b", re.IGNORECASE
)
_EVERY_RUN_INCONCLUSIVE: Final = re.compile(
    r"\b(?:every|each|any|all)\s+runs?\b[^.;\n]*\bINCONCLUSIVE\b"
    r"|\balways\s+INCONCLUSIVE\b"
)
_CLAIM_WORD: Final = re.compile(r"\bsynchroni[sz]\w*|\bguarantee\w*", re.IGNORECASE)
_NEGATION: Final = re.compile(
    r"\b(?:not|no|never|nothing|neither|nor|without)\b", re.IGNORECASE
)
_SENTENCE_END: Final = re.compile(r"(?<=[.;])\s+|\n+")


@dataclass(frozen=True)
class Finding:
    """One way a record breaks a rule."""

    rule_id: str
    record: str
    location: str
    detail: str


#: Each rule, with its statement, in report order.
RULES: Final[Mapping[str, str]] = {
    "prereg-record-missing": (
        "Each of the five experiments has a committed freeze record in its directory, "
        "and the record names that experiment."
    ),
    "prereg-record-shape": (
        "A record answers each field that this check reads with one value, and each "
        "member that it reads has the type that the check reads."
    ),
    "prereg-qualification-incompatible": (
        "The qualification that a record names is committed with the stated digest, "
        "is QUALIFIED, and states the provider, the environment digest, the identity "
        "revision, the server version, the node count, the freeze record, and the "
        "release that the record states."
    ),
    "prereg-bounds-stale": (
        "The bound record that a record names is the latest committed one, has the "
        "stated digest, and states the four bounds of the record with the same names, "
        "formulas, and values."
    ),
    "prereg-bounds-incompatible": (
        "The bound record states the environment, the qualification, and the release "
        "that the record states."
    ),
    "prereg-criterion-bound-unknown": (
        "A criterion that names a bound names a bound of the record and states its "
        "value as a whole figure in milliseconds."
    ),
    "prereg-reconciliation-bound-differs": (
        "The reconciliation bound of V2-E05 is the sum of its three registered "
        "components."
    ),
    "prereg-shared-differs": (
        "The five records state one environment, one caller profile, one intended "
        "level, and one bound record with its bounds. Every record of rule set 2 "
        "states one clock policy. V2-E02A and V2-E02B state every shared field, "
        "definition, clock policy, validity criterion with its clocks, and exclusion "
        "reason alike."
    ),
    "prereg-baseline-difference-unpermitted": (
        "The topology of V2-E02A differs from that of V2-E02B only in the permitted "
        "members. The replica counts and the release of each side are those of the "
        "committed COMPARABLE baseline comparison and of the pinned desired-state "
        "files, and each disruption budget is the one the chart renders for its "
        "replica count."
    ),
    "prereg-target-topology-differs": (
        "V2-E02C, V2-E04, and V2-E05 state the topology of V2-E02B."
    ),
    "prereg-executable-unpinned": (
        "A record lists at least one executable, each is a pinned input, the entry "
        "file of a tool has its entry module in the material scope, and the scope "
        "names this check, the record's procedure directory, the qualification, and "
        "the bound record."
    ),
    "prereg-exclusion-reasons-unsupported": (
        "A record registers exclusion reasons for its own experiment, in the form "
        "that the aggregate reads."
    ),
    "prereg-rule-set-unknown": (
        "A revision-1 record of V2-S6-003-PR1 states no rule set and is read under "
        "rule set 1. Every other record states a rule set of 2 or later that this "
        "check knows, a V2-E04 record after revision 1 states rule set 3 or later, "
        "and a V2-E04 record after revision 2 states rule set 4 or later."
    ),
    "prereg-clock-inventory": (
        "A record of rule set 2 states the node clock and the host clock, and each "
        "instant source with the clock and the resolution of rule set 2. Each "
        "criterion entry of definition.criterionClocks names a criterion of the "
        "record and two instants, each with a source and a clock of the inventory, "
        "and is cross-clock exactly when the inventory puts its sources on two "
        "clocks. Each criterion declares clocks or is listed in "
        "definition.criteriaWithoutClocks, and not both. Each criterion that names a "
        "bound declares the clocks of its interval."
    ),
    "prereg-clock-measurement": (
        "A record of rule set 2 has a P8 that reads the clocks before the runner "
        "starts and after the window ends and states the bound formula of revision "
        "1, and its clock policy measures with P8, a start and an end reading of "
        "three instants, and the bound formula and the computation of rule set 2."
    ),
    "prereg-clock-rules": (
        "The clock policy of a record of rule set 2 states the offset-stability "
        "assumption, refuses a run with an unusable start reading before the fault, "
        "leaves the bound not computable after an unusable end reading with the state "
        "that the rule for a verdict that is not judged decides, applies that rule of "
        "rule set 2, and orders and compares instants of two clocks with the margin "
        "and the words of rule set 2."
    ),
    "prereg-clock-reasons": (
        "A record of rule set 2 registers clock-reading-missing and "
        "clock-bound-reached for INCONCLUSIVE, and its outcome rules name both."
    ),
    "prereg-clock-contradiction": (
        "No text of a record of rule set 2 states that the clock difference is not "
        "measured, orders instants by a time in a sentence that does not name the "
        "margin of rule set 2, names synchronization or a guarantee in a sentence "
        "with no negation, or states that every run is INCONCLUSIVE, in the phrases "
        "that this check names."
    ),
    "prereg-reversal-instants": (
        "A V2-E04 record of rule set 3 or 4 names reversalStart, controllerObserved, "
        "desiredStateRestored, stabilizationOnset, and stabilizedAt, each with its "
        "source and clock. reversalStart is the Git-visibility instant of an operator "
        "event, bracketed and judged at the earlier end, and it leaves E04-AC12 not "
        "judged when it is not established. stabilizedAt lies inside the observation "
        "limit, and recoveryEnd is stabilizationOnset. The definition of reversalStart "
        "and its two bracket ends hold the phrases that this check names. Under rule "
        "set 3, stabilizationOnset is also read from "
        "stabilizedRecovery.span.first.finishedAt of a span that completed, and follows "
        "reversalStart, stabilizedAt is read from stabilizedRecovery.stabilizedAt, and "
        "the definition of stabilizationOnset holds the phrases that this check names. "
        "No other prose is read."
    ),
    "prereg-reversal-intervals": (
        "A V2-E04 record of rule set 3 or 4 states recoveryMs from reversalStart to "
        "stabilizationOnset, judged by E04-AC12, gitopsDiscoveryMs from reversalStart "
        "to controllerObserved, and operatorDecisionMs from detection-reviewed to "
        "reversalStart, each reported, and keeps the instants of the four operator "
        "events of the reversal."
    ),
    "prereg-reversal-criteria": (
        "In a V2-E04 record of rule set 3 or 4, E04-AC12 judges recoveryMs against "
        "reversal_recovery_bound_ms with the value, the formula, and the bound record "
        "of derivedNumericBounds, and declares that interval cross-clock, from "
        "reversalStart on the host clock to stabilizationOnset on the node clock. "
        "E04-AC8 ends its window at desiredStateRestored. Each of the two criteria is "
        "stated once."
    ),
    "prereg-reversal-reasons": (
        "A V2-E04 record of rule set 3 registers reversal-start-unconfirmed and "
        "recovery-onset-not-after-reversal for INCONCLUSIVE, and its outcome rules "
        "name both. A V2-E04 record of rule set 4 registers reversal-start-unconfirmed "
        "for INCONCLUSIVE, and its outcome rules name it."
    ),
    "prereg-reversal-selection": (
        "A V2-E04 record of rule set 4 selects the span of E04-AC12 in "
        "definition.reversalTiming.selection: the candidates are the caller "
        "completions after reversalStart, the span rule is _find_span of "
        "tools/reliability_analysis, unchanged, with 10 successes over 60,000 ms, "
        "stabilizationOnset is the first and stabilizedAt the last request of the "
        "first span that it finds, inside the observation limit of 1,680,000 ms after "
        "fault-injection-finished, which definition.observation states, and a span or "
        "the part of a span that starts before reversalStart is never selected and "
        "never a reason for a verdict. The order of a candidate and reversalStart, and "
        "that of stabilizedAt and the end of the observation limit, are each resolved "
        "both ways inside the margin, and different verdicts leave E04-AC12 not "
        "judged, for clock-bound-reached, with the state that "
        "definition.clockPolicy.notJudged decides. The reported span is that of the "
        "resolution that counts only the completions ordered after reversalStart, and "
        "otherwise that of the other one. An unusable end reading leaves not judged "
        "only the verdicts that depend on the bound, and with no span that completes "
        "the criterion is not met. stabilizationOnset names the selection and no "
        "member of the run analysis, and its definition holds the phrases that this "
        "check names. The rule reads these members and the named phrases, and no "
        "other prose."
    ),
    "prereg-reversal-onset-exclusion": (
        "A V2-E04 record of rule set 4 registers no recovery-onset-not-after-reversal, "
        "names it in no outcome rule, criterion, criterion clock, or member of the "
        "reversal timing, and has no notAfterReversalStart member. No member that "
        "names E04-AC12 and a not-judged verdict, no registered reason that names "
        "E04-AC12 not judged, and no reason that an outcome rule names for E04-AC12 "
        "not judged is other than reversal-start-unconfirmed, clock-bound-reached, or "
        "clock-reading-missing, and no registered reason other than "
        "reversal-start-unconfirmed names reversalStart or the onset. No outcome rule, "
        "criterion, criterion clock, text of the reversal timing, observation limit, "
        "or post-recovery window states that the onset or a span does not follow "
        "reversalStart, or names reversalStart, an earlier instant or span, and a "
        "verdict that is not judged or an INCONCLUSIVE run in one sentence, in the "
        "words that this check names. No criterion clock of E04-AC12 orders "
        "stabilizationOnset, and each order of E04-AC12 is resolved both ways. A "
        "paraphrase that no named word reaches is not refused."
    ),
    "prereg-reversal-unmet-recovery": (
        "In a V2-E04 record of rule set 4, E04-AC12 is a pass criterion, and it and "
        "the outcome rules state that when reversalStart is established and no span "
        "that starts after it completes inside the observation limit, the criterion is "
        "not met. E04-AC12 states that it is not judged, for "
        "reversal-start-unconfirmed, when reversalStart is not established."
    ),
    "prereg-reversal-selected-span": (
        "In a V2-E04 record of rule set 4, stabilizedAt names the selection and no "
        "member of the run analysis, and the definitions of stabilizedAt, of the "
        "observation limit, and of the post-recovery window, and E04-AC5, a validity "
        "criterion, each name the selected span and not the stabilized recovery that "
        "the analysis states. The rule reads these members and the named "
        "phrases, and no other prose."
    ),
    "prereg-reversal-outcome-reference": (
        "A V2-E04 record of rule set 4 names the outcome reference, reversal_outcome "
        "of tools.reversal_outcome.core, in its selection, names that module in its "
        "material scope and pins its file, and states that code which computes the "
        "selection from the evidence of a run is pinned before the first "
        "result-bearing run. The rule reads these members and the named "
        "phrase, and no other prose."
    ),
    "prereg-reversal-controller-discovery": (
        "A V2-E04 record of rule set 4 states in "
        "definition.reversalTiming.controllerDiscovery that the discovery of the "
        "reversal commit by the controller is part of recoveryMs, judged by E04-AC12 "
        "and by no validity criterion, and that a controller that does not discover "
        "it leaves E04-AC12 not met. E04-AC2 is a validity criterion that names the "
        "four operator events of the reversal and the reversal commit, stated once, "
        "and each criterion clock of E04-AC2 orders operator events only. No sentence "
        "of a validity criterion, of a criterion clock of one, of an INCONCLUSIVE or "
        "ABORTED exclusion reason, or of an abort condition names a reading or an "
        "instant of the controller together with the reversal or the known-good "
        "revision, or names controllerObserved, desiredStateRestored, "
        "gitopsDiscoveryMs, or the sync state, and no sentence of the reversal "
        "timing, the outcome rules, the Git transitions, the fault procedure, the "
        "observation limit, the post-recovery window, the clock policy, the "
        "repetition rule, the preparation, the execution gate, a pass criterion, its "
        "criterion clocks, or another exclusion reason names one with a verdict that "
        "is not judged, an INCONCLUSIVE run, or an abort, in the words that this check "
        "names. A paraphrase that no named word reaches is not "
        "refused."
    ),
}


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def _contained(path: object) -> bool:
    """A relative POSIX repository path with no parent part and no backslash."""
    return (
        isinstance(path, str)
        and bool(path)
        and not PurePosixPath(path).is_absolute()
        and ".." not in PurePosixPath(path).parts
        and "\\" not in path
        and ":" not in path
    )


def _read(root: Path, path: object) -> tuple[bytes, Any] | None:
    """The bytes and the JSON value of a committed file, or None.

    A path that is not a relative repository path inside ``root`` is not read.
    """
    if not _contained(path):
        return None
    target = root / str(path)
    if not target.is_file():
        return None
    data = target.read_bytes()
    try:
        return data, json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return data, None


def record_revisions(
    root: Path = REPO_ROOT,
) -> dict[str, list[tuple[int, str, Any]]]:
    """Every committed revision of each experiment's record, by experiment identifier.

    The revisions of one experiment are in the order of their numbers, from the
    file names. The document of a file that is not JSON is None.
    """
    found: dict[str, list[tuple[int, str, Any]]] = {}
    paths = set(record_paths(root))
    for experiment in EXPERIMENTS:
        revisions: list[tuple[int, str, Any]] = []
        for path in sorted(paths):
            if PurePosixPath(path).parent.as_posix() != experiment.directory:
                continue
            match = RECORD_NAME.match(PurePosixPath(path).name)
            if match is None:
                continue
            read = _read(root, path)
            revisions.append(
                (int(match.group(1)), path, None if read is None else read[1])
            )
        if revisions:
            found[experiment.experiment_id] = sorted(revisions, key=lambda r: r[0])
    return found


def latest_records(root: Path = REPO_ROOT) -> dict[str, tuple[str, Any]]:
    """The latest revision of each experiment's record, by experiment identifier."""
    return {
        key: (revisions[-1][1], revisions[-1][2])
        for key, revisions in record_revisions(root).items()
    }


def _value(document: Mapping[str, Any], field: str) -> Any:
    """The value of the one entry of a field, or None when it has no such entry."""
    entries = _member(document, "fields").get(field)
    if not isinstance(entries, list) or len(entries) != 1:
        return None
    entry = entries[0]
    if not isinstance(entry, Mapping) or entry.get("status") != "value":
        return None
    return entry.get("value")


def _member(value: Any, name: str) -> Mapping[str, Any]:
    """The member ``name`` of ``value`` when both are objects, or an empty one."""
    if not isinstance(value, Mapping):
        return {}
    member = value.get(name)
    return member if isinstance(member, Mapping) else {}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _normalised(value: Any, experiment: Experiment) -> Any:
    """``value`` with the identifiers of its experiment replaced by fixed words.

    Two records of one comparison name their own directory, experiment, and run
    identifiers. Each is replaced where it is a whole token: not after a letter, a
    digit, or a hyphen, and, for an experiment or a directory, not before a letter
    or a digit. The comparison reads every other character. A text that names
    both experiments of the comparison is normalised for its own record only, so
    it reads as a difference: no shared text of the records does so.
    """
    text = _canonical(value)
    for actual, word in (
        (experiment.directory, "<directory>"),
        (experiment.experiment_id, "<experiment>"),
    ):
        text = re.sub(
            rf"(?<![A-Za-z0-9-]){re.escape(actual)}(?![A-Za-z0-9])", word, text
        )
    text = re.sub(
        rf"(?<![A-Za-z0-9-]){re.escape(experiment.run_prefix)}-", "<run>-", text
    )
    return json.loads(text)


def _pins(document: Mapping[str, Any]) -> dict[str, str]:
    pinned = document.get("pinnedInputs")
    if not isinstance(pinned, list):
        return {}
    return {
        item["path"]: item["sha256"]
        for item in pinned
        if isinstance(item, Mapping)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("sha256"), str)
    }


# --------------------------------------------------------------------------
# One record against its sources
# --------------------------------------------------------------------------


#: The members of an environment that this check reads, with the type of each.
_ENVIRONMENT_TYPES: Final[Mapping[str, type]] = {
    "provider": str,
    "environmentSha256": str,
    "identityRevision": int,
    "kubernetesServerVersion": str,
    "nodeCount": int,
    "qualification": dict,
    "qualificationFreezeRecord": dict,
    "qualifiedRelease": str,
}
_QUALIFICATION_MEMBERS: Final = ("qualificationId", "path", "contentSha256", "result")
_REFERENCE_MEMBERS: Final = frozenset({"path", "contentSha256"})
_BOUND_TYPES: Final[Mapping[str, type]] = {"name": str, "formula": str, "valueMs": int}
_BOUND_COUNT: Final = 4
#: The members of a release that are objects. The others are strings.
_RELEASE_OBJECTS: Final = frozenset({"contract", "desiredStateFiles"})


def _typed(value: Any, kind: type) -> bool:
    """``value`` is of ``kind``. A bool is not an int, and an object is a Mapping."""
    if kind is int:
        return type(value) is int
    if kind is dict:
        return isinstance(value, Mapping)
    return isinstance(value, kind)


def _reference(value: Any) -> bool:
    return isinstance(value, Mapping) and all(
        isinstance(value.get(member), str) and value.get(member)
        for member in _REFERENCE_MEMBERS
    )


def _strings(value: Any, *, empty: bool = False) -> bool:
    """``value`` is a list of non-empty strings, and not empty unless permitted."""
    return (
        isinstance(value, list)
        and (empty or bool(value))
        and all(isinstance(item, str) and item for item in value)
    )


def _budget(value: Any) -> bool:
    if not isinstance(value, Mapping) or type(value.get("rendered")) is not bool:
        return False
    return not value["rendered"] or type(value.get("minAvailable")) is int


def _shape_problem(document: Any, rule_set: int = RULE_SET_ONE) -> str | None:
    """Why a record cannot be read by this check, or None.

    Every member that a later step indexes or compares is held to its type here,
    so a malformed record gives a finding and not an error. The clock rules read
    the members of the clock policy with a type test each, and use only a string as
    a key, so a member of the wrong type is a finding of its rule.
    """
    problem = _shape_one(document)
    if problem is not None or rule_set < CLOCK_RULE_SET:
        return problem
    definition = document["definition"]
    if not isinstance(definition.get("clockPolicy"), Mapping) or not isinstance(
        definition.get("criterionClocks"), list
    ):
        return "definition states no clock policy and no criterion clocks"
    if not _strings(definition.get("preparation")) or not _strings(
        definition.get("outcomeRules")
    ):
        return "definition states no preparation steps and no outcome rules"
    if not isinstance(_member(document, "exclusionReasons").get("reasons"), list):
        return "the record registers no list of exclusion reasons"
    # Rule set 3 and rule set 4 each read the reversal timing as an object. This
    # gate requires that alone, so rule set 4 inherits no onset rule from it.
    if (
        rule_set >= REVERSAL_RULE_SET
        and _member(document, "metadata").get("experiment") == REVERSAL_EXPERIMENT
        and not isinstance(definition.get("reversalTiming"), Mapping)
    ):
        return "definition states no reversal timing"
    return None


def _shape_one(document: Any) -> str | None:
    """Why a record cannot be read under rule set 1, or None."""
    if not isinstance(document, Mapping):
        return "the record is not one JSON object"
    if not isinstance(document.get("fields"), Mapping) or not isinstance(
        document.get("metadata"), Mapping
    ):
        return "the record states no fields object and no metadata object"
    environment = _value(document, "environmentIdentity")
    if not isinstance(environment, Mapping) or not all(
        _typed(environment.get(member), kind)
        for member, kind in _ENVIRONMENT_TYPES.items()
    ):
        return "environmentIdentity states no environment in the form read here"
    if not all(
        isinstance(environment["qualification"].get(member), str)
        for member in _QUALIFICATION_MEMBERS
    ) or not _reference(environment["qualificationFreezeRecord"]):
        return "the qualification is not named by identifier, path, digest, and result"
    bounds = _value(document, "derivedNumericBounds")
    if (
        not isinstance(bounds, Mapping)
        or not _reference(bounds.get("boundRecord"))
        or not isinstance(bounds.get("bounds"), list)
        or len(bounds["bounds"]) != _BOUND_COUNT
        or not all(
            isinstance(b, Mapping)
            and all(_typed(b.get(m), kind) for m, kind in _BOUND_TYPES.items())
            for b in bounds["bounds"]
        )
    ):
        return "derivedNumericBounds names no bound record and no four bounds"
    topology = _value(document, "topology")
    release = _member(topology, "release")
    if (
        set(release) != RELEASE_MEMBERS
        or not all(
            isinstance(release[m], str) for m in RELEASE_MEMBERS - _RELEASE_OBJECTS
        )
        or not _reference(release["contract"])
        or not isinstance(release["desiredStateFiles"], Mapping)
        or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in release["desiredStateFiles"].items()
        )
    ):
        return "topology states no release in the form read here"
    if (
        type(topology.get("apiReplicas")) is not int
        or type(topology.get("runtimeReplicas")) is not int
        or not _budget(topology.get("apiDisruptionBudget"))
        or not _budget(topology.get("runtimeDisruptionBudget"))
    ):
        return "topology states no replica counts and disruption budgets in the form read here"
    definition = document.get("definition")
    if not isinstance(definition, Mapping) or not _strings(
        definition.get("executables")
    ):
        return "definition lists no executables"
    criteria = _value(document, "acceptanceCriteria")
    if not isinstance(criteria, list) or not all(
        isinstance(c, Mapping) and isinstance(c.get("bound", ""), str) for c in criteria
    ):
        return "acceptanceCriteria is not a list of criteria"
    scope = document.get("materialScope")
    if (
        not isinstance(scope, Mapping)
        or not _strings(scope.get("paths"))
        or not _strings(scope.get("entryModules"))
    ):
        return "materialScope names no paths and no entry modules"
    if not isinstance(document.get("exclusionReasons"), Mapping):
        return "the record registers no exclusion reasons"
    return None


def _qualification_findings(
    name: str, document: Mapping[str, Any], root: Path, target_release: str | None
) -> Iterator[Finding]:
    rule = "prereg-qualification-incompatible"
    environment = _value(document, "environmentIdentity")
    named = environment["qualification"]
    where = "fields.environmentIdentity"
    read = _read(root, str(named["path"]))
    if read is None or read[1] is None:
        yield Finding(rule, name, where, "the qualification is not committed")
        return
    data, record = read
    if content_digest(data) != named["contentSha256"]:
        yield Finding(rule, name, where, "the qualification has another digest")
    if not isinstance(record, Mapping):
        yield Finding(rule, name, where, "the qualification is not one JSON object")
        return
    stated = record.get("environment") if isinstance(record, Mapping) else None
    identities = record.get("identities")
    collection = record.get("collection")
    stated = stated if isinstance(stated, Mapping) else {}
    identities = identities if isinstance(identities, Mapping) else {}
    collection = collection if isinstance(collection, Mapping) else {}
    nodes = stated.get("nodes")
    comparisons = (
        ("result", record.get("result"), QUALIFIED),
        ("the stated result", named["result"], QUALIFIED),
        (
            "qualificationId",
            collection.get("qualificationId"),
            named["qualificationId"],
        ),
        (
            "environmentSha256",
            record.get("environmentSha256"),
            environment["environmentSha256"],
        ),
        ("provider", stated.get("provider"), environment["provider"]),
        (
            "identityRevision",
            stated.get("identityRevision"),
            environment["identityRevision"],
        ),
        (
            "kubernetesServerVersion",
            stated.get("kubernetesServerVersion"),
            environment["kubernetesServerVersion"],
        ),
        (
            "nodeCount",
            len(nodes) if isinstance(nodes, list) else None,
            environment["nodeCount"],
        ),
        (
            "the freeze record",
            identities.get("freezeRecord"),
            environment["qualificationFreezeRecord"],
        ),
        (
            "the qualified release",
            identities.get("releaseId"),
            environment["qualifiedRelease"],
        ),
    )
    for label, actual, expected in comparisons:
        if _canonical(actual) != _canonical(expected):
            yield Finding(rule, name, where, f"{label} differs from the qualification")
    if target_release is not None and environment["qualifiedRelease"] != target_release:
        yield Finding(
            rule, name, where, "the qualified release is not the target release"
        )
    freeze = environment["qualificationFreezeRecord"]
    try:
        registry = load_registry(root)
    except ValueError:
        registry = {}
    if not isinstance(freeze, Mapping) or registry.get(
        str(freeze.get("path"))
    ) != freeze.get("contentSha256"):
        yield Finding(
            rule, name, where, "the qualification freeze record is not registered"
        )


def _latest_bound_record(root: Path) -> str | None:
    base = root / BOUNDS_DIR
    if not base.is_dir():
        return None
    numbered = sorted(
        (int(match.group(1)), f"{BOUNDS_DIR}/{path.name}")
        for path in base.iterdir()
        if path.is_file() and (match := BOUNDS_NAME.match(path.name)) is not None
    )
    return numbered[-1][1] if numbered else None


def _bound_findings(
    name: str,
    document: Mapping[str, Any],
    root: Path,
    target_release: str | None,
    *,
    current: bool = True,
) -> Iterator[Finding]:
    value = _value(document, "derivedNumericBounds")
    reference = value["boundRecord"]
    where = "fields.derivedNumericBounds"
    stale = "prereg-bounds-stale"
    # A superseded revision is not run, so it is not held to the latest bounds.
    if current and reference["path"] != _latest_bound_record(root):
        yield Finding(
            stale, name, where, "the bound record is not the latest committed"
        )
    read = _read(root, str(reference["path"]))
    if read is None or not isinstance(read[1], Mapping):
        yield Finding(stale, name, where, "the bound record is not committed")
        return
    data, record = read
    if content_digest(data) != reference["contentSha256"]:
        yield Finding(stale, name, where, "the bound record has another digest")
    if record.get("schema") != BOUNDS_SCHEMA:
        yield Finding(stale, name, where, "the named file is not a bound record")
        return
    stated = [(b["name"], b["formula"], b["valueMs"]) for b in value["bounds"]]
    committed = [
        (b.get("name"), b.get("formula"), b.get("valueMs"))
        for b in (
            record.get("bounds") if isinstance(record.get("bounds"), list) else []
        )
        if isinstance(b, Mapping)
    ]
    if _canonical(stated) != _canonical(committed):
        yield Finding(
            stale, name, where, "the bounds differ from those of the bound record"
        )
    incompatible = "prereg-bounds-incompatible"
    environment = _value(document, "environmentIdentity")
    bound_environment = record.get("environment")
    bound_environment = (
        bound_environment if isinstance(bound_environment, Mapping) else {}
    )
    qualification = environment["qualification"]
    for label, actual, expected in (
        ("provider", bound_environment.get("provider"), environment["provider"]),
        (
            "environmentSha256",
            bound_environment.get("environmentSha256"),
            environment["environmentSha256"],
        ),
        (
            "the qualification",
            bound_environment.get("qualification"),
            {
                "contentSha256": qualification["contentSha256"],
                "path": qualification["path"],
                "qualificationId": qualification["qualificationId"],
            },
        ),
        (
            "the release",
            bound_environment.get("releaseId"),
            environment["qualifiedRelease"],
        ),
        (
            "the source release",
            value.get("sourceRelease"),
            environment["qualifiedRelease"],
        ),
    ):
        if _canonical(actual) != _canonical(expected):
            yield Finding(incompatible, name, where, f"{label} differs")
    if (
        target_release is not None
        and bound_environment.get("releaseId") != target_release
    ):
        yield Finding(
            incompatible, name, where, "the bounds are not of the target release"
        )


def _bound_values(document: Mapping[str, Any]) -> dict[str, int]:
    value = _value(document, "derivedNumericBounds")
    values = {
        str(b["name"]): b["valueMs"]
        for b in value["bounds"]
        if isinstance(b.get("valueMs"), int)
    }
    reconciliation = value.get("reconciliationBound")
    if isinstance(reconciliation, Mapping) and isinstance(
        reconciliation.get("valueMs"), int
    ):
        values[str(reconciliation.get("name"))] = reconciliation["valueMs"]
    return values


def _states(statement: str, value: int) -> bool:
    """``statement`` states ``value`` as a whole figure in milliseconds, with commas.

    A figure inside a larger one, such as 20,000 ms inside 120,000 ms, is not it.
    The check does not read what the statement says about the figure.
    """
    figure = re.escape(f"{value:,} ms")
    return re.search(rf"(?<![0-9,]){figure}", statement) is not None


def _criterion_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    values = _bound_values(document)
    for index, criterion in enumerate(_value(document, "acceptanceCriteria")):
        if not isinstance(criterion, Mapping) or "bound" not in criterion:
            continue
        where = f"fields.acceptanceCriteria[0].value[{index}]"
        bound = criterion["bound"]
        if bound not in values:
            yield Finding(
                "prereg-criterion-bound-unknown",
                name,
                where,
                "it names no bound of the record",
            )
        elif not _states(str(criterion.get("statement")), values[bound]):
            yield Finding(
                "prereg-criterion-bound-unknown",
                name,
                where,
                f"its statement does not state {values[bound]:,} ms",
            )


def _reconciliation_findings(
    name: str, experiment: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    reconciliation = _value(document, "derivedNumericBounds").get("reconciliationBound")
    where = "fields.derivedNumericBounds.reconciliationBound"
    rule = "prereg-reconciliation-bound-differs"
    if experiment != RECONCILIATION_EXPERIMENT:
        if reconciliation is not None:
            yield Finding(
                rule, name, where, "only V2-E05 states a reconciliation bound"
            )
        return
    if not isinstance(reconciliation, Mapping):
        yield Finding(rule, name, where, "V2-E05 states no reconciliation bound")
        return
    components = reconciliation.get("components")
    if (
        reconciliation.get("name") != RECONCILIATION_BOUND
        or _canonical(components) != _canonical(dict(RECONCILIATION_COMPONENTS))
        or reconciliation.get("valueMs") != sum(RECONCILIATION_COMPONENTS.values())
    ):
        yield Finding(
            rule, name, where, "the bound is not the sum of its registered components"
        )


def _executable_findings(
    name: str, experiment: Experiment, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-executable-unpinned"
    pins = _pins(document)
    scope = _member(document, "materialScope")
    paths: list[Any] = list(scope.get("paths", []))
    modules: list[Any] = list(scope.get("entryModules", []))
    for path in document["definition"]["executables"]:
        if path not in pins:
            yield Finding(rule, name, "definition.executables", f"{path} is not pinned")
        entry = _ENTRY_FILE.fullmatch(path)
        if entry is not None and f"tools.{entry.group(1)}.__main__" not in modules:
            yield Finding(
                rule,
                name,
                "materialScope.entryModules",
                f"the scope names no entry module for {path}",
            )
    environment = _value(document, "environmentIdentity")
    bounds = _value(document, "derivedNumericBounds")
    for required in (
        f"{experiment.directory}/procedure/*",
        environment["qualification"]["path"],
        bounds["boundRecord"]["path"],
    ):
        if required not in paths:
            yield Finding(
                rule, name, "materialScope.paths", f"the scope does not name {required}"
            )
    if ENTRY_MODULE not in modules:
        yield Finding(
            rule,
            name,
            "materialScope.entryModules",
            "the scope does not name this check",
        )


def _exclusion_findings(
    name: str, experiment: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-exclusion-reasons-unsupported"
    policy = document.get("exclusionReasons")
    problem = _reasons_problem(policy)
    if problem is not None:
        yield Finding(rule, name, "exclusionReasons", problem)
    elif _member(document, "exclusionReasons").get("experimentId") != experiment:
        yield Finding(
            rule, name, "exclusionReasons", "the reasons name another experiment"
        )


# --------------------------------------------------------------------------
# The clock rules of rule set 2
# --------------------------------------------------------------------------


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _clock_policy(document: Mapping[str, Any]) -> Mapping[str, Any]:
    return _member(document["definition"], "clockPolicy")


def _inventory_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "prereg-clock-inventory"
    policy = _clock_policy(document)
    definition = document["definition"]
    clocks = policy.get("clocks")
    if not isinstance(clocks, list) or [
        c.get("id") if isinstance(c, Mapping) and _text(c.get("statement")) else None
        for c in clocks
    ] != list(CLOCKS):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.clocks",
            "the inventory does not state the node clock and the host clock, each "
            "with a statement",
        )
    # Only a string is used as a key, so a member of another type is a finding.
    sources = policy.get("sources")
    stated: dict[str, tuple[str, Any]] | None = None
    if isinstance(sources, list) and all(
        isinstance(s, Mapping)
        and isinstance(s.get("id"), str)
        and isinstance(s.get("clock"), str)
        and _text(s.get("statement"))
        for s in sources
    ):
        stated = {s["id"]: (s["clock"], s.get("resolutionMs")) for s in sources}
        if len(stated) != len(sources):
            stated = None
    if (
        stated is None
        or any(type(resolution) is not int for _, resolution in stated.values())
        or stated != dict(CLOCK_SOURCES)
    ):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.sources",
            "the sources are not those of rule set 2, each once with its clock, its "
            "resolution, and a statement",
        )
    criteria = _value(document, "acceptanceCriteria")
    identifiers = {
        c["id"] for c in criteria if isinstance(c.get("id"), str) and c.get("id")
    }
    declared: set[tuple[str, str]] = set()
    entered: set[str] = set()
    for index, entry in enumerate(definition["criterionClocks"]):
        where = f"definition.criterionClocks[{index}]"
        yield from _entry_findings(rule, name, where, entry, identifiers, declared)
        if isinstance(entry, Mapping) and isinstance(entry.get("criterion"), str):
            entered.add(entry["criterion"])
    without = definition.get("criteriaWithoutClocks")
    if not _strings(without, empty=True) or len(set(without)) != len(without):
        yield Finding(
            rule,
            name,
            "definition.criteriaWithoutClocks",
            "it is not a list of criterion identifiers, each once",
        )
        without = []
    for listed in without:
        if listed not in identifiers:
            yield Finding(
                rule,
                name,
                "definition.criteriaWithoutClocks",
                f"{listed} is not a criterion of the record",
            )
        elif listed in entered:
            yield Finding(
                rule,
                name,
                "definition.criteriaWithoutClocks",
                f"{listed} is listed as without clocks and declares clocks",
            )
    for index, criterion in enumerate(criteria):
        where = f"fields.acceptanceCriteria[0].value[{index}]"
        identifier = criterion.get("id")
        if not isinstance(identifier, str) or not identifier:
            yield Finding(rule, name, where, "it states no identifier")
            continue
        if identifier not in entered and identifier not in without:
            yield Finding(
                rule,
                name,
                where,
                "it declares no clocks and is not listed in "
                "definition.criteriaWithoutClocks",
            )
        if "bound" in criterion and (identifier, criterion["bound"]) not in declared:
            yield Finding(
                rule,
                name,
                where,
                "it names a bound and declares no clocks of its interval",
            )


def _entry_findings(
    rule: str,
    name: str,
    where: str,
    entry: Any,
    identifiers: set[str],
    declared: set[tuple[str, str]],
) -> Iterator[Finding]:
    """The findings of one criterion clock entry. ``declared`` gains its bound."""
    if not isinstance(entry, Mapping):
        yield Finding(rule, name, where, "the entry is not an object")
        return
    criterion = entry.get("criterion")
    if not isinstance(criterion, str) or criterion not in identifiers:
        yield Finding(rule, name, where, "it names no criterion of the record")
    comparison = entry.get("comparison")
    if (
        not isinstance(comparison, str)
        or comparison not in CLOCK_COMPARISONS
        or not _text(entry.get("statement"))
    ):
        yield Finding(
            rule,
            name,
            where,
            "it states no comparison, order or interval, and no statement",
        )
    instants = entry.get("instants")
    if (
        not isinstance(instants, list)
        or len(instants) != 2
        or not all(
            isinstance(i, Mapping)
            and all(_text(i.get(member)) for member in ("instant", "source", "clock"))
            for i in instants
        )
    ):
        yield Finding(
            rule,
            name,
            where,
            "it does not state two instants, each with a source and a clock",
        )
        return
    # Whether an entry is cross-clock is read from the inventory clock of each
    # source, so a clock stated wrongly does not make an entry same-clock.
    clocks: list[str] = []
    for instant in instants:
        clock, source = instant["clock"], instant["source"]
        clocks.append(CLOCK_SOURCES[source][0] if source in CLOCK_SOURCES else clock)
        if clock not in CLOCKS:
            yield Finding(
                rule,
                name,
                where,
                f"it names the clock {clock}, which the inventory does not hold",
            )
        elif source not in CLOCK_SOURCES:
            yield Finding(
                rule,
                name,
                where,
                f"it names the source {source}, which the inventory does not hold",
            )
        elif CLOCK_SOURCES[source][0] != clock:
            yield Finding(
                rule,
                name,
                where,
                f"it puts the source {source} on the {clock} clock, and the inventory "
                f"puts it on the {CLOCK_SOURCES[source][0]} clock",
            )
    cross = entry.get("crossClock")
    two_clocks = clocks[0] != clocks[1]
    if type(cross) is not bool:
        yield Finding(
            rule, name, where, "it does not declare whether it is cross-clock"
        )
    elif cross and not two_clocks:
        yield Finding(
            rule,
            name,
            where,
            "it is declared cross-clock, and its instants are on one clock",
        )
    elif not cross and two_clocks:
        yield Finding(
            rule,
            name,
            where,
            "it is declared same-clock, and its instants are on two clocks",
        )
    bound = entry.get("bound")
    if (
        comparison == "interval"
        and isinstance(criterion, str)
        and isinstance(bound, str)
    ):
        declared.add((criterion, bound))
    elif "bound" in entry:
        yield Finding(
            rule,
            name,
            where,
            "it names a bound and is not an interval of one criterion",
        )


def _measurement_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "prereg-clock-measurement"
    steps = [s for s in document["definition"]["preparation"] if s.startswith("P8. ")]
    if len(steps) != 1:
        yield Finding(
            rule, name, "definition.preparation", "the preparation has no one step P8"
        )
    else:
        step = steps[0]
        if (
            "before the runner starts" not in step
            or "after the window ends" not in step
        ):
            yield Finding(
                rule,
                name,
                "definition.preparation",
                "P8 does not read the clocks before the runner starts and after the "
                "window ends",
            )
        if CLOCK_BOUND_FORMULA not in step:
            yield Finding(
                rule,
                name,
                "definition.preparation",
                "P8 does not state the bound formula of revision 1",
            )
    policy = _clock_policy(document)
    measurement = _member(policy, "measurement")
    when = _member(measurement, "when")
    if (
        measurement.get("step") != CLOCK_STEP
        or measurement.get("readings") != list(CLOCK_READINGS)
        or measurement.get("instants") != list(CLOCK_INSTANTS)
        or not all(_text(when.get(reading)) for reading in CLOCK_READINGS)
        or not _text(measurement.get("statement"))
    ):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.measurement",
            "the measurement is not P8, with a start and an end reading of three "
            "instants, each with its time",
        )
    bound = _member(policy, "bound")
    if (
        bound.get("formula") != CLOCK_BOUND_FORMULA
        or bound.get("computation") != CLOCK_BOUND_COMPUTATION
        or bound.get("unit") != "ms"
        or not _text(bound.get("conservative"))
    ):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.bound",
            "the bound is not the formula of revision 1 with the computation of rule "
            "set 2, in milliseconds, with the reason that it is conservative",
        )


def _rule_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "prereg-clock-rules"
    policy = _clock_policy(document)
    uncertainty = _member(policy, "uncertainty")
    if uncertainty.get("offsetStability") != OFFSET_STABILITY:
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.uncertainty",
            "it does not state the offset-stability assumption of rule set 2",
        )
    if not all(
        _text(uncertainty.get(member))
        for member in ("drift", "netChange", "notClaimed")
    ):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.uncertainty",
            "it does not state the drift, the net change of the offset, and what is "
            "not claimed",
        )
    missing = _member(policy, "missingReadings")
    start, end = _member(missing, "start"), _member(missing, "end")
    if not _text(missing.get("unusable")) or not (
        start.get("resultState") == "REFUSED"
        and start.get("reason") == "precondition-not-held"
        and start.get("faultInjected") is False
        and _text(start.get("statement"))
    ):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.missingReadings.start",
            "an unusable start reading does not refuse the run before the fault",
        )
    # The end reading names no state of its own: the rule for a verdict that is
    # not judged decides it.
    if (
        end.get("boundComputable") is not False
        or end.get("reason") != CLOCK_READING_MISSING
        or end.get("stateDecidedBy") != NOT_JUDGED_MEMBER
        or end.get("statement") != END_READING_RULE
        or "resultState" in end
    ):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.missingReadings.end",
            "an unusable end reading does not leave the bound not computable, under "
            f"{CLOCK_READING_MISSING}, with the state that {NOT_JUDGED_MEMBER} decides",
        )
    not_judged = _member(policy, "notJudged")
    if (
        not_judged.get("rule") != NOT_JUDGED_RULE
        or not_judged.get("decidedStateStands") is not True
    ):
        yield Finding(
            rule,
            name,
            "definition.clockPolicy.notJudged",
            "a verdict that is not judged does not follow the rule of rule set 2, in "
            "which a state that the judged verdicts decide stands",
        )
    for member, rules in (
        ("ordering", ORDERING_RULES),
        ("boundComparison", COMPARISON_RULES),
    ):
        stated = _member(policy, member)
        if (
            stated.get("margin") != CLOCK_MARGIN
            or stated.get("reason") != CLOCK_BOUND_REACHED
            or any(stated.get(key) != text for key, text in rules.items())
        ):
            yield Finding(
                rule,
                name,
                f"definition.clockPolicy.{member}",
                "it does not apply the margin of rule set 2 across the clocks, under "
                f"{CLOCK_BOUND_REACHED}",
            )


def _reason_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "prereg-clock-reasons"
    registered = {
        (r["id"], r["resultState"])
        for r in document["exclusionReasons"]["reasons"]
        if isinstance(r, Mapping)
        and isinstance(r.get("id"), str)
        and isinstance(r.get("resultState"), str)
    }
    outcome = " ".join(document["definition"]["outcomeRules"])
    for reason in (CLOCK_READING_MISSING, CLOCK_BOUND_REACHED):
        if (reason, INCONCLUSIVE) not in registered:
            yield Finding(
                rule,
                name,
                "exclusionReasons",
                f"{reason} is not registered for {INCONCLUSIVE}",
            )
        if re.search(rf"(?<![\w-]){re.escape(reason)}(?![\w-])", outcome) is None:
            yield Finding(
                rule,
                name,
                "definition.outcomeRules",
                f"the outcome rules do not name {reason}",
            )


def _strings_in(value: Any, location: str) -> Iterator[tuple[str, str]]:
    """Every string of ``value`` with its location. Member names are not read."""
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from _strings_in(item, f"{location}.{key}" if location else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings_in(item, f"{location}[{index}]")


def _contradictions(text: str) -> Iterator[str]:
    """The detail of each contradiction that one text states, once each."""
    found: list[str] = []
    if _NOT_MEASURED.search(text):
        found.append("it states that the clock difference is not measured")
    for sentence in _SENTENCE_END.split(text):
        if (
            _ORDER_WORD.search(sentence)
            and _TIME_QUANTITY.search(sentence)
            and not _MARGIN_PHRASE.search(sentence)
        ):
            found.append(
                "it states an ordering threshold that does not name the margin of "
                "rule set 2"
            )
        if _CLAIM_WORD.search(sentence) and not _NEGATION.search(sentence):
            found.append("it names synchronization or a guarantee with no negation")
        if _EVERY_RUN_INCONCLUSIVE.search(sentence):
            found.append("it states that every run is INCONCLUSIVE")
    yield from dict.fromkeys(found)


def _contradiction_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-clock-contradiction"
    scanned = {k: v for k, v in document.items() if k != "pinnedInputs"}
    for location, text in _strings_in(scanned, ""):
        for detail in _contradictions(text):
            yield Finding(rule, name, location, detail)


def _clock_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    """Every finding of the clock rules of rule set 2 for one record."""
    yield from _inventory_findings(name, document)
    yield from _measurement_findings(name, document)
    yield from _rule_findings(name, document)
    yield from _reason_findings(name, document)
    yield from _contradiction_findings(name, document)


# --------------------------------------------------------------------------
# The reversal-timing rules of rule set 3, for V2-E04
# --------------------------------------------------------------------------


def _timing(document: Mapping[str, Any]) -> Mapping[str, Any]:
    return _member(document["definition"], "reversalTiming")


def _instant_findings(
    name: str, document: Mapping[str, Any], rule_set: int = REVERSAL_RULE_SET
) -> Iterator[Finding]:
    """The findings of prereg-reversal-instants. Under rule set 3 every clause is
    read, in the order of revision 2. Under rule set 4 the clauses of the onset of
    the analysis are not, and the selection rules read the span instead."""
    rule = "prereg-reversal-instants"
    timing = _timing(document)
    instants = _member(timing, "instants")
    base = "definition.reversalTiming"
    for instant, source in REVERSAL_INSTANTS.items():
        stated = instants.get(instant)
        if (
            not isinstance(stated, Mapping)
            or stated.get("source") != source
            or stated.get("clock") != CLOCK_SOURCES[source][0]
            or not _text(stated.get("definition"))
        ):
            yield Finding(
                rule,
                name,
                f"{base}.instants.{instant}",
                f"{instant} is not stated with its definition, the source {source}, "
                f"and the {CLOCK_SOURCES[source][0]} clock",
            )
    start = _member(instants, REVERSAL_START)
    where = f"{base}.instants.{REVERSAL_START}"
    if start.get("kind") != GIT_VISIBILITY:
        yield Finding(
            rule,
            name,
            where,
            "reversalStart is not the Git-visibility instant: it is not stated as "
            f"{GIT_VISIBILITY}",
        )
    bracket = _member(start, "bracket")
    if start.get("judgedAt") != EARLIER or not all(
        _text(_member(bracket, end).get("instant"))
        and _member(bracket, end).get("source") == REVERSAL_INSTANTS[REVERSAL_START]
        for end in BRACKET_ENDS
    ):
        yield Finding(
            rule,
            name,
            where,
            "reversalStart is not bracketed by two operator-event instants and judged "
            "at the earlier end",
        )
    phrased = REVERSAL_PHRASES if rule_set == REVERSAL_RULE_SET else START_PHRASES
    for path, phrases in phrased.items():
        text: Any = instants
        for step in path:
            text = text.get(step) if isinstance(text, Mapping) else None
        missing = [p for p in phrases if not isinstance(text, str) or p not in text]
        if missing:
            yield Finding(
                rule,
                name,
                f"{base}.instants.{'.'.join(path)}",
                "it does not hold the phrases " + ", ".join(repr(p) for p in missing),
            )
    absent = _member(start, "notEstablished")
    if (
        absent.get("reason") != REVERSAL_START_UNCONFIRMED
        or absent.get("criterion") != RECOVERY_CRITERION
        or absent.get("verdict") != NOT_JUDGED_VERDICT
        or not _text(absent.get("statement"))
    ):
        yield Finding(
            rule,
            name,
            f"{where}.notEstablished",
            f"a reversalStart that is not established does not leave "
            f"{RECOVERY_CRITERION} not judged, for {REVERSAL_START_UNCONFIRMED}",
        )
    if rule_set != REVERSAL_RULE_SET:
        settled = _member(instants, STABILIZED_AT)
        if settled.get("insideObservationLimit") is not True:
            yield Finding(
                rule,
                name,
                f"{base}.instants.{STABILIZED_AT}",
                "stabilizedAt is not held inside the observation limit",
            )
        if timing.get("recoveryEnd") != STABILIZATION_ONSET:
            yield Finding(
                rule,
                name,
                f"{base}.recoveryEnd",
                "recoveryEnd is not stabilizationOnset, the onset of the span",
            )
        return
    onset = _member(instants, STABILIZATION_ONSET)
    where = f"{base}.instants.{STABILIZATION_ONSET}"
    if onset.get("analysisMember") != ANALYSIS_MEMBERS[STABILIZATION_ONSET]:
        yield Finding(
            rule,
            name,
            where,
            "stabilizationOnset is not read from "
            f"{ANALYSIS_MEMBERS[STABILIZATION_ONSET]}",
        )
    if onset.get("completedSpanOnly") is not True:
        yield Finding(
            rule,
            name,
            where,
            "stabilizationOnset is not held to a span that completed: an interrupted "
            "span could establish a recovery",
        )
    later = _member(onset, "notAfterReversalStart")
    if (
        onset.get("after") != REVERSAL_START
        or later.get("reason") != ONSET_NOT_AFTER_START
        or later.get("criterion") != RECOVERY_CRITERION
        or later.get("verdict") != NOT_JUDGED_VERDICT
        or not _text(later.get("statement"))
    ):
        yield Finding(
            rule,
            name,
            where,
            "stabilizationOnset is not held to follow reversalStart, with "
            f"{RECOVERY_CRITERION} not judged for {ONSET_NOT_AFTER_START} otherwise",
        )
    settled = _member(instants, STABILIZED_AT)
    if (
        settled.get("analysisMember") != ANALYSIS_MEMBERS[STABILIZED_AT]
        or settled.get("insideObservationLimit") is not True
    ):
        yield Finding(
            rule,
            name,
            f"{base}.instants.{STABILIZED_AT}",
            f"stabilizedAt is not read from {ANALYSIS_MEMBERS[STABILIZED_AT]} and held "
            "inside the observation limit",
        )
    if timing.get("recoveryEnd") != STABILIZATION_ONSET:
        yield Finding(
            rule,
            name,
            f"{base}.recoveryEnd",
            "recoveryEnd is not stabilizationOnset, the onset of the span",
        )


def _interval_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "prereg-reversal-intervals"
    timing = _timing(document)
    intervals = _member(timing, "intervals")
    base = "definition.reversalTiming"
    for interval, (start, end, judged) in REVERSAL_INTERVALS.items():
        stated = intervals.get(interval)
        criterion = RECOVERY_CRITERION if judged else None
        if (
            not isinstance(stated, Mapping)
            or stated.get("start") != start
            or stated.get("end") != end
            or stated.get("judged") is not judged
            or stated.get("criterion") != criterion
            or not _text(stated.get("statement"))
        ):
            role = f"judged by {RECOVERY_CRITERION}" if judged else "reported"
            yield Finding(
                rule,
                name,
                f"{base}.intervals.{interval}",
                f"{interval} is not stated from {start} to {end}, {role}",
            )
    if timing.get("operatorEvents") != list(REVERSAL_EVENTS):
        yield Finding(
            rule,
            name,
            f"{base}.operatorEvents",
            "the four operator events of the reversal are not kept with their own "
            "instants",
        )


def _reversal_criterion_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-reversal-criteria"
    listed = [
        (index, c)
        for index, c in enumerate(_value(document, "acceptanceCriteria"))
        if isinstance(c.get("id"), str)
    ]
    # A second criterion of one identifier would let a conforming copy hide a
    # defective one, so each of the two is stated once.
    for identifier in (RECOVERY_CRITERION, CONTAINMENT_CRITERION):
        count = sum(1 for _, c in listed if c["id"] == identifier)
        if count != 1:
            yield Finding(
                rule,
                name,
                "fields.acceptanceCriteria",
                f"{identifier} is stated {count} times, and not once",
            )
    criteria: dict[str, tuple[int | None, Mapping[str, Any]]] = {
        c["id"]: (index, c) for index, c in reversed(listed)
    }
    absent: tuple[int | None, Mapping[str, Any]] = (None, {})
    bounds = _value(document, "derivedNumericBounds")
    named = next((b for b in bounds["bounds"] if b["name"] == RECOVERY_BOUND), None)
    index, criterion = criteria.get(RECOVERY_CRITERION, absent)
    where = (
        "fields.acceptanceCriteria"
        if index is None
        else f"fields.acceptanceCriteria[0].value[{index}]"
    )
    if (
        criterion.get("bound") != RECOVERY_BOUND
        or criterion.get("interval") != RECOVERY_INTERVAL
        or named is None
    ):
        yield Finding(
            rule,
            name,
            where,
            f"{RECOVERY_CRITERION} does not judge {RECOVERY_INTERVAL} against "
            f"{RECOVERY_BOUND}",
        )
    else:
        for label, member, expected in (
            ("value", "boundValueMs", named["valueMs"]),
            ("formula", "boundFormula", named["formula"]),
            ("bound record", "boundRecord", bounds["boundRecord"]),
        ):
            if _canonical(criterion.get(member)) != _canonical(expected):
                yield Finding(
                    rule,
                    name,
                    where,
                    f"{RECOVERY_CRITERION} states another {label} of {RECOVERY_BOUND} "
                    "than derivedNumericBounds",
                )
    sources = [
        REVERSAL_INSTANTS[REVERSAL_START],
        REVERSAL_INSTANTS[STABILIZATION_ONSET],
    ]
    entries = [
        e
        for e in document["definition"]["criterionClocks"]
        if isinstance(e, Mapping)
        and e.get("criterion") == RECOVERY_CRITERION
        and e.get("comparison") == "interval"
    ]
    if len(entries) != 1 or not (
        entries[0].get("bound") == RECOVERY_BOUND
        and entries[0].get("crossClock") is True
        and isinstance(entries[0].get("instants"), list)
        and [
            i.get("source") if isinstance(i, Mapping) else None
            for i in entries[0]["instants"]
        ]
        == sources
    ):
        yield Finding(
            rule,
            name,
            "definition.criterionClocks",
            f"{RECOVERY_CRITERION} does not declare one cross-clock interval of "
            f"{RECOVERY_BOUND}, from reversalStart on the host clock to "
            "stabilizationOnset on the node clock",
        )
    index, criterion = criteria.get(CONTAINMENT_CRITERION, absent)
    statement = criterion.get("statement")
    if (
        _canonical(criterion.get("window")) != _canonical(dict(CONTAINMENT_WINDOW))
        or not isinstance(statement, str)
        or DESIRED_STATE_RESTORED not in statement
        or REVERSAL_START in statement
    ):
        yield Finding(
            rule,
            name,
            "fields.acceptanceCriteria"
            if index is None
            else f"fields.acceptanceCriteria[0].value[{index}]",
            f"{CONTAINMENT_CRITERION} does not end its window at "
            f"{DESIRED_STATE_RESTORED}",
        )


def _reversal_reason_findings(
    name: str,
    document: Mapping[str, Any],
    reasons: Sequence[str] = (REVERSAL_START_UNCONFIRMED, ONSET_NOT_AFTER_START),
) -> Iterator[Finding]:
    """The findings of prereg-reversal-reasons. Rule set 3 reads both reasons of
    the timing, and rule set 4 reads reversal-start-unconfirmed alone."""
    rule = "prereg-reversal-reasons"
    registered = {
        (r["id"], r["resultState"])
        for r in document["exclusionReasons"]["reasons"]
        if isinstance(r, Mapping)
        and isinstance(r.get("id"), str)
        and isinstance(r.get("resultState"), str)
    }
    outcome = " ".join(document["definition"]["outcomeRules"])
    for reason in reasons:
        if (reason, INCONCLUSIVE) not in registered:
            yield Finding(
                rule,
                name,
                "exclusionReasons",
                f"{reason} is not registered for {INCONCLUSIVE}",
            )
        if re.search(rf"(?<![\w-]){re.escape(reason)}(?![\w-])", outcome) is None:
            yield Finding(
                rule,
                name,
                "definition.outcomeRules",
                f"the outcome rules do not name {reason}",
            )


def _reversal_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    """Every finding of the reversal-timing rules of rule set 3 for one V2-E04
    record."""
    yield from _instant_findings(name, document)
    yield from _interval_findings(name, document)
    yield from _reversal_criterion_findings(name, document)
    yield from _reversal_reason_findings(name, document)


# --------------------------------------------------------------------------
# The selection rules of rule set 4, for V2-E04
# --------------------------------------------------------------------------


def _selection(document: Mapping[str, Any]) -> Mapping[str, Any]:
    return _member(_timing(document), SELECTION)


def _holds(text: Any, phrase: str) -> bool:
    return isinstance(text, str) and phrase in text


def _equal(stated: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    """Each member of ``expected`` is stated with its value, and of its type."""
    return all(
        _canonical(stated.get(key)) == _canonical(value)
        for key, value in expected.items()
    )


def _criteria_by_id(
    document: Mapping[str, Any],
) -> dict[str, tuple[int, Mapping[str, Any]]]:
    """Each criterion by identifier, with its index. The first of two is kept, and
    prereg-reversal-criteria refuses a second E04-AC12."""
    found: dict[str, tuple[int, Mapping[str, Any]]] = {}
    for index, criterion in enumerate(_value(document, "acceptanceCriteria")):
        identifier = criterion.get("id") if isinstance(criterion, Mapping) else None
        if isinstance(identifier, str) and identifier not in found:
            found[identifier] = (index, criterion)
    return found


def _criterion_at(index: int | None) -> str:
    return (
        "fields.acceptanceCriteria"
        if index is None
        else f"fields.acceptanceCriteria[0].value[{index}]"
    )


def _span_selection_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-reversal-selection"
    selection = _selection(document)
    where = f"{SELECTED_BY}"
    if not selection:
        yield Finding(rule, name, where, "the record states no selection of the span")
        return
    checks: tuple[tuple[str, bool, str], ...] = (
        (
            "candidates",
            _equal(_member(selection, "candidates"), SELECTION_CANDIDATES)
            and _text(_member(selection, "candidates").get("statement")),
            "the candidates are not the caller completions after reversalStart",
        ),
        (
            "spanRule",
            _equal(_member(selection, "spanRule"), SPAN_RULE)
            and _text(_member(selection, "spanRule").get("statement")),
            "the span rule is not _find_span of tools/reliability_analysis, "
            "unchanged, with 10 successes over 60,000 ms",
        ),
        (
            "onset",
            _member(selection, "onset").get("instant") == SELECTED_REQUESTS["onset"][0]
            and _member(selection, "onset").get("request")
            == SELECTED_REQUESTS["onset"][1],
            "stabilizationOnset is not the first request of the selected span",
        ),
        (
            "stabilizedAt",
            _member(selection, "stabilizedAt").get("instant")
            == SELECTED_REQUESTS["stabilizedAt"][0]
            and _member(selection, "stabilizedAt").get("request")
            == SELECTED_REQUESTS["stabilizedAt"][1],
            "stabilizedAt is not the last request of the selected span",
        ),
        (
            "observationLimit",
            _equal(_member(selection, "observationLimit"), OBSERVATION_LIMIT)
            and _holds(
                document["definition"].get("observation"), OBSERVATION_LIMIT_TEXT
            ),
            "the observation limit is not 1,680,000 ms after fault-injection-finished, "
            "as definition.observation states it",
        ),
        (
            "beforeReversalStart",
            _equal(_member(selection, "beforeReversalStart"), BEFORE_REVERSAL_START)
            and _text(_member(selection, "beforeReversalStart").get("statement")),
            "a span that starts before reversalStart is not held from the selection "
            "and from every verdict",
        ),
        (
            "verdicts",
            _equal(_member(selection, "verdicts"), {"differ": DIFFERENT_VERDICTS})
            and _text(_member(selection, "verdicts").get("statement")),
            "different verdicts of the resolutions do not leave E04-AC12 not judged, "
            "for clock-bound-reached, with the state that "
            "definition.clockPolicy.notJudged decides",
        ),
        (
            "reported",
            _equal(_member(selection, "reported"), REPORTED_SPAN)
            and _text(_member(selection, "reported").get("statement")),
            "the reported span is not that of the resolution that counts only the "
            "completions ordered after reversalStart",
        ),
        (
            "endReading",
            _equal(_member(selection, "endReading"), SELECTION_END_READING)
            and _text(_member(selection, "endReading").get("statement")),
            "an unusable end reading does not leave not judged only the verdicts that "
            "depend on the bound, with no completed span not met",
        ),
    )
    for member, held, detail in checks:
        if not held:
            yield Finding(rule, name, f"{where}.{member}", detail)
    orders = selection.get("orders")
    stated: dict[str, Any] = {}
    if isinstance(orders, list):
        for order in orders:
            identifier = order.get("id") if isinstance(order, Mapping) else None
            if isinstance(identifier, str):
                stated.setdefault(identifier, []).append(order)
    for identifier, resolutions in SELECTION_ORDERS.items():
        listed = stated.get(identifier, [])
        if len(listed) != 1 or not (
            listed[0].get("insideMargin") == BOTH_WAYS
            and listed[0].get("resolutions") == list(resolutions)
            and _text(listed[0].get("statement"))
        ):
            yield Finding(
                rule,
                name,
                f"{where}.orders",
                f"the order {identifier} is not stated once and resolved both ways "
                "inside the margin",
            )
    if not isinstance(orders, list) or set(stated) != set(SELECTION_ORDERS):
        yield Finding(
            rule,
            name,
            f"{where}.orders",
            "the orders are not exactly the two of the selection",
        )
    instants = _member(_timing(document), "instants")
    onset = _member(instants, STABILIZATION_ONSET)
    onset_at = f"definition.reversalTiming.instants.{STABILIZATION_ONSET}"
    if (
        onset.get("selectedBy") != SELECTED_BY
        or "analysisMember" in onset
        or onset.get("after") != REVERSAL_START
        or onset.get("completedSpanOnly") is not True
    ):
        yield Finding(
            rule,
            name,
            onset_at,
            "stabilizationOnset does not name the selection of a completed span after "
            "reversalStart, or names a member of the run analysis",
        )
    missing = [p for p in ONSET_PHRASES if not _holds(onset.get("definition"), p)]
    if missing:
        yield Finding(
            rule,
            name,
            f"{onset_at}.definition",
            "it does not hold the phrases " + ", ".join(repr(p) for p in missing),
        )


def _outside_history(document: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    """Every text that can state a rule of the record: the reversal timing, the
    criteria, the criterion clocks, the outcome rules, and the exclusion reasons.
    The history and the limitations may name what an earlier revision stated."""
    definition = document["definition"]
    yield from _strings_in(
        definition.get("reversalTiming"), "definition.reversalTiming"
    )
    yield from _strings_in(
        definition.get("criterionClocks"), "definition.criterionClocks"
    )
    yield from _strings_in(definition.get("outcomeRules"), "definition.outcomeRules")
    yield from _strings_in(
        _value(document, "acceptanceCriteria"), "fields.acceptanceCriteria[0].value"
    )
    yield from _strings_in(document.get("exclusionReasons"), "exclusionReasons")


def _not_judged_members(value: Any, location: str) -> Iterator[tuple[str, Any]]:
    """Each member that leaves E04-AC12 not judged, with the reason it states."""
    if isinstance(value, Mapping):
        if (
            value.get("criterion") == RECOVERY_CRITERION
            and value.get("verdict") == NOT_JUDGED_VERDICT
        ):
            yield location, value.get("reason")
        for key, item in value.items():
            yield from _not_judged_members(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _not_judged_members(item, f"{location}[{index}]")


def _onset_exclusion_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-reversal-onset-exclusion"
    reasons = [
        r for r in document["exclusionReasons"]["reasons"] if isinstance(r, Mapping)
    ]
    if any(r.get("id") == ONSET_NOT_AFTER_START for r in reasons):
        yield Finding(
            rule,
            name,
            "exclusionReasons",
            f"{ONSET_NOT_AFTER_START} is registered",
        )
    for location, text in _outside_history(document):
        if ONSET_NOT_AFTER_START in text:
            yield Finding(rule, name, location, f"it names {ONSET_NOT_AFTER_START}")
    for location, _ in _named(
        document["definition"], "notAfterReversalStart", "definition"
    ):
        yield Finding(rule, name, location, "it is a notAfterReversalStart member")
    for location, reason in _not_judged_members(
        {k: v for k, v in document.items() if k != "pinnedInputs"}, ""
    ):
        if not isinstance(reason, str) or reason not in RECOVERY_NOT_JUDGED_REASONS:
            yield Finding(
                rule,
                name,
                location.lstrip("."),
                f"it leaves {RECOVERY_CRITERION} not judged for another reason",
            )
    allowed = RECOVERY_NOT_JUDGED_REASONS | {ONSET_NOT_AFTER_START}
    for index, entry in enumerate(reasons):
        reason_id, reason_text = entry.get("id"), entry.get("reason")
        if (
            isinstance(reason_id, str)
            and reason_id not in allowed
            and isinstance(reason_text, str)
            and RECOVERY_CRITERION in reason_text
            and "not judged" in reason_text
        ):
            yield Finding(
                rule,
                name,
                f"exclusionReasons.reasons[{index}]",
                f"{reason_id} leaves {RECOVERY_CRITERION} not judged",
            )
    for index, entry in enumerate(reasons):
        reason_id, reason_text = entry.get("id"), entry.get("reason")
        if (
            isinstance(reason_id, str)
            and reason_id not in (REVERSAL_START_UNCONFIRMED, ONSET_NOT_AFTER_START)
            and isinstance(reason_text, str)
            and _TIMING_WORD.search(reason_text)
        ):
            yield Finding(
                rule,
                name,
                f"exclusionReasons.reasons[{index}]",
                f"{reason_id} is a reason of the reversal timing beside "
                f"{REVERSAL_START_UNCONFIRMED}",
            )
    registered = {r.get("id") for r in reasons if isinstance(r.get("id"), str)} | {
        ONSET_NOT_AFTER_START
    }
    rules = document["definition"]["outcomeRules"]
    for index, text in enumerate(rules):
        for sentence in _SENTENCE_END.split(text):
            if RECOVERY_CRITERION not in sentence or "not judged" not in sentence:
                continue
            named = {
                reason
                for reason in registered
                if re.search(rf"(?<![\w-]){re.escape(str(reason))}(?![\w-])", sentence)
            } | set(_FOR_THE_REASON.findall(sentence))
            if named - RECOVERY_NOT_JUDGED_REASONS:
                yield Finding(
                    rule,
                    name,
                    f"definition.outcomeRules[{index}]",
                    f"it leaves {RECOVERY_CRITERION} not judged for another reason",
                )
    definition = document["definition"]
    texts: list[tuple[str, Any]] = [
        (f"definition.outcomeRules[{i}]", r) for i, r in enumerate(rules)
    ]
    for index, criterion in enumerate(_value(document, "acceptanceCriteria")):
        if isinstance(criterion, Mapping):
            texts.append((_criterion_at(index), criterion.get("statement")))
    clocks = definition["criterionClocks"]
    for index, entry in enumerate(clocks):
        if isinstance(entry, Mapping):
            texts.append(
                (f"definition.criterionClocks[{index}]", entry.get("statement"))
            )
    texts.extend(
        _strings_in(definition.get("reversalTiming"), "definition.reversalTiming")
    )
    for member in ("observation", "postRecoveryWindow"):
        texts.append((f"definition.{member}", definition.get(member)))
    for location, text in texts:
        if not isinstance(text, str):
            continue
        if _ONSET_EXCLUSION.search(text) or any(
            REVERSAL_START in sentence
            and _EARLY_WORD.search(sentence)
            and _VERDICT_WORD.search(sentence)
            for sentence in _SENTENCE_END.split(text)
        ):
            yield Finding(
                rule,
                name,
                location,
                "it states that the onset or a span does not follow reversalStart",
            )
    for index, entry in enumerate(clocks):
        if not (
            isinstance(entry, Mapping)
            and entry.get("criterion") == RECOVERY_CRITERION
            and entry.get("comparison") == "order"
        ):
            continue
        instants = entry.get("instants")
        ends = [
            i.get("instant")
            for i in (instants if isinstance(instants, list) else [])
            if isinstance(i, Mapping)
        ]
        if any(isinstance(e, str) and e.startswith(STABILIZATION_ONSET) for e in ends):
            yield Finding(
                rule,
                name,
                f"definition.criterionClocks[{index}]",
                f"an order of {RECOVERY_CRITERION} orders stabilizationOnset",
            )
        if not _holds(entry.get("statement"), BOTH_WAYS_PHRASE):
            yield Finding(
                rule,
                name,
                f"definition.criterionClocks[{index}]",
                f"an order of {RECOVERY_CRITERION} is not resolved both ways",
            )


def _named(value: Any, member: str, location: str) -> Iterator[tuple[str, Any]]:
    """The location and the value of each member named ``member`` in ``value``."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            where = f"{location}.{key}"
            if key == member:
                yield where, item
            yield from _named(item, member, where)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _named(item, member, f"{location}[{index}]")


def _unmet_recovery_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-reversal-unmet-recovery"
    index, criterion = _criteria_by_id(document).get(RECOVERY_CRITERION, (None, {}))
    where = _criterion_at(index)
    if criterion.get("kind") != "pass":
        yield Finding(
            rule, name, where, f"{RECOVERY_CRITERION} is not a pass criterion"
        )
    statement = criterion.get("statement")
    if not (_holds(statement, UNMET_RECOVERY) and _holds(statement, NOT_MET)):
        yield Finding(
            rule,
            name,
            where,
            f"{RECOVERY_CRITERION} does not state that it is not met when no span that "
            "starts after reversalStart completes inside the observation limit",
        )
    if not (
        _holds(statement, "When reversalStart is not established")
        and _holds(statement, REVERSAL_START_UNCONFIRMED)
    ):
        yield Finding(
            rule,
            name,
            where,
            f"{RECOVERY_CRITERION} does not state that it is not judged, for "
            f"{REVERSAL_START_UNCONFIRMED}, when reversalStart is not established",
        )
    outcome = " ".join(document["definition"]["outcomeRules"])
    if not (
        UNMET_RECOVERY in outcome and f"{RECOVERY_CRITERION} is not met" in outcome
    ):
        yield Finding(
            rule,
            name,
            "definition.outcomeRules",
            f"the outcome rules do not state that {RECOVERY_CRITERION} is not met when "
            "no span that starts after reversalStart completes inside the observation "
            "limit",
        )


def _selected_span_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-reversal-selected-span"
    instants = _member(_timing(document), "instants")
    settled = _member(instants, STABILIZED_AT)
    where = f"definition.reversalTiming.instants.{STABILIZED_AT}"
    if (
        settled.get("selectedBy") != SELECTED_BY
        or "analysisMember" in settled
        or not _holds(settled.get("definition"), SELECTED_SPAN)
    ):
        yield Finding(
            rule,
            name,
            where,
            "stabilizedAt does not name the selected span, or names a member of the "
            "run analysis",
        )
    definition = document["definition"]
    for member in ("observation", "postRecoveryWindow"):
        text = definition.get(member)
        if not _holds(text, SELECTED_SPAN) or _holds(text, ANALYSIS_SPAN):
            yield Finding(
                rule,
                name,
                f"definition.{member}",
                "it does not name the selected span, or names the stabilized recovery "
                "that the analysis states",
            )
    stated = [
        c
        for c in _value(document, "acceptanceCriteria")
        if isinstance(c, Mapping) and c.get("id") == "E04-AC5"
    ]
    if len(stated) != 1:
        yield Finding(
            rule,
            name,
            "fields.acceptanceCriteria",
            f"E04-AC5 is stated {len(stated)} times, and not once",
        )
    index, criterion = _criteria_by_id(document).get("E04-AC5", (None, {}))
    statement = criterion.get("statement")
    if (
        criterion.get("kind") != "validity"
        or not _holds(statement, SELECTED_SPAN)
        or _holds(statement, ANALYSIS_SPAN)
    ):
        yield Finding(
            rule,
            name,
            _criterion_at(index),
            "E04-AC5 is not a validity criterion of the selected span",
        )


def _outcome_reference_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-reversal-outcome-reference"
    selection = _selection(document)
    reference = _member(selection, "outcomeReference")
    where = f"{SELECTED_BY}.outcomeReference"
    if not _equal(reference, OUTCOME_REFERENCE) or not _text(
        reference.get("statement")
    ):
        yield Finding(
            rule,
            name,
            where,
            "the selection does not name reversal_outcome of "
            "tools.reversal_outcome.core",
        )
    scope = _member(document, "materialScope")
    modules = scope.get("entryModules")
    if not isinstance(modules, list) or OUTCOME_REFERENCE["module"] not in modules:
        yield Finding(
            rule,
            name,
            "materialScope.entryModules",
            "the scope does not name the outcome reference",
        )
    if OUTCOME_REFERENCE["path"] not in _pins(document):
        yield Finding(rule, name, "pinnedInputs", "the outcome reference is not pinned")
    if not _holds(selection.get("evidenceComputation"), EVIDENCE_COMPUTATION_PHRASE):
        yield Finding(
            rule,
            name,
            f"{SELECTED_BY}.evidenceComputation",
            "it does not state that code which computes the selection from evidence "
            "is pinned before the first result-bearing run",
        )


def _controller_sentence(text: str, *, excluding: bool) -> bool:
    """A sentence names a reading or an instant of the controller, and with it the
    reversal or the known-good revision, or an instant or a state that only the
    controller sets; or, when ``excluding``, names a reading or an instant of the
    controller with a verdict that is not judged, an INCONCLUSIVE run, or an
    abort."""
    return any(
        _CONTROLLER_WORD.search(sentence)
        and (
            _EXCLUDING_WORD.search(sentence)
            if excluding
            else _REVERSAL_WORD.search(sentence) or _CONTROLLER_INSTANT.search(sentence)
        )
        for sentence in _FULL_SENTENCE_END.split(text)
    )


def _controller_discovery_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-reversal-controller-discovery"
    discovery = _member(_timing(document), CONTROLLER_DISCOVERY)
    if not _equal(discovery, CONTROLLER_DISCOVERY_MEMBERS) or not _text(
        discovery.get("statement")
    ):
        yield Finding(
            rule,
            name,
            f"definition.reversalTiming.{CONTROLLER_DISCOVERY}",
            "the controller's discovery of the reversal is not stated as part of "
            "recoveryMs, judged by E04-AC12 and by no validity criterion",
        )
    criteria = [
        (index, c)
        for index, c in enumerate(_value(document, "acceptanceCriteria") or [])
        if isinstance(c, Mapping)
    ]
    events = [(i, c) for i, c in criteria if c.get("id") == REVERSAL_EVENTS_CRITERION]
    if len(events) != 1:
        yield Finding(
            rule,
            name,
            "fields.acceptanceCriteria",
            f"{REVERSAL_EVENTS_CRITERION} is stated {len(events)} times, and not once",
        )
    for index, criterion in events:
        statement = criterion.get("statement")
        if criterion.get("kind") != "validity" or not all(
            _holds(statement, named) for named in REVERSAL_EVENTS_NAMED
        ):
            yield Finding(
                rule,
                name,
                _criterion_at(index),
                f"{REVERSAL_EVENTS_CRITERION} is not the validity criterion of the "
                "operator events of the reversal and the reversal commit",
            )
    validity = {
        identifier
        for _, c in criteria
        if c.get("kind") == "validity" and isinstance(identifier := c.get("id"), str)
    }
    strict: list[tuple[str, Any]] = []
    loose: list[tuple[str, Any]] = []
    for index, criterion in criteria:
        identifier = criterion.get("id")
        texts = (
            strict if isinstance(identifier, str) and identifier in validity else loose
        )
        texts.extend(_strings_in(criterion, _criterion_at(index)))
    definition = document["definition"]
    clocks = definition.get("criterionClocks")
    for index, entry in enumerate(clocks if isinstance(clocks, list) else []):
        if not isinstance(entry, Mapping):
            continue
        where = f"definition.criterionClocks[{index}]"
        criterion_id = entry.get("criterion")
        texts = (
            strict
            if isinstance(criterion_id, str) and criterion_id in validity
            else loose
        )
        texts.extend(_strings_in(entry, where))
        instants = entry.get("instants")
        if entry.get("criterion") == REVERSAL_EVENTS_CRITERION and any(
            not isinstance(i, Mapping) or i.get("source") != "operator-event"
            for i in (instants if isinstance(instants, list) else [None])
        ):
            yield Finding(
                rule,
                name,
                where,
                f"an order of {REVERSAL_EVENTS_CRITERION} reads a source other than "
                "the operator events",
            )
    reasons = _member(document, "exclusionReasons").get("reasons")
    for index, reason in enumerate(reasons if isinstance(reasons, list) else []):
        if isinstance(reason, Mapping):
            texts = (
                strict
                if reason.get("resultState") in ("INCONCLUSIVE", "ABORTED")
                else loose
            )
            texts.extend(_strings_in(reason, f"exclusionReasons.reasons[{index}]"))
    strict.extend(
        _strings_in(
            _value(document, "abortConditions"), "fields.abortConditions[0].value"
        )
    )
    loose.extend(
        _strings_in(definition.get("reversalTiming"), "definition.reversalTiming")
    )
    for member in (
        "outcomeRules",
        "gitTransitions",
        "faultProcedure",
        "observation",
        "postRecoveryWindow",
        "clockPolicy",
        "repetitionRule",
        "preparation",
        "executionGate",
    ):
        loose.extend(_strings_in(definition.get(member), f"definition.{member}"))
    for texts, excluding in ((strict, False), (loose, True)):
        for location, text in texts:
            if isinstance(text, str) and _controller_sentence(
                text, excluding=excluding
            ):
                yield Finding(
                    rule,
                    name,
                    location,
                    "it makes the controller's discovery of the reversal a condition "
                    "of validity"
                    if not excluding
                    else "it leaves a verdict not judged, or a run INCONCLUSIVE or "
                    "aborted, on the controller's discovery of the reversal",
                )


def _selection_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    """Every finding of the reversal rules of rule set 4 for one V2-E04 record: the
    parts of rule set 3 that it keeps, and the six selection rules."""
    yield from _instant_findings(name, document, SELECTION_RULE_SET)
    yield from _interval_findings(name, document)
    yield from _reversal_criterion_findings(name, document)
    yield from _reversal_reason_findings(name, document, (REVERSAL_START_UNCONFIRMED,))
    yield from _span_selection_findings(name, document)
    yield from _onset_exclusion_findings(name, document)
    yield from _unmet_recovery_findings(name, document)
    yield from _selected_span_findings(name, document)
    yield from _outcome_reference_findings(name, document)
    yield from _controller_discovery_findings(name, document)


# --------------------------------------------------------------------------
# The records against each other
# --------------------------------------------------------------------------


def _policy_findings(
    records: Mapping[str, tuple[str, Mapping[str, Any]]],
    rule_sets: Mapping[str, int],
) -> Iterator[Finding]:
    """Every record of rule set 2 states the clock policy of the first one.

    The first is V2-E02B when it is of rule set 2, and otherwise the first such
    record in the order of :data:`EXPERIMENTS`.
    """
    clocked = [
        e.experiment_id
        for e in EXPERIMENTS
        if e.experiment_id in records
        and rule_sets.get(e.experiment_id, RULE_SET_ONE) >= CLOCK_RULE_SET
    ]
    if not clocked:
        return
    reference = TARGET if TARGET in clocked else clocked[0]
    policy = _canonical(_clock_policy(records[reference][1]))
    for experiment in clocked:
        path, document = records[experiment]
        if experiment != reference and _canonical(_clock_policy(document)) != policy:
            yield Finding(
                "prereg-shared-differs",
                path,
                "definition.clockPolicy",
                f"it differs from {reference}",
            )


def _shared_findings(
    records: Mapping[str, tuple[str, Mapping[str, Any]]],
    rule_sets: Mapping[str, int],
) -> Iterator[Finding]:
    rule = "prereg-shared-differs"
    yield from _policy_findings(records, rule_sets)
    reference = records.get(TARGET)
    if reference is None:
        return
    for path, document in records.values():
        for field in COMMON_FIELDS:
            if _canonical(_value(document, field)) != _canonical(
                _value(reference[1], field)
            ):
                yield Finding(
                    rule, path, f"fields.{field}", f"it differs from {TARGET}"
                )
        bounds = {
            key: value
            for key, value in _value(document, "derivedNumericBounds").items()
            if key not in BOUND_MEMBERS_NOT_SHARED
        }
        target_bounds = {
            key: value
            for key, value in _value(reference[1], "derivedNumericBounds").items()
            if key not in BOUND_MEMBERS_NOT_SHARED
        }
        if _canonical(bounds) != _canonical(target_bounds):
            yield Finding(
                rule, path, "fields.derivedNumericBounds", f"it differs from {TARGET}"
            )
    if BASELINE not in records:
        return
    by_id = {e.experiment_id: e for e in EXPERIMENTS}
    path, baseline = records[BASELINE]
    target = reference[1]
    pairs: list[tuple[str, Any, Any]] = []
    for field in SHARED_FIELDS:
        pairs.append(
            (f"fields.{field}", _value(baseline, field), _value(target, field))
        )
    for member in SHARED_DEFINITION:
        pairs.append(
            (
                f"definition.{member}",
                baseline["definition"].get(member),
                target["definition"].get(member),
            )
        )
    # The two sides state the clocks of their validity criteria alike.
    if min(rule_sets.get(BASELINE, 1), rule_sets.get(TARGET, 1)) >= CLOCK_RULE_SET:
        pairs.append(
            (
                "definition.criterionClocks (validity)",
                _validity_clocks(baseline),
                _validity_clocks(target),
            )
        )
    # The two sides state one clock policy. When both are of rule set 2 the policy
    # findings above compare them. A side of rule set 1 states no policy, so a
    # side of rule set 2 beside one of rule set 1 differs from it here.
    if rule_sets.get(BASELINE, RULE_SET_ONE) != rule_sets.get(TARGET, RULE_SET_ONE):
        pairs.append(
            (
                "definition.clockPolicy",
                baseline["definition"].get("clockPolicy"),
                target["definition"].get("clockPolicy"),
            )
        )
    pairs.append(
        (
            "fields.acceptanceCriteria (validity)",
            _validity(baseline),
            _validity(target),
        )
    )
    pairs.append(
        (
            "exclusionReasons.reasons",
            _member(baseline, "exclusionReasons").get("reasons"),
            _member(target, "exclusionReasons").get("reasons"),
        )
    )
    for location, left, right in pairs:
        if location == "fields.derivedNumericBounds":
            left = {k: v for k, v in (left or {}).items() if k != "use"}
            right = {k: v for k, v in (right or {}).items() if k != "use"}
        if left is None or _canonical(_normalised(left, by_id[BASELINE])) != _canonical(
            _normalised(right, by_id[TARGET])
        ):
            yield Finding(rule, path, location, f"it differs from {TARGET}")


def _validity_clocks(document: Mapping[str, Any]) -> dict[str, Any]:
    """The clock entries of the validity criteria of a record of rule set 2, and the
    validity criteria that it lists as without clocks. Each criterion is named by
    the part of its identifier after the experiment part, such as ``AC3``."""
    validity = {
        str(c.get("id")): str(c.get("id")).split("-", 1)[-1]
        for c in _value(document, "acceptanceCriteria")
        if isinstance(c, Mapping) and c.get("kind") == "validity"
    }
    entries = [
        {**e, "criterion": validity[e["criterion"]]}
        for e in document["definition"]["criterionClocks"]
        if isinstance(e, Mapping)
        and isinstance(e.get("criterion"), str)
        and e["criterion"] in validity
    ]
    without = document["definition"].get("criteriaWithoutClocks")
    listed = [
        validity[c]
        for c in (without if isinstance(without, list) else [])
        if isinstance(c, str) and c in validity
    ]
    return {"entries": entries, "withoutClocks": listed}


def _validity(document: Mapping[str, Any]) -> list[Any] | None:
    """The statements of the validity criteria of a record, in order.

    A validity criterion decides whether a run answers its question, and the two
    sides of the comparison hold a run to the same ones. A pass criterion of the
    target is a criterion of the reliability claim, and the baseline has none.
    """
    criteria = _value(document, "acceptanceCriteria")
    if not isinstance(criteria, list):
        return None
    statements = [
        c.get("statement")
        for c in criteria
        if isinstance(c, Mapping) and c.get("kind") == "validity"
    ]
    return statements or None


def _comparison_findings(
    records: Mapping[str, tuple[str, Mapping[str, Any]]], root: Path
) -> Iterator[Finding]:
    rule = "prereg-baseline-difference-unpermitted"
    if BASELINE not in records or TARGET not in records:
        return
    path, baseline = records[BASELINE]
    target = records[TARGET][1]
    # A finding about one side names the record of that side.
    owners = {"baseline": path, "target": records[TARGET][0]}
    sides = {
        "baseline": _value(baseline, "topology"),
        "target": _value(target, "topology"),
    }
    for member in sorted(set(sides["baseline"]) | set(sides["target"])):
        if member in PERMITTED_TOPOLOGY:
            continue
        if _canonical(sides["baseline"].get(member)) != _canonical(
            sides["target"].get(member)
        ):
            yield Finding(
                rule,
                path,
                f"fields.topology.{member}",
                "it is not a permitted difference",
            )
    for side in ("baseline", "target"):
        topology = sides[side]
        for tier, count in (
            ("apiDisruptionBudget", topology["apiReplicas"]),
            ("runtimeDisruptionBudget", topology["runtimeReplicas"]),
        ):
            budget = topology[tier]
            if budget["rendered"] != (count >= _BUDGET_REPLICAS) or (
                budget["rendered"] and budget.get("minAvailable") != _BUDGET_MINIMUM
            ):
                yield Finding(
                    rule,
                    owners[side],
                    f"fields.topology.{tier}",
                    "it is not the budget that the chart renders for the replica count",
                )
    reference = sides["baseline"].get("comparison")
    if not isinstance(reference, Mapping) or not set(reference) >= _REFERENCE_MEMBERS:
        yield Finding(
            rule, path, "fields.topology.comparison", "it names no comparison"
        )
        return
    read = _read(root, str(reference["path"]))
    if read is None or not isinstance(read[1], Mapping):
        yield Finding(rule, path, "fields.topology.comparison", "it is not committed")
        return
    data, comparison = read
    if content_digest(data) != reference["contentSha256"]:
        yield Finding(
            rule,
            path,
            "fields.topology.comparison",
            "the comparison has another digest",
        )
    if comparison.get("result") != COMPARABLE:
        yield Finding(
            rule, path, "fields.topology.comparison", "the comparison is not COMPARABLE"
        )
    if _canonical(reference.get("permittedDifferences")) != _canonical(
        comparison.get("permittedDifferences")
    ):
        yield Finding(
            rule,
            path,
            "fields.topology.comparison",
            "the permitted differences are not those of the comparison",
        )
    for side, document in (("baseline", baseline), ("target", target)):
        topology = sides[side]
        release = topology["release"]
        stated = _member(_member(comparison, "releases"), side)
        metadata = _member(stated, "metadata")
        values = _member(_member(stated, "output"), "helmValues")
        declared = _member(_member(comparison, "declarations"), side)
        replicas = _member(_member(comparison, "effectiveTopology"), side)
        pins = _pins(document)
        contract = _member(release, "contract")
        files = _member(release, "desiredStateFiles")
        directory = release["filesFrom"]
        checks = (
            ("releaseId", release["releaseId"], metadata.get("releaseId")),
            (
                "workloadVersion",
                release["workloadVersion"],
                metadata.get("workloadVersion"),
            ),
            ("helmValuesSha256", release["helmValuesSha256"], values.get("sha256")),
            ("contract", contract.get("path"), declared.get("contract")),
            (
                "contract digest",
                contract.get("contentSha256"),
                pins.get(str(contract.get("path"))),
            ),
            ("filesFrom", directory, declared.get("directory")),
            (
                "runtimeReplicas",
                topology.get("runtimeReplicas"),
                replicas.get("runtimeReplicas"),
            ),
            ("apiReplicas", topology.get("apiReplicas"), replicas.get("apiReplicas")),
            (
                "the values file",
                files.get("values.generated.yaml"),
                release["helmValuesSha256"],
            ),
        )
        for label, actual, expected in checks:
            if actual is None or _canonical(actual) != _canonical(expected):
                yield Finding(
                    rule,
                    owners[side],
                    f"fields.topology.release ({side})",
                    f"{label} is not the one of the comparison",
                )
        for file_name, digest in files.items():
            if pins.get(f"{directory}/{file_name}") != digest:
                yield Finding(
                    rule,
                    owners[side],
                    f"fields.topology.release ({side})",
                    f"{file_name} is not pinned with the stated digest",
                )


def _target_findings(
    records: Mapping[str, tuple[str, Mapping[str, Any]]],
) -> Iterator[Finding]:
    if TARGET not in records:
        return
    target = _value(records[TARGET][1], "topology")
    for experiment, (path, document) in records.items():
        if experiment in (BASELINE, TARGET):
            continue
        if _canonical(_value(document, "topology")) != _canonical(target):
            yield Finding(
                "prereg-target-topology-differs",
                path,
                "fields.topology",
                f"it differs from {TARGET}",
            )


# --------------------------------------------------------------------------
# The whole check
# --------------------------------------------------------------------------


def _rule_set(path: str, document: Mapping[str, Any]) -> int | None:
    """The rule set that a record is read under, or None when it states no known one.

    A V2-E04 record after revision 1 is read under rule set 3 or later, so that the
    reversal-timing rules read every such revision, and one after revision 2 under
    rule set 4 or later, so that no later revision can leave the selection rules by
    stating rule set 3.
    """
    stated = _member(document, "metadata").get(RULE_SET_MEMBER, None)
    if path in REVISION_ONE_RECORDS:
        return RULE_SET_ONE if stated is None else None
    if type(stated) is not int or stated not in RULE_SETS or stated == RULE_SET_ONE:
        return None
    reversal = _member(document, "metadata").get("experiment") == REVERSAL_EXPERIMENT
    if reversal and stated < REVERSAL_RULE_SET:
        return None
    if reversal and _revision(path) > 2 and stated < SELECTION_RULE_SET:
        return None
    return stated


def _revision(path: str) -> int:
    """The revision that the name of a record states, or 0."""
    match = RECORD_NAME.match(PurePosixPath(path).name)
    return 0 if match is None else int(match.group(1))


def _readable(
    experiment: Experiment, path: str, document: Any
) -> tuple[list[Finding], int | None]:
    """The findings that stop a record from being read, and its rule set."""
    if (
        not isinstance(document, Mapping)
        or _member(document, "metadata").get("experiment") != experiment.experiment_id
    ):
        return [
            Finding(
                "prereg-record-missing",
                path,
                "metadata.experiment",
                f"the record does not name {experiment.experiment_id}",
            )
        ], None
    rule_set = _rule_set(path, document)
    if rule_set is None:
        if path in REVISION_ONE_RECORDS:
            detail = "a revision-1 record of rule set 1 states no rule set"
        elif experiment.experiment_id == REVERSAL_EXPERIMENT and _revision(path) > 2:
            detail = (
                "a V2-E04 record after revision 2 states no rule set of 4 or later "
                "that this check knows"
            )
        elif experiment.experiment_id == REVERSAL_EXPERIMENT:
            detail = (
                "a V2-E04 record after revision 1 states no rule set of 3 or later "
                "that this check knows"
            )
        else:
            detail = "the record states no rule set of 2 or later that this check knows"
        return [
            Finding(
                "prereg-rule-set-unknown",
                path,
                f"metadata.{RULE_SET_MEMBER}",
                detail,
            )
        ], None
    problem = _shape_problem(document, rule_set)
    if problem is not None:
        return [Finding("prereg-record-shape", path, "$", problem)], None
    return [], rule_set


def _record_findings(
    path: str,
    experiment: Experiment,
    document: Mapping[str, Any],
    rule_set: int,
    root: Path,
    target_release: str | None,
    *,
    current: bool,
) -> Iterator[Finding]:
    """Every finding of the rules that read one record."""
    yield from _qualification_findings(path, document, root, target_release)
    yield from _bound_findings(path, document, root, target_release, current=current)
    yield from _criterion_findings(path, document)
    yield from _reconciliation_findings(path, experiment.experiment_id, document)
    yield from _executable_findings(path, experiment, document)
    yield from _exclusion_findings(path, experiment.experiment_id, document)
    if rule_set >= CLOCK_RULE_SET:
        yield from _clock_findings(path, document)
    # Rule set 3 reads the onset of the analysis and its exclusion reason, and rule
    # set 4 reads the selection instead: neither inherits the other's rules.
    if experiment.experiment_id == REVERSAL_EXPERIMENT:
        if rule_set == REVERSAL_RULE_SET:
            yield from _reversal_findings(path, document)
        elif rule_set >= SELECTION_RULE_SET:
            yield from _selection_findings(path, document)


def _sorted(findings: list[Finding]) -> list[Finding]:
    order = {rule: index for index, rule in enumerate(RULES)}
    return sorted(findings, key=lambda f: (order[f.rule_id], f.record, f.location))


def check_records(
    records: Mapping[str, tuple[str, Any]], root: Path = REPO_ROOT
) -> list[Finding]:
    """Every way one set of records, one for each experiment, breaks a rule.

    Each record is read under its own rule set, and the records are compared with
    each other. :func:`check_repository` passes the latest revisions.
    """
    findings: list[Finding] = []
    usable: dict[str, tuple[str, Mapping[str, Any]]] = {}
    rule_sets: dict[str, int] = {}
    for experiment in EXPERIMENTS:
        if experiment.experiment_id not in records:
            findings.append(
                Finding(
                    "prereg-record-missing",
                    experiment.directory,
                    "$",
                    "no freeze record is committed",
                )
            )
            continue
        path, document = records[experiment.experiment_id]
        problems, rule_set = _readable(experiment, path, document)
        findings.extend(problems)
        if rule_set is None:
            continue
        usable[experiment.experiment_id] = (path, document)
        rule_sets[experiment.experiment_id] = rule_set
    target_release = None
    if TARGET in usable:
        target_release = _value(usable[TARGET][1], "topology")["release"]["releaseId"]
    by_id = {e.experiment_id: e for e in EXPERIMENTS}
    for experiment_id, (path, document) in usable.items():
        findings.extend(
            _record_findings(
                path,
                by_id[experiment_id],
                document,
                rule_sets[experiment_id],
                root,
                target_release,
                current=True,
            )
        )
    findings.extend(_shared_findings(usable, rule_sets))
    findings.extend(_comparison_findings(usable, root))
    findings.extend(_target_findings(usable))
    return _sorted(findings)


def check_repository(root: Path = REPO_ROOT) -> list[Finding]:
    """Every way the committed records of the five experiments break a rule.

    The latest revision of each experiment is checked in full. Each earlier
    revision is checked alone, under its own rule set, and is not compared with
    the present: its bound record need not be the latest one, and its qualified
    release is not compared with that of the latest V2-E02B.
    """
    revisions = record_revisions(root)
    findings = check_records(
        {key: (r[-1][1], r[-1][2]) for key, r in revisions.items()}, root
    )
    for experiment in EXPERIMENTS:
        for _, path, document in revisions.get(experiment.experiment_id, [])[:-1]:
            problems, rule_set = _readable(experiment, path, document)
            findings.extend(problems)
            if rule_set is not None:
                findings.extend(
                    _record_findings(
                        path, experiment, document, rule_set, root, None, current=False
                    )
                )
    return _sorted(findings)


def superseded_count(root: Path = REPO_ROOT) -> int:
    """The number of committed revisions that a later revision supersedes."""
    return sum(len(r) - 1 for r in record_revisions(root).values())


def rule_statements() -> Sequence[tuple[str, str]]:
    """Each rule and its statement, in report order."""
    return tuple(RULES.items())
