"""The controlled single-runtime baseline, compared with the release it is a baseline of.

The target is the desired-state release of the reference workload: two API
replicas and two serving runtime replicas. The baseline is an experiment profile:
two API replicas and one serving runtime replica. A comparison of the two
topologies means something only while the runtime replica count is the one
variable that differs. This module declares the baseline, derives both releases,
and refuses each difference that is not stated here.

**The baseline is declared as the target with one input replaced.**
:func:`baseline_profile` takes the target's declaration and replaces the contract
and the directory. The binding, the platform defaults, and both revisions stay the
target's. The baseline's contract is version ``0.1.0`` of the target's workload,
which declares a replica range of one and one.

**Six layers are compared.** The two declarations, the two contract documents,
the two generated values documents, the two release documents, the two install
descriptions, and the two documents of effective values.
:data:`PERMITTED` names each path that may differ in a layer, and why. A
difference at any other path refuses the comparison. Both releases are derived
again from their declared inputs, so no committed generated file is trusted.

**A workload version names one content.** The two contracts differ in content, so
they must differ in version. The version is a rendered value, so the two releases
differ in it too. That is the second permitted difference, and it follows the
first.

**Each side states its install inputs.** A release is installed from a chart, a
release name, a namespace, one generated values file, and hand-written values.
The target states them in the Application that reads it. The baseline states
them in :data:`INSTALL_PATH`, a file that a person writes. Each description is
read whole: an absent file, a file that does not parse, an absent member, and a
member that this module does not read each refuse the comparison. No value is
taken from a default when a description does not state it. The chart is stated
by its version and by the digest of the files that a render reads.

**Effective values are the values that the chart receives.** They are the
chart's defaults, then the generated values of the side, then its hand-written
values, merged as Helm merges values documents. :data:`READINESS_INPUTS` names
each probe path and each probe setting of the two tiers. Each side must state
each of them, so two absent values are never read as two equal values.

**``COMPARABLE`` is not eligibility.** The result is about committed inputs. A
record lists each input that no committed file resolves:
:func:`build_record` states them under ``unresolvedInputs``, and it states
``experimentEligibility`` as ``not-established`` in every record.

**What is not compared.** Comments in a contract are not part of the parsed
document. No committed file states the API image digest, so it is listed as
unresolved. No caller profile exists in this repository, so it is listed as
unresolved. This module does not run Helm, so it compares no rendered object;
a test of the chart suite renders each side with its own install description.
Nothing here reads a cluster, so nothing compares an installed release with a
description.

**The declaration layer is a tripwire.** :func:`baseline_profile` builds the
baseline from the target's declaration, so the two agree by construction. The
layer is not held when a later edit of that function names another binding,
another defaults file, or another revision.

**The comparison rests on the parsers.** A release is derived before it is
compared, so a contract that the render boundary refuses is never compared.
The walk of two documents does not depend on that: a mapping beside a sequence,
and a mapping with a key that is not text, are each compared whole.

**Offline.** Every function reads files under the root it is given.
:func:`write_profile` writes the declared profile directory and the comparison
record beside it. Nothing here contacts a cluster, a registry, a network, or a
model, and nothing runs Helm or Git.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

import yaml

from tools.capacity_preflight import APPLICATIONS
from tools.generated_release import (
    GENERATED_FILES,
    REPO_ROOT,
    DeclaredRelease,
    SourcesRefused,
    derive,
    regenerate,
    verify,
)
from tools.gitops_desired_state import (
    DESIRED_STATE_ROOT,
    desired_state_release,
)

__all__ = [
    "BASELINE_CONTRACT",
    "CHECK_RULES",
    "COMPARABLE",
    "DOES_NOT_ESTABLISH",
    "ELIGIBILITY",
    "HELD",
    "INSTALL_PATH",
    "INSTALL_SCHEMA",
    "INTENDED",
    "NOT_EVALUATED",
    "NOT_HELD",
    "PERMITTED",
    "PROFILE_DIRECTORY",
    "READINESS_INPUTS",
    "RECORD_PATH",
    "RECORD_SCHEMA",
    "REFUSED",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RESULT_STATES",
    "RULES",
    "TARGET_KEY",
    "TOPOLOGY",
    "Finding",
    "Rule",
    "WriteRefused",
    "baseline_profile",
    "build_record",
    "record_text",
    "target_release",
    "verify_profile",
    "write_profile",
]

#: The schema name a comparison record states.
RECORD_SCHEMA: Final = "inferops.io/baseline-profile-comparison/v1alpha1"

#: The desired-state release that the baseline is a baseline of, by its key.
TARGET_KEY: Final = "local-docker-desktop/support-assistant"

#: The contract the baseline is rendered from: version ``0.1.0`` of the target's
#: workload, which declares one serving runtime replica.
BASELINE_CONTRACT: Final = (
    "contracts/workload/examples/valid/synchronous-llm-local.yaml"
)

#: The directory that holds the baseline's two generated files. It is outside the
#: Git desired state, so no Application reads it.
PROFILE_DIRECTORY: Final = (
    "tests/domain/fixtures/experiment-profiles/single-runtime-baseline"
)

#: The committed comparison record, beside the profile directory.
RECORD_PATH: Final = f"{PROFILE_DIRECTORY}.comparison.v1alpha1.json"

#: The install inputs of the baseline, beside the profile directory. A person
#: writes this file. The target states the same inputs in its Application.
INSTALL_PATH: Final = f"{PROFILE_DIRECTORY}.install.v1alpha1.yaml"

#: The schema name the baseline's install description states.
INSTALL_SCHEMA: Final = "inferops.io/baseline-install-inputs/v1alpha1"

#: What every record states about eligibility. This tool resolves no caller
#: profile, so no record of it states another value.
ELIGIBILITY: Final = "not-established"

#: The exit status of a comparison whose result is ``REFUSED``.
REFUSED_EXIT: Final = 5

COMPARABLE: Final = "COMPARABLE"
REFUSED: Final = "REFUSED"

#: The result states of a comparison record.
RESULT_STATES: Final = (COMPARABLE, REFUSED)

HELD: Final = "held"
NOT_HELD: Final = "not-held"
NOT_EVALUATED: Final = "not-evaluated"

#: The replica counts each side must state. The runtime count is the variable.
TOPOLOGY: Final[Mapping[str, Mapping[str, int]]] = {
    "baseline": {"apiReplicas": 2, "runtimeReplicas": 1},
    "target": {"apiReplicas": 2, "runtimeReplicas": 2},
}

#: Why a path may differ: it is the variable of the comparison.
INTENDED: Final = "intended-variable"
#: Why a path may differ: it is an identity that follows a permitted difference.
_IDENTITY: Final = "identity-of-a-different-content"
#: Why a path may differ: it is prose that no render reads.
_PROSE: Final = "prose-not-rendered"
#: Why a declaration field may differ: it is what makes the baseline a profile.
_PROFILE: Final = "profile-declaration"

#: Every path that may differ, by layer, and the reason. A path is a JSON
#: pointer into the layer's document. No other path may differ.
PERMITTED: Final[Mapping[str, Mapping[str, str]]] = {
    "declaration": {
        "/contract": _PROFILE,
        "/directory": _PROFILE,
    },
    "contract": {
        "/metadata/description": _PROSE,
        "/metadata/version": _IDENTITY,
        "/spec/scaling/maximumReplicas": INTENDED,
        "/spec/scaling/minimumReplicas": INTENDED,
    },
    "values": {
        "/ownership/workloadVersion": _IDENTITY,
        "/runtime/replicaCount": INTENDED,
    },
    "release": {
        "/metadata/releaseId": _IDENTITY,
        "/metadata/workloadVersion": _IDENTITY,
        "/output/helmValues/sha256": _IDENTITY,
        "/source/contract/sha256": _IDENTITY,
    },
    "install": {
        "/valuesFile": _PROFILE,
    },
    "effective": {
        "/ownership/workloadVersion": _IDENTITY,
        "/runtime/replicaCount": INTENDED,
    },
}

#: The layers of a comparison, in the order a record reports them.
_LAYERS: Final = (
    "declaration",
    "contract",
    "values",
    "release",
    "install",
    "effective",
)

_PROBE_SETTINGS: Final[Mapping[str, tuple[str, ...]]] = {
    "startup": ("budgetMs", "periodSeconds", "timeoutSeconds"),
    "readiness": ("periodSeconds", "timeoutSeconds", "failureThreshold"),
    "liveness": ("periodSeconds", "timeoutSeconds", "failureThreshold"),
}


def _probe_inputs(tier: str, *paths: str) -> tuple[str, ...]:
    return (
        *(f"/{tier}/{path}" for path in paths),
        f"/{tier}/probes/enabled",
        *(
            f"/{tier}/probes/{probe}/{setting}"
            for probe, settings in _PROBE_SETTINGS.items()
            for setting in settings
        ),
    )


#: The readiness inputs: each value that the chart's probe templates read, as a
#: JSON pointer into the effective values. A startup probe gates the other two,
#: and a liveness probe restarts a container, so all three probes are named.
#: Each side must state each path.
READINESS_INPUTS: Final[tuple[str, ...]] = (
    *_probe_inputs("api", "readinessPath", "livenessPath"),
    *_probe_inputs("runtime", "healthPath", "startupBudgetMs"),
)

#: The members a description states, by the block that holds them. A member that
#: is not named here is an install input that this module does not read, and it
#: refuses the comparison.
_APPLICATION_MEMBERS: Final[Mapping[str, frozenset[str]]] = {
    "spec": frozenset({"project", "source", "destination", "syncPolicy"}),
    "spec.source": frozenset({"repoURL", "targetRevision", "path", "helm"}),
    "spec.source.helm": frozenset({"releaseName", "valueFiles", "valuesObject"}),
    "spec.destination": frozenset({"server", "namespace"}),
}
_INSTALL_MEMBERS: Final[Mapping[str, frozenset[str]]] = {
    "the document": frozenset(
        {"apiVersion", "kind", "chart", "release", "valuesFile", "handWrittenValues"}
    ),
    "chart": frozenset({"repository", "revision", "path"}),
    "release": frozenset({"name", "namespace"}),
}

#: The files of a chart that a render reads, beside its templates.
_CHART_FILES: Final = ("Chart.yaml", "values.yaml", "values.schema.json")
_CHART_TEMPLATES: Final = "templates"
_API_IMAGE_DIGEST: Final = "/api/image/digest"


@dataclass(frozen=True)
class Rule:
    """A property the baseline has to hold beside the target."""

    rule_id: str
    statement: str


#: The rules a comparison record states, in the order it reports them.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "baseline-declaration-differs",
        "The baseline declaration states the bindings, the binding name, the "
        "platform defaults, and both revisions that the target declaration states, "
        "and its directory is outside the Git desired state.",
    ),
    Rule(
        "baseline-sources-refused",
        "The declared sources of the baseline and of the target each derive a release.",
    ),
    Rule(
        "baseline-contract-differs",
        "The two contract documents differ only in the replica range, the "
        "workload version, and the description.",
    ),
    Rule(
        "baseline-values-differ",
        "The two generated values documents differ only in the runtime replica "
        "count and the workload version.",
    ),
    Rule(
        "baseline-release-differs",
        "The two release documents differ only in the release identifier, the "
        "workload version, the contract digest, and the values digest.",
    ),
    Rule(
        "baseline-topology-not-declared",
        "The baseline states two API replicas and one runtime replica. The target "
        "states two API replicas and two runtime replicas. Each contract states a "
        "replica range of one number.",
    ),
    Rule(
        "baseline-version-not-distinct",
        "The baseline and the target name one workload and two workload versions.",
    ),
    Rule(
        "baseline-install-inputs-refused",
        "The install description of the baseline and of the target is each a "
        "file that parses, that states each member this tool reads and no "
        "other, and that names a chart of this tree.",
    ),
    Rule(
        "baseline-install-differs",
        "The two install descriptions differ only in the generated values file, "
        "and each names the generated values file of its own release.",
    ),
    Rule(
        "baseline-effective-values-differ",
        "The values that the chart receives on each side differ only in the "
        "runtime replica count and the workload version, and they state the "
        "replica counts of that side.",
    ),
    Rule(
        "baseline-readiness-input-absent",
        "The values that the chart receives on each side state each readiness "
        "input: each probe path and each probe setting of the API and of the "
        "runtime.",
    ),
)

#: The rules that are evaluated only when each side derives a release.
_RELEASE_RULES: Final = (
    "baseline-contract-differs",
    "baseline-values-differ",
    "baseline-release-differs",
    "baseline-topology-not-declared",
    "baseline-version-not-distinct",
)

#: The rules that :func:`verify_profile` adds for the committed files.
CHECK_RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "baseline-release-drifted",
        "The committed baseline release is, byte for byte, what its declared "
        "sources derive.",
    ),
    Rule(
        "baseline-record-stale",
        "The committed comparison record is, byte for byte, the record that the "
        "files of this tree give.",
    ),
)

#: What a comparison record does not establish. A record states each line.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "That a cluster ran the baseline. No Application reads the profile directory, "
    "and no run installed the baseline release.",
    "What a caller observes when the one runtime pod of the baseline stops, or "
    "when one of the two runtime pods of the target stops.",
    "That the baseline is eligible for an experiment. The result is a statement "
    "about committed inputs, and every record states the eligibility as "
    "not-established.",
    "That a run installs either release with the install inputs that this record "
    "states. The record compares two committed descriptions. No procedure reads "
    "the baseline's description, and nothing compares a cluster with either.",
    "That the two releases install with one API image digest. No committed file "
    "states the digest. An operator supplies it at install, and the record lists "
    "it as unresolved.",
    "That a cluster reads the chart files whose digest this record states. Each "
    "description names a branch as the chart revision, and the digest is of the "
    "files of the tree that the tool read.",
    "That the two releases render equal probes. The record compares the values "
    "that the chart receives and the digest of the chart files. This tool does "
    "not run Helm.",
    "That a probe behaves as its settings state, or that a pod was Ready. No "
    "cluster was read.",
    "That the model cache claim is in one state for both sides. The claim is not "
    "a compared input.",
    "That one caller profile is applied to both sides. No caller profile exists "
    "in this repository, and the record lists it as unresolved.",
    "That telemetry of the two sides is equal. The workload version differs, and "
    "it is a resource attribute of the API's telemetry.",
    "That a cluster holds the baseline. The capacity preflight derives the "
    "footprint of the target only.",
    "That either recorded revision is the commit a release was rendered at, or "
    "that it names a commit.",
)


@dataclass(frozen=True)
class Finding:
    """One way the baseline breaks a rule.

    ``subject`` is a layer followed by a path in it, a declared input, or a file
    under the repository root.
    """

    rule_id: str
    subject: str
    detail: str


class WriteRefused(Exception):
    """A write of a profile that the rules refuse."""

    def __init__(self, findings: Sequence[Finding]) -> None:
        super().__init__("; ".join(f"{f.rule_id} {f.subject}" for f in findings))
        self.findings = tuple(findings)


def target_release() -> DeclaredRelease:
    """The declaration of the desired-state release the baseline is compared with."""
    return desired_state_release(TARGET_KEY)


def baseline_profile() -> DeclaredRelease:
    """The declaration of the baseline: the target's, with two fields replaced."""
    return replace(
        target_release(), directory=PROFILE_DIRECTORY, contract=BASELINE_CONTRACT
    )


# --------------------------------------------------------------------------
# Differences between two documents
# --------------------------------------------------------------------------

#: A path that one side of a comparison does not have.
_ABSENT: Final = object()


def _escaped(key: str) -> str:
    """One reference token of a JSON pointer."""
    return key.replace("~", "~0").replace("/", "~1")


def _kind(document: Any) -> str:
    """Whether a document is walked as a mapping, walked as a sequence, or a leaf.

    An empty mapping and an empty sequence are leaves, so a side that empties a
    member differs from a side that fills it. A mapping with a key that is not
    text is a leaf too: such a key has no pointer of its own, so the mapping is
    compared whole.
    """
    if isinstance(document, Mapping) and document:
        return "mapping" if all(type(key) is str for key in document) else "leaf"
    if isinstance(document, list) and document:
        return "sequence"
    return "leaf"


def _children(document: Any, kind: str) -> dict[str, Any]:
    """The members of a walked document, by reference token."""
    if document is _ABSENT:
        return {}
    if kind == "mapping":
        return {_escaped(key): value for key, value in document.items()}
    return {str(index): value for index, value in enumerate(document)}


def _pairs(
    baseline: Any, target: Any, pointer: str = ""
) -> Iterator[tuple[str, Any, Any]]:
    """Every leaf path of two documents, with the value each side has there.

    Both sides are walked together. A mapping on one side and a sequence on the
    other are one leaf at their own path, so an index never meets a key of the
    same spelling. A path that one side lacks is walked on the side that has it.
    """
    kinds = {_kind(side) for side in (baseline, target) if side is not _ABSENT}
    if len(kinds) != 1 or kinds == {"leaf"}:
        yield pointer, baseline, target
        return
    (kind,) = kinds
    ours, theirs = _children(baseline, kind), _children(target, kind)
    for token in sorted(ours.keys() | theirs.keys()):
        yield from _pairs(
            ours.get(token, _ABSENT), theirs.get(token, _ABSENT), f"{pointer}/{token}"
        )


def _plain(value: Any) -> Any:
    """A value as a JSON record can state it.

    A value that JSON cannot state without loss, such as a mapping with a key
    that is not text, is stated as its Python text.
    """
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, list):
        return [_plain(member) for member in value]
    if isinstance(value, Mapping) and all(type(key) is str for key in value):
        return {key: _plain(member) for key, member in value.items()}
    return repr(value)


def _differences(
    layer: str, baseline: Any, target: Any
) -> tuple[list[dict[str, Any]], int]:
    """Each path at which two documents differ, and the count of paths read.

    A difference states the value of each side that has the path. A side that
    lacks the path states no value.
    """
    permitted = PERMITTED[layer]
    differences = []
    count = 0
    for path, ours, theirs in sorted(
        _pairs(baseline, target), key=lambda pair: pair[0]
    ):
        count += 1
        # The absent marker has its own type, so it equals no stated value.
        if type(ours) is type(theirs) and ours == theirs:
            continue
        entry: dict[str, Any] = {"path": path, "permitted": path in permitted}
        if path in permitted:
            entry["reason"] = permitted[path]
        if ours is not _ABSENT:
            entry["baseline"] = _plain(ours)
        if theirs is not _ABSENT:
            entry["target"] = _plain(theirs)
        differences.append(entry)
    return differences, count


def _shown(entry: Mapping[str, Any], side: str) -> str:
    return json.dumps(entry[side]) if side in entry else "(absent)"


def _layer_findings(
    rule_id: str, layer: str, differences: Sequence[Mapping[str, Any]]
) -> list[Finding]:
    return [
        Finding(
            rule_id,
            f"{layer}: {entry['path'] or '/'}",
            f"the baseline states {_shown(entry, 'baseline')} and the target "
            f"states {_shown(entry, 'target')}; this path may not differ",
        )
        for entry in differences
        if not entry["permitted"]
    ]


# --------------------------------------------------------------------------
# One comparison
# --------------------------------------------------------------------------


def _declaration(declared: DeclaredRelease) -> dict[str, Any]:
    """One declaration, as a record states it."""
    return {
        "bindingName": declared.binding_name,
        "bindings": list(declared.bindings),
        "contract": declared.contract,
        "directory": declared.directory,
        "platformDefaults": declared.platform_defaults,
        "platformDefaultsRevision": declared.platform_defaults_revision,
        "rendererRevision": declared.renderer_revision,
    }


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _member(document: Any, *path: str) -> Any:
    for name in path:
        if not isinstance(document, Mapping) or name not in document:
            return None
        document = document[name]
    return document


def _whole(value: Any) -> int | None:
    """A whole number as a document states it, and nothing a parser coerced."""
    return value if type(value) is int else None


def _topology_findings(
    contracts: Mapping[str, Any], values: Mapping[str, Any]
) -> tuple[list[Finding], dict[str, dict[str, int | None]]]:
    findings = []
    stated: dict[str, dict[str, int | None]] = {}
    for side, expected in TOPOLOGY.items():
        raw = {
            "apiReplicas": _member(values[side], "api", "replicaCount"),
            "runtimeReplicas": _member(values[side], "runtime", "replicaCount"),
        }
        stated[side] = {name: _whole(found) for name, found in raw.items()}
        for name, found in raw.items():
            if _whole(found) != expected[name]:
                findings.append(
                    Finding(
                        "baseline-topology-not-declared",
                        f"values: {side} {name}",
                        f"the {side} states {json.dumps(_plain(found))}; the "
                        f"comparison needs the whole number {expected[name]}",
                    )
                )
        scaling = _member(contracts[side], "spec", "scaling")
        low = _member(scaling, "minimumReplicas")
        high = _member(scaling, "maximumReplicas")
        needed = expected["runtimeReplicas"]
        if _whole(low) != needed or _whole(high) != needed:
            findings.append(
                Finding(
                    "baseline-topology-not-declared",
                    f"contract: {side} /spec/scaling",
                    f"the {side} contract states a replica range of "
                    f"{json.dumps(_plain(low))} to {json.dumps(_plain(high))}; the "
                    f"comparison needs the whole numbers {needed} and {needed}",
                )
            )
    return findings, stated


def _version_findings(contracts: Mapping[str, Any]) -> list[Finding]:
    names = {side: _member(contracts[side], "metadata", "name") for side in TOPOLOGY}
    versions = {
        side: _member(contracts[side], "metadata", "version") for side in TOPOLOGY
    }
    findings = []
    if names["baseline"] != names["target"]:
        findings.append(
            Finding(
                "baseline-version-not-distinct",
                "contract: /metadata/name",
                f"the baseline names the workload {json.dumps(names['baseline'])} "
                f"and the target names {json.dumps(names['target'])}",
            )
        )
    if versions["baseline"] == versions["target"]:
        findings.append(
            Finding(
                "baseline-version-not-distinct",
                "contract: /metadata/version",
                f"both contracts state the version {json.dumps(versions['target'])}; "
                "one version would name two contents",
            )
        )
    return findings


def _declaration_findings(
    baseline: DeclaredRelease, differences: Sequence[Mapping[str, Any]]
) -> list[Finding]:
    findings = _layer_findings(
        "baseline-declaration-differs", "declaration", differences
    )
    reason = _directory_refusal(baseline.directory)
    if reason is not None:
        findings.append(
            Finding(
                "baseline-declaration-differs",
                "declaration: /directory",
                f"{baseline.directory} {reason}",
            )
        )
    return findings


def _directory_refusal(directory: str) -> str | None:
    """Why a profile directory is refused, or ``None``.

    The directory is one spelling: a relative POSIX path with no ``.`` and no
    ``..`` segment. So no second spelling of a path names the desired state. The
    first segment is compared without case, because a file system that ignores
    case gives ``GitOps`` and ``gitops`` one directory.
    """
    if not _plain_path(directory):
        return (
            "is not a relative POSIX path of plain segments, so the tree it is in "
            "cannot be read from its spelling"
        )
    if directory.split("/")[0].casefold() == DESIRED_STATE_ROOT.casefold():
        return (
            "is inside the Git desired state; an Application reads that tree, and "
            "the baseline is not desired state"
        )
    return None


def _plain_path(path: str) -> bool:
    """Whether a text is one relative POSIX path of plain segments."""
    return not (
        chr(92) in path
        or ":" in path
        or any(segment in ("", ".", "..") for segment in path.split("/"))
    )


# --------------------------------------------------------------------------
# The install inputs of one side
# --------------------------------------------------------------------------


class _InstallRefused(Exception):
    """An install description that is not read whole."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _document(root: Path, relative: str) -> Any:
    """The parsed YAML of one file under the root.

    A reason names the file under the root, and no path of the host.
    """
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise _InstallRefused(f"{relative} is not a regular file")
    try:
        return yaml.safe_load(path.read_bytes().decode("utf-8"))
    except OSError as error:
        reason = error.strerror or "no reason given"
        raise _InstallRefused(f"{relative} was not read: {reason}") from error
    except UnicodeError as error:
        raise _InstallRefused(f"{relative} is not UTF-8 text") from error
    except yaml.YAMLError as error:
        raise _InstallRefused(f"{relative} is not YAML") from error


def _block(
    document: Any, label: str, source: str, members: Mapping[str, frozenset[str]]
) -> Mapping[Any, Any]:
    """One mapping of a description, with no member that this module does not read."""
    if not isinstance(document, Mapping):
        raise _InstallRefused(f"{source} states no mapping at {label}")
    other = sorted(str(name) for name in document if name not in members[label])
    if other:
        raise _InstallRefused(
            f"{source} states a member of {label} that this tool does not read: "
            f"{', '.join(other)}"
        )
    return document


def _text(block: Mapping[Any, Any], name: str, label: str, source: str) -> str:
    """A text that a description states. An absent text is not given a default."""
    value = block.get(name)
    if type(value) is not str or not value:
        raise _InstallRefused(f"{source} states no text at {name} of {label}")
    return value


def _hand_written(
    block: Mapping[Any, Any], name: str, label: str, source: str
) -> Mapping[Any, Any]:
    """The hand-written values of a description. An empty mapping states none."""
    value = block.get(name)
    if not isinstance(value, Mapping):
        raise _InstallRefused(f"{source} states no mapping at {name} of {label}")
    return value


def _target_description(root: Path, source: str) -> dict[str, Any]:
    """The install inputs that the target's Application states."""
    application = _document(root, source)
    if not isinstance(application, Mapping) or application.get("kind") != (
        "Application"
    ):
        raise _InstallRefused(f"{source} is not an Application")
    members = _APPLICATION_MEMBERS
    spec = _block(application.get("spec"), "spec", source, members)
    chart = _block(spec.get("source"), "spec.source", source, members)
    helm = _block(chart.get("helm"), "spec.source.helm", source, members)
    destination = _block(spec.get("destination"), "spec.destination", source, members)
    files = helm.get("valueFiles")
    if (
        not isinstance(files, list)
        or len(files) != 1
        or type(files[0]) is not str
        or not files[0].startswith("/")
    ):
        raise _InstallRefused(
            f"{source} does not name one values file from the root of the repository"
        )
    return {
        "chart": {
            "path": _text(chart, "path", "spec.source", source),
            "repository": _text(chart, "repoURL", "spec.source", source),
            "revision": _text(chart, "targetRevision", "spec.source", source),
        },
        "release": {
            "name": _text(helm, "releaseName", "spec.source.helm", source),
            "namespace": _text(destination, "namespace", "spec.destination", source),
        },
        "valuesFile": files[0][1:],
        "handWrittenValues": _hand_written(
            helm, "valuesObject", "spec.source.helm", source
        ),
    }


def _baseline_description(root: Path, source: str) -> dict[str, Any]:
    """The install inputs that the baseline's description states."""
    members = _INSTALL_MEMBERS
    label = "the document"
    document = _block(_document(root, source), label, source, members)
    if (
        document.get("apiVersion") != INSTALL_SCHEMA
        or document.get("kind") != "BaselineInstallInputs"
    ):
        raise _InstallRefused(
            f"{source} is not a BaselineInstallInputs document of {INSTALL_SCHEMA}"
        )
    chart = _block(document.get("chart"), "chart", source, members)
    release = _block(document.get("release"), "release", source, members)
    return {
        "chart": {
            "path": _text(chart, "path", "chart", source),
            "repository": _text(chart, "repository", "chart", source),
            "revision": _text(chart, "revision", "chart", source),
        },
        "release": {
            "name": _text(release, "name", "release", source),
            "namespace": _text(release, "namespace", "release", source),
        },
        "valuesFile": _text(document, "valuesFile", label, source),
        "handWrittenValues": _hand_written(
            document, "handWrittenValues", label, source
        ),
    }


def _chart_content(root: Path, directory: str, source: str) -> tuple[str, str, Any]:
    """The version of a chart, the digest of its files, and its default values.

    The digest is over the files that a render reads: the chart document, the
    default values, the values schema, and each file under the templates. Each
    file is stated by its own SHA-256 and its path in the chart, in the order
    of the paths.
    """
    if not _plain_path(directory):
        raise _InstallRefused(
            f"{source} names a chart path that is not one relative POSIX path of "
            "plain segments"
        )
    templates = root / directory / _CHART_TEMPLATES
    names = list(_CHART_FILES)
    if templates.is_dir() and not templates.is_symlink():
        names.extend(
            sorted(
                path.relative_to(root / directory).as_posix()
                for path in templates.rglob("*")
                if not path.is_dir()
            )
        )
    if len(names) == len(_CHART_FILES):
        raise _InstallRefused(f"{directory} holds no template")
    digest = hashlib.sha256()
    for name in names:
        path = root / directory / name
        if path.is_symlink() or not path.is_file():
            raise _InstallRefused(f"{directory}/{name} is not a regular file")
        try:
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            reason = error.strerror or "no reason given"
            raise _InstallRefused(
                f"{directory}/{name} was not read: {reason}"
            ) from error
        digest.update(f"{content}  {name}\n".encode())
    chart = _document(root, f"{directory}/{_CHART_FILES[0]}")
    if not isinstance(chart, Mapping):
        raise _InstallRefused(f"{directory}/{_CHART_FILES[0]} is not a mapping")
    version = _text(chart, "version", "the chart document", directory)
    defaults = _document(root, f"{directory}/{_CHART_FILES[1]}")
    if not isinstance(defaults, Mapping):
        raise _InstallRefused(f"{directory}/{_CHART_FILES[1]} is not a mapping")
    return version, digest.hexdigest(), defaults


def _merged(base: Any, over: Any) -> Any:
    """The second document over the first, as Helm merges two values documents.

    A mapping is merged member by member, and any other value replaces the
    earlier one. A null in the second document removes the member, as the Helm
    documentation states for a null in a later values document.
    """
    if isinstance(base, Mapping) and isinstance(over, Mapping):
        merged = dict(base)
        for name, value in over.items():
            if value is None:
                merged.pop(name, None)
            elif name in base:
                merged[name] = _merged(base[name], value)
            else:
                merged[name] = value
        return merged
    return over


def _at(document: Any, pointer: str) -> Any:
    """The value at a pointer of plain tokens, or the absent marker."""
    for token in pointer.split("/")[1:]:
        if not isinstance(document, Mapping) or token not in document:
            return _ABSENT
        document = document[token]
    return document


def _install_findings(
    sides: Mapping[str, DeclaredRelease],
    install: Mapping[str, Mapping[str, Any]],
    differences: Sequence[Mapping[str, Any]],
) -> list[Finding]:
    findings = _layer_findings("baseline-install-differs", "install", differences)
    for side, declared in sides.items():
        expected = f"{declared.directory}/{GENERATED_FILES[0]}"
        stated = install[side]["valuesFile"]
        if stated != expected:
            findings.append(
                Finding(
                    "baseline-install-differs",
                    f"install: {side} /valuesFile",
                    f"the {side} names {json.dumps(stated)}; the generated values "
                    f"file of its release is {json.dumps(expected)}",
                )
            )
    return findings


def _effective_findings(
    effective: Mapping[str, Any], differences: Sequence[Mapping[str, Any]]
) -> tuple[list[Finding], dict[str, dict[str, int | None]]]:
    findings = _layer_findings(
        "baseline-effective-values-differ", "effective", differences
    )
    stated: dict[str, dict[str, int | None]] = {}
    for side, expected in TOPOLOGY.items():
        raw = {
            "apiReplicas": _member(effective[side], "api", "replicaCount"),
            "runtimeReplicas": _member(effective[side], "runtime", "replicaCount"),
        }
        stated[side] = {name: _whole(found) for name, found in raw.items()}
        findings.extend(
            Finding(
                "baseline-effective-values-differ",
                f"effective: {side} {name}",
                f"the chart receives {json.dumps(_plain(found))} on the {side}; "
                f"the comparison needs the whole number {expected[name]}",
            )
            for name, found in raw.items()
            if _whole(found) != expected[name]
        )
    return findings, stated


def _readiness(
    effective: Mapping[str, Any],
) -> tuple[list[Finding], dict[str, dict[str, Any]]]:
    """Each readiness input of each side, and a finding for each that is absent."""
    findings = []
    stated: dict[str, dict[str, Any]] = {}
    for side in TOPOLOGY:
        stated[side] = {}
        for pointer in READINESS_INPUTS:
            found = _at(effective[side], pointer)
            if found is _ABSENT or found is None:
                findings.append(
                    Finding(
                        "baseline-readiness-input-absent",
                        f"effective: {side} {pointer}",
                        f"no values document of the {side} states this readiness "
                        "input, and no default is assumed for it",
                    )
                )
            else:
                stated[side][pointer] = _plain(found)
    return findings, stated


def _unresolved(effective: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Each input of a controlled comparison that no committed file resolves."""
    without_digest = [
        side
        for side in TOPOLOGY
        if side not in effective
        or type(_at(effective[side], _API_IMAGE_DIGEST)) is not str
        or not _at(effective[side], _API_IMAGE_DIGEST)
    ]
    entries: list[dict[str, Any]] = []
    if without_digest:
        entries.append(
            {
                "input": "api-image-digest",
                "path": _API_IMAGE_DIGEST,
                "sides": without_digest,
                "statement": "No committed file states the API image digest of "
                "this side. An operator supplies it at install. A run must give "
                "both sides one digest.",
            }
        )
    entries.append(
        {
            "input": "caller-profile",
            "sides": list(TOPOLOGY),
            "statement": "No caller profile exists in this repository. A run "
            "must give both sides one revision of one caller profile.",
        }
    )
    return entries


def build_record(
    root: Path = REPO_ROOT,
    baseline: DeclaredRelease | None = None,
    target: DeclaredRelease | None = None,
) -> dict[str, Any]:
    """The comparison record of the baseline and the target, from the files of ``root``.

    The record states each difference of each layer, the state of each rule, and
    each finding. The result is ``COMPARABLE`` when no rule is broken, and
    ``REFUSED`` when one is. This reads files and writes none. It reads no
    committed generated file: both releases are derived from their declared inputs.
    """
    baseline = baseline_profile() if baseline is None else baseline
    target = target_release() if target is None else target
    sides = {"baseline": baseline, "target": target}

    findings: list[Finding] = []
    differences: dict[str, list[dict[str, Any]]] = {}
    compared: dict[str, int] = {}
    evaluated = {"baseline-declaration-differs", "baseline-sources-refused"}

    differences["declaration"], compared["declaration"] = _differences(
        "declaration", _declaration(baseline), _declaration(target)
    )
    findings.extend(_declaration_findings(baseline, differences["declaration"]))

    derived = {}
    for side, declared in sides.items():
        try:
            derived[side] = derive(declared, root)
        except SourcesRefused as refused:
            findings.append(
                Finding(
                    "baseline-sources-refused",
                    f"{side}: declared inputs",
                    f"nothing was compared: {refused.reason}",
                )
            )

    sources = {"baseline": INSTALL_PATH, "target": APPLICATIONS.get(TARGET_KEY)}
    readers = {"baseline": _baseline_description, "target": _target_description}
    install: dict[str, dict[str, Any]] = {}
    defaults: dict[str, Any] = {}
    hand_written: dict[str, Any] = {}
    evaluated.add("baseline-install-inputs-refused")
    for side, source in sources.items():
        try:
            if source is None:
                raise _InstallRefused(
                    f"no Application is declared for the key {TARGET_KEY}"
                )
            description = readers[side](root, source)
            if not _plain_path(description["valuesFile"]):
                raise _InstallRefused(
                    f"{source} names a values file that is not one relative POSIX "
                    "path of plain segments"
                )
            version, digest, defaults[side] = _chart_content(
                root, description["chart"]["path"], source
            )
            description["chart"].update(version=version, contentSha256=digest)
            hand_written[side] = description["handWrittenValues"]
            install[side] = _plain(description)
        except _InstallRefused as refused:
            findings.append(
                Finding(
                    "baseline-install-inputs-refused",
                    f"{side}: install inputs",
                    f"no install input of this side was compared: {refused.reason}",
                )
            )
    if len(install) == len(sides):
        evaluated.add("baseline-install-differs")
        differences["install"], compared["install"] = _differences(
            "install", install["baseline"], install["target"]
        )
        findings.extend(_install_findings(sides, install, differences["install"]))

    releases: dict[str, Any] = {}
    topology: dict[str, dict[str, int | None]] = {}
    effective: dict[str, Any] = {}
    effective_topology: dict[str, dict[str, int | None]] = {}
    readiness: dict[str, dict[str, Any]] = {}
    if len(derived) == len(sides):
        evaluated.update(_RELEASE_RULES)
        contracts = {
            side: _load_yaml(root / declared.contract)
            for side, declared in sides.items()
        }
        values = {side: derived[side].values.as_document() for side in sides}
        releases = {side: derived[side].release.as_document() for side in sides}
        for layer, documents, rule_id in (
            ("contract", contracts, "baseline-contract-differs"),
            ("values", values, "baseline-values-differ"),
            ("release", releases, "baseline-release-differs"),
        ):
            differences[layer], compared[layer] = _differences(
                layer, documents["baseline"], documents["target"]
            )
            findings.extend(_layer_findings(rule_id, layer, differences[layer]))
        found, topology = _topology_findings(contracts, values)
        findings.extend(found)
        findings.extend(_version_findings(contracts))
        if len(install) == len(sides):
            evaluated.update(
                ("baseline-effective-values-differ", "baseline-readiness-input-absent")
            )
            effective = {
                side: _merged(_merged(defaults[side], values[side]), hand_written[side])
                for side in sides
            }
            differences["effective"], compared["effective"] = _differences(
                "effective", effective["baseline"], effective["target"]
            )
            found, effective_topology = _effective_findings(
                effective, differences["effective"]
            )
            findings.extend(found)
            found, readiness = _readiness(effective)
            findings.extend(found)

    order = {rule.rule_id: index for index, rule in enumerate(RULES)}
    findings.sort(key=lambda finding: (order[finding.rule_id], finding.subject))
    broken = {finding.rule_id for finding in findings}
    return {
        "apiVersion": RECORD_SCHEMA,
        "kind": "BaselineProfileComparison",
        "result": REFUSED if findings else COMPARABLE,
        "intendedVariable": {
            "name": "serving runtime replica count",
            "baseline": TOPOLOGY["baseline"]["runtimeReplicas"],
            "target": TOPOLOGY["target"]["runtimeReplicas"],
        },
        "targetKey": TARGET_KEY,
        "declarations": {
            side: _declaration(declared) for side, declared in sides.items()
        },
        "releases": releases,
        "topology": topology,
        "installSources": sources,
        "installInputs": install,
        "effectiveTopology": effective_topology,
        "readinessInputs": readiness,
        "unresolvedInputs": _unresolved(effective),
        "experimentEligibility": ELIGIBILITY,
        "pathsCompared": compared,
        "differences": {
            layer: differences[layer] for layer in _LAYERS if layer in differences
        },
        "permittedDifferences": {
            layer: dict(sorted(PERMITTED[layer].items())) for layer in _LAYERS
        },
        "rules": [
            {
                "id": rule.rule_id,
                "statement": rule.statement,
                "state": (
                    NOT_EVALUATED
                    if rule.rule_id not in evaluated
                    else NOT_HELD
                    if rule.rule_id in broken
                    else HELD
                ),
            }
            for rule in RULES
        ],
        "findings": [
            {"rule": f.rule_id, "subject": f.subject, "detail": f.detail}
            for f in findings
        ],
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def record_text(record: Mapping[str, Any]) -> str:
    """The bytes a committed record holds."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------------------------
# The committed profile
# --------------------------------------------------------------------------


def _record_findings(record: Mapping[str, Any]) -> list[Finding]:
    return [
        Finding(found["rule"], found["subject"], found["detail"])
        for found in record["findings"]
    ]


def verify_profile(root: Path = REPO_ROOT) -> tuple[Finding, ...]:
    """Every way the committed profile under ``root`` breaks a rule.

    An empty result means that the comparison is ``COMPARABLE``, that the
    committed baseline release is what its declared sources derive, and that the
    committed record is the record this tree gives. This reads files and writes
    none.
    """
    record = build_record(root)
    findings = _record_findings(record)
    baseline = baseline_profile()
    findings.extend(
        Finding(
            "baseline-release-drifted",
            f"{baseline.directory}: {finding.subject}",
            f"{finding.rule_id}: {finding.detail}",
        )
        for finding in verify(baseline, root)
    )
    path = root / RECORD_PATH
    if not path.is_file() or path.is_symlink():
        findings.append(
            Finding(
                "baseline-record-stale", RECORD_PATH, "the record is not a regular file"
            )
        )
    elif path.read_bytes() != record_text(record).encode("utf-8"):
        findings.append(
            Finding(
                "baseline-record-stale",
                RECORD_PATH,
                "the committed record is not the record this tree gives. Read the "
                "difference, then write it again: python -m tools.baseline_profile "
                "--write",
            )
        )
    return tuple(findings)


def write_profile(root: Path = REPO_ROOT) -> tuple[bool, bool]:
    """Write the baseline release and the comparison record from the files of ``root``.

    Returns whether the release was written and whether the record was written.
    Each is ``False`` when the committed bytes were already the derived ones.

    Raises:
        WriteRefused: the comparison is ``REFUSED``, or the record path is not a
            regular file; nothing is touched.
        RegenerationRefused: the profile directory holds something the platform
            did not write, or a staging directory is left beside it; nothing is
            touched.
        OSError: a file could not be removed or written. The release is written
            before the record, so the two can then be out of step.
            :func:`verify_profile` reports that, and a second write repairs it.
    """
    record = build_record(root)
    if record["result"] != COMPARABLE:
        raise WriteRefused(_record_findings(record))
    path = root / RECORD_PATH
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise WriteRefused(
            [
                Finding(
                    "baseline-record-stale",
                    RECORD_PATH,
                    "the record path is not a regular file",
                )
            ]
        )
    baseline = baseline_profile()
    (root / baseline.directory).parent.mkdir(parents=True, exist_ok=True)
    release_written = regenerate(baseline, root)
    text = record_text(record).encode("utf-8")
    if path.is_file() and path.read_bytes() == text:
        return release_written, False
    path.write_bytes(text)
    return release_written, True
