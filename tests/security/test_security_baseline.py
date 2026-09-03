"""Deterministic checks over the V1 threat model and security baseline.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness, and no scanner is invoked.

What this suite establishes is that the committed baseline is internally
consistent, that it agrees with the architecture, telemetry catalog, and test
strategy already committed beside it, and above all that a control's status is
*derived* rather than asserted: the enforcement kind and runtime scope a control
declares determine its status through a committed table, the test function or
shell guard it names has to exist, the evidence record it names has to be
committed, and a declared status that disagrees with the derived one is a
failing test rather than a judgement call. It also holds every manifest this
repository publishes to eight pod-security assertions, a digest pin, and the rule
that none of them exposes a service outside the cluster; it recomputes from the
data every count those documents state in prose; and it refuses the vocabulary of
a security posture in any sentence of any Markdown document committed here, and
in the baseline data, that is not denying it.

That last scope is deliberate, and it was widened after a review found it too
narrow. A vocabulary check reading only `docs/security/` would pass while the
top-level README described a posture this project does not have -- which is the
failure T-18 names, happening inside the control for T-18.

What it does not establish is that anything is defended. No component in this
repository authenticates a caller, authorises a request, enforces a network
policy, or applies a security context to a pod it deployed, because none of them
deploys a pod or serves a request. No secret scanner, image scanner, or
dependency auditor has been run and recorded, and no security assessment or
penetration test has been performed. This suite reads a threat model; it does not
test a system.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
SECURITY_DIR = REPO_ROOT / "docs" / "security"
BASELINE_PATH = SECURITY_DIR / "security-baseline.v1alpha1.json"
THREAT_MODEL_PATH = SECURITY_DIR / "threat-model.md"
CONTROL_MATRIX_PATH = SECURITY_DIR / "control-matrix.md"
DEFERRED_RISK_PATH = SECURITY_DIR / "deferred-risks.md"
DECISION_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0008-v1-security-baseline.md"
)
ARCHITECTURE_PATH = REPO_ROOT / "docs" / "architecture" / "system-architecture.md"
CATALOG_PATH = REPO_ROOT / "docs" / "telemetry" / "telemetry-catalog.v1alpha1.json"
STRATEGY_PATH = REPO_ROOT / "docs" / "testing" / "test-strategy.v1alpha1.json"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
GITLEAKS_PATH = REPO_ROOT / ".gitleaks.toml"
DEPLOY_DIR = REPO_ROOT / "deploy"
PROOF_DIR = REPO_ROOT / "docs" / "proof"
THIS_MODULE = Path(__file__)

EXPECTED_BASELINE_ID = "https://inferops.io/security/security-baseline.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

# This suite is collected by the documentation layer of the test strategy, which
# has to name the directory it lives in or the layer selects nothing here.
DECLARING_LAYER = "documentation"
DECLARED_PATH = "tests/security"

# The public claim this baseline supports.
BASELINE_CLAIM = "a-security-control-cannot-claim-enforcement-it-does-not-have"

# Identifiers in the baseline are lowercase, hyphen-separated slugs.
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# Threat, risk, and exception identifiers are a prefix and a two-digit number.
PREFIXED_ID = re.compile(r"^(T|DR|EX)-\d{2}$")

# An identifier as a document publishes it: an inline code span in the first
# column of a Markdown table row.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([A-Za-z_][A-Za-z0-9_.:-]*)`\s*\|", flags=re.MULTILINE
)

# A prefixed identifier as a document publishes it, in the first column of a
# Markdown table row and without a code span, because these read as labels.
FIRST_TABLE_COLUMN_PLAIN = re.compile(
    r"^\|\s*\*{0,2}((?:T|DR|EX)-\d{2})\*{0,2}\s*\|", flags=re.MULTILINE
)

# A Python test function definition, for confirming that a control's named
# verification exists rather than trusting that somebody wrote it.
TEST_DEF = "def {symbol}("

# A container image reference pinned by digest rather than by tag alone.
DIGEST_PINNED = re.compile(r"@sha256:[0-9a-f]{64}$")

# A personal filesystem path: a Windows user directory, a POSIX home directory,
# or either of those reached through a mount point. The mount case is not
# hypothetical here - this project is developed on Windows through a POSIX
# shell, where a home directory is routinely written `/mnt/c/Users/...`, so a
# pattern anchored to the start of a path would miss the realistic shape.
PERSONAL_PATH = re.compile(
    r"[A-Za-z]:[\\/](?:Users|home)[\\/]"
    r"|[\\/](?:Users|home)[\\/][A-Za-z0-9._-]+[\\/]",
    flags=re.IGNORECASE,
)

# What a sentence has to carry for a reserved term in it to be a denial rather
# than a claim.
DENIAL = re.compile(
    r"\b(?:no|not|never|none|neither|nothing|nobody|cannot|without|absent|absence"
    r"|deferred|defer|unproven|unverified|untested|unenforced|refuse[sd]?|refusing"
    r"|reserved|forbidden|forbids|prohibit(?:s|ed|ion)?|denie[sd]|deny|denial"
    r"|stops?|blocked|blocker|gap|overclaim(?:s|ed|ing)?|claim(?:s|ed)? nothing"
    r"|may not|must not|does not|do not|is not|are not|has not|have not|had not"
    r"|would not|will not|cannot be|rather than|instead of)\b",
    flags=re.IGNORECASE,
)

FENCE = re.compile(r"^[ \t]*```")

# A Markdown list item marker, which starts a new unit of prose.
LIST_ITEM = re.compile(r"^(?:[-*+]|\d+\.)\s")

REQUIRED_ACTOR_FIELDS = (
    "actorId",
    "name",
    "trustedTo",
    "notTrustedTo",
    "reachesBoundaries",
)

REQUIRED_BOUNDARY_FIELDS = (
    "boundaryId",
    "name",
    "whatCrosses",
    "enforcedToday",
    "notDefended",
    "mappedInArchitecture",
    "owner",
)

REQUIRED_ASSET_FIELDS = (
    "assetId",
    "name",
    "whatItIs",
    "boundary",
    "worstCase",
    "ownedBy",
)

REQUIRED_THREAT_FIELDS = (
    "threatId",
    "title",
    "category",
    "assetId",
    "boundaryId",
    "actorId",
    "abuseCase",
    "impact",
    "controls",
    "residualRisk",
    "deferredRiskRef",
)

REQUIRED_CONTROL_FIELDS = (
    "controlId",
    "statement",
    "boundaryId",
    "threats",
    "verification",
    "runtimeScope",
    "specifiedFor",
    "restsOnAConfiguration",
    "v1Status",
    "owner",
    "evidenceRef",
    "whatItDoesNotVerify",
)

REQUIRED_VERIFICATION_FIELDS = ("kind", "ref", "symbol")

REQUIRED_RISK_FIELDS = (
    "riskId",
    "statement",
    "boundaryId",
    "threats",
    "whyDeferred",
    "whatWouldHaveToBeTrue",
    "notClaimed",
    "blocksProductionUse",
)

REQUIRED_EXCEPTION_FIELDS = (
    "exceptionId",
    "statement",
    "acceptedIn",
    "compensatingControl",
    "residualRisk",
    "revisitedWhen",
    "deferredRiskRef",
)

REQUIRED_PROHIBITION_FIELDS = ("ruleId", "statement", "enforcedBy", "testRef")

REQUIRED_TERM_FIELDS = ("term", "whyReserved")

REQUIRED_QUESTION_FIELDS = ("questionId", "question", "whyNotAnswered")

REQUIRED_LIMITATION_FIELDS = ("limitationId", "statement")

# The six properties every pod specification and container in this repository
# carries. They are listed here rather than read from the data so that a change
# to the data cannot quietly reduce what is checked.
REQUIRED_POD_SECURITY = {
    "automountServiceAccountToken": False,
    "securityContext.runAsNonRoot": True,
    "securityContext.seccompProfile.type": "RuntimeDefault",
}

REQUIRED_CONTAINER_SECURITY = {
    "securityContext.allowPrivilegeEscalation": False,
    "securityContext.readOnlyRootFilesystem": True,
}

# Directory prefixes that hold generated host state, tool caches, the project
# virtual environment, or build output. Nothing under any of them may be
# committed, and each has to be named in .gitignore.
#
# The environment and the build directories were added when ADR 0009 adopted a
# dependency manager and a build backend. They are not a widening of what may be
# published: `.venv/` holds an installed third party's files, several of which
# carry the interpreter path of whichever machine created them, and `dist/` and
# `build/` hold artifacts a build produced. Reading them as candidates for
# publication was a check reporting on somebody else's code.
IGNORED_PREFIXES = (
    ".kube/",
    ".artifacts/",
    ".ruff_cache/",
    ".mypy_cache/",
    ".pytest_cache/",
    "__pycache__/",
    ".venv/",
    "build/",
    "dist/",
    # `V1-S2-005-PR2` found this list stops one directory short: `.cache/`
    # holds the workspace-scoped model cache and the baseline's own raw and
    # summary output, and this walk reported a hash-verified model artifact
    # under it as a candidate for publication on the first host that had
    # actually acquired one. `.gitignore` already ignores it; this list
    # only did not know.
    ".cache/",
)

# Extensions a model artifact arrives in. None belongs in public history.
MODEL_ARTIFACT_SUFFIXES = (
    ".gguf",
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".bin",
    ".onnx",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


BASELINE = _load(BASELINE_PATH)
CATALOG = _load(CATALOG_PATH)
STRATEGY = _load(STRATEGY_PATH)

ACTORS = BASELINE["actors"]
BOUNDARIES = BASELINE["boundaries"]
ASSETS = BASELINE["assets"]
THREATS = BASELINE["threats"]
CONTROLS = BASELINE["controls"]
RISKS = BASELINE["deferredRisks"]
EXCEPTIONS = BASELINE["exceptions"]
PROHIBITIONS = BASELINE["prohibitions"]
RESERVED_TERMS = BASELINE["reservedTerms"]
LIMITATIONS = BASELINE["limitations"]
OPEN_QUESTIONS = BASELINE["openQuestions"]

BOUNDARY_IDS = {row["boundaryId"] for row in BOUNDARIES}
ASSET_IDS = {row["assetId"] for row in ASSETS}
ACTOR_IDS = {row["actorId"] for row in ACTORS}
THREAT_IDS = {row["threatId"] for row in THREATS}
CONTROL_IDS = {row["controlId"] for row in CONTROLS}
RISK_IDS = {row["riskId"] for row in RISKS}

LEVEL_BY_KIND = {
    row["kindId"]: row["enforcementLevel"] for row in BASELINE["enforcementKinds"]
}
SCOPE_IDS = {row["scopeId"] for row in BASELINE["runtimeScopes"]}
STATUS_BY_ID = {row["statusId"]: row for row in BASELINE["controlStatuses"]}
DERIVATION = {
    (row["enforcementLevel"], row["runtimeScope"]): row["status"]
    for row in BASELINE["statusDerivation"]["rules"]
}


def _strip_fences(text: str) -> str:
    """Drop fenced code blocks, so that a command sample is not read as prose."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def _sentences(text: str) -> list[str]:
    """Split prose into sentences, joining lines that a sentence wraps across.

    Two units are kept whole rather than split. A Markdown table row is one
    unit of meaning: the reserved-term table pairs a term with the reason it is
    reserved, and splitting the row would separate a term from its denial. And
    a sentence that wraps across a hard line break is one sentence: splitting on
    the newline would cut a denial away from the term it denies, which reports a
    formatting choice as a claim.
    """
    out: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if not paragraph:
            return
        joined = " ".join(paragraph)
        for piece in re.split(r"(?<=[.!?])\s+", joined):
            if piece.strip():
                out.append(piece)
        paragraph.clear()

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(">"):
            # A blockquote wraps like any other prose; the marker is not content.
            stripped = stripped.lstrip("> ").strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith(("|", "#")):
            flush()
            out.append(line)
            continue
        if LIST_ITEM.match(stripped):
            # A list item starts a unit; joining it to the item above would put
            # one item's denial in front of another item's claim.
            flush()
        paragraph.append(stripped)
    flush()
    return out


# Keys whose values are identifiers, paths, or symbols rather than prose. A
# reserved term inside a test function name is not a claim about anything.
NON_PROSE_KEYS = frozenset(
    {
        "$id",
        "contractVersion",
        "symbol",
        "ref",
        "testRef",
        "acceptedIn",
        "compensatingControl",
        "enforcedBy",
        "owner",
        "category",
        "status",
        "enforcementLevel",
        "term",
        "v1Status",
        "runtimeScope",
    }
)


def _prose_strings(node: object, path: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """Every prose string in the data, with the key path that reached it.

    Three things are excluded. The reserved-term block is the list of terms, so
    it is the one place a term appears as data rather than as a claim. A key
    whose value is an identifier, a path, or a symbol is not prose: a reserved
    term inside a test function name asserts nothing about anything. And a
    string inside a list is a cross-reference rather than a sentence, because
    every list of prose in this file is a list of objects.
    """
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "reservedTerms" or key in NON_PROSE_KEYS:
                continue
            if key.endswith(("Id", "Ref")):
                continue
            found.extend(_prose_strings(value, (*path, key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, str):
                continue
            found.extend(_prose_strings(value, (*path, str(index))))
    elif isinstance(node, str):
        found.append((".".join(path), node))
    return found


def _repository_files() -> list[Path]:
    """Every file in the working tree outside the ignored directories.

    This is a filesystem walk rather than a `git ls-files` call, so that the
    suite needs nothing but the standard library and reads exactly what is on
    disk. The difference matters in one direction only: an untracked file that
    is not ignored is reported here and would not be reported by git, which is
    the safe direction for a check about what gets published.
    """
    skip = {".git"} | {prefix.rstrip("/") for prefix in IGNORED_PREFIXES}
    out: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(REPO_ROOT).parts)
        if parts & skip:
            continue
        out.append(path)
    return sorted(out)


REPOSITORY_FILES = _repository_files()


def _manifest_documents() -> list[tuple[str, dict]]:
    """Every YAML document under deploy/, with the path that produced it."""
    out: list[tuple[str, dict]] = []
    for path in sorted(DEPLOY_DIR.rglob("*.yaml")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for index, document in enumerate(
            yaml.safe_load_all(path.read_text(encoding="utf-8"))
        ):
            if isinstance(document, dict):
                out.append((f"{rel}[{index}]", document))
    return out


MANIFESTS = _manifest_documents()


def _pod_specs() -> list[tuple[str, dict]]:
    """Every pod specification in every manifest, with where it came from."""
    out: list[tuple[str, dict]] = []
    for label, document in MANIFESTS:
        spec = document.get("spec")
        if not isinstance(spec, dict):
            continue
        template = spec.get("template")
        if isinstance(template, dict) and isinstance(template.get("spec"), dict):
            out.append((label, template["spec"]))
        elif document.get("kind") == "Pod":
            out.append((label, spec))
    return out


POD_SPECS = _pod_specs()


def _containers() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for label, spec in POD_SPECS:
        for key in ("initContainers", "containers"):
            for container in spec.get(key) or []:
                out.append((f"{label}.{key}[{container.get('name')}]", container))
    return out


CONTAINERS = _containers()


def _images() -> list[tuple[str, str]]:
    """Every image reference anywhere in any manifest, however it is nested."""
    out: list[tuple[str, str]] = []

    def walk(node: object, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "image" and isinstance(value, str):
                    out.append((f"{trail}.{key}", value))
                else:
                    walk(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{trail}[{index}]")

    for label, document in MANIFESTS:
        walk(document, label)
    return out


IMAGES = _images()


ABSENT = object()


def _dig(node: dict, dotted: str):
    """Read a dotted path out of a parsed manifest, or ABSENT if it is not there.

    An absent field and a field set to `false` are different failures, and a
    sentinel is what keeps them different.
    """
    current: object = node
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return ABSENT
        current = current[part]
    return current


# --------------------------------------------------------------------------
# Shape: the baseline says everything it has to say
# --------------------------------------------------------------------------


def test_the_baseline_declares_its_identity_and_contract_version() -> None:
    assert BASELINE["$id"] == EXPECTED_BASELINE_ID
    assert BASELINE["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_the_baseline_is_not_empty() -> None:
    assert len(ACTORS) >= 4
    assert len(BOUNDARIES) >= 5
    assert len(ASSETS) >= 8
    assert len(THREATS) >= 15
    assert len(CONTROLS) >= 20
    assert len(RISKS) >= 8
    assert len(EXCEPTIONS) >= 3
    assert len(PROHIBITIONS) >= 10
    assert len(LIMITATIONS) >= 8


@pytest.mark.parametrize("row", ACTORS, ids=lambda row: row["actorId"])
def test_every_actor_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_ACTOR_FIELDS)
    assert SLUG.match(row["actorId"])
    assert row["reachesBoundaries"]


@pytest.mark.parametrize("row", BOUNDARIES, ids=lambda row: row["boundaryId"])
def test_every_boundary_declares_every_required_field(row: dict) -> None:
    expected = set(REQUIRED_BOUNDARY_FIELDS)
    assert expected <= set(row)
    extra = set(row) - expected
    assert extra <= {"extendsArchitecture"}, extra
    assert re.fullmatch(r"B\d", row["boundaryId"])


@pytest.mark.parametrize("row", ASSETS, ids=lambda row: row["assetId"])
def test_every_asset_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_ASSET_FIELDS)
    assert SLUG.match(row["assetId"])


@pytest.mark.parametrize("row", THREATS, ids=lambda row: row["threatId"])
def test_every_threat_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_THREAT_FIELDS)
    assert PREFIXED_ID.match(row["threatId"])
    for field in ("title", "abuseCase", "impact", "residualRisk"):
        assert row[field].strip()


@pytest.mark.parametrize("row", CONTROLS, ids=lambda row: row["controlId"])
def test_every_control_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_CONTROL_FIELDS)
    assert SLUG.match(row["controlId"])
    assert set(row["verification"]) == set(REQUIRED_VERIFICATION_FIELDS)
    assert row["statement"].strip()
    assert row["whatItDoesNotVerify"].strip()


@pytest.mark.parametrize("row", RISKS, ids=lambda row: row["riskId"])
def test_every_deferred_risk_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_RISK_FIELDS)
    assert PREFIXED_ID.match(row["riskId"])
    assert isinstance(row["blocksProductionUse"], bool)


@pytest.mark.parametrize("row", EXCEPTIONS, ids=lambda row: row["exceptionId"])
def test_every_exception_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_EXCEPTION_FIELDS)
    assert PREFIXED_ID.match(row["exceptionId"])


@pytest.mark.parametrize("row", PROHIBITIONS, ids=lambda row: row["ruleId"])
def test_every_prohibition_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_PROHIBITION_FIELDS)
    assert SLUG.match(row["ruleId"])
    assert row["enforcedBy"] in {"test", "review"}


@pytest.mark.parametrize("row", RESERVED_TERMS, ids=lambda row: row["term"])
def test_every_reserved_term_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_TERM_FIELDS)
    assert row["term"] == row["term"].lower()
    assert row["whyReserved"].strip()


@pytest.mark.parametrize("row", OPEN_QUESTIONS, ids=lambda row: row["questionId"])
def test_every_open_question_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_QUESTION_FIELDS)
    assert SLUG.match(row["questionId"])


@pytest.mark.parametrize("row", LIMITATIONS, ids=lambda row: row["limitationId"])
def test_every_limitation_declares_every_required_field(row: dict) -> None:
    assert set(row) == set(REQUIRED_LIMITATION_FIELDS)
    assert SLUG.match(row["limitationId"])


def test_identifiers_are_unique() -> None:
    for label, ids in (
        ("actor", [row["actorId"] for row in ACTORS]),
        ("boundary", [row["boundaryId"] for row in BOUNDARIES]),
        ("asset", [row["assetId"] for row in ASSETS]),
        ("threat", [row["threatId"] for row in THREATS]),
        ("control", [row["controlId"] for row in CONTROLS]),
        ("risk", [row["riskId"] for row in RISKS]),
        ("exception", [row["exceptionId"] for row in EXCEPTIONS]),
        ("rule", [row["ruleId"] for row in PROHIBITIONS]),
        ("term", [row["term"] for row in RESERVED_TERMS]),
        ("limitation", [row["limitationId"] for row in LIMITATIONS]),
    ):
        assert len(ids) == len(set(ids)), f"duplicate {label} identifier"


def test_the_data_points_back_at_the_documents_that_describe_it() -> None:
    for field in (
        "decisionRef",
        "documentRef",
        "controlMatrixRef",
        "deferredRiskRef",
        "architectureRef",
        "telemetryCatalogRef",
        "redactionRef",
        "strategyRef",
        "workloadContractRef",
        "reportingRef",
    ):
        assert (REPO_ROOT / BASELINE[field]).exists(), field


# --------------------------------------------------------------------------
# References: nothing names something that is not there
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", ACTORS, ids=lambda row: row["actorId"])
def test_every_actor_reaches_declared_boundaries(row: dict) -> None:
    assert set(row["reachesBoundaries"]) <= BOUNDARY_IDS


@pytest.mark.parametrize("row", ASSETS, ids=lambda row: row["assetId"])
def test_every_asset_sits_on_a_declared_boundary(row: dict) -> None:
    assert row["boundary"] in BOUNDARY_IDS


@pytest.mark.parametrize("row", THREATS, ids=lambda row: row["threatId"])
def test_every_threat_names_declared_things(row: dict) -> None:
    assert row["assetId"] in ASSET_IDS
    assert row["boundaryId"] in BOUNDARY_IDS
    assert row["actorId"] in ACTOR_IDS
    assert set(row["controls"]) <= CONTROL_IDS
    if row["deferredRiskRef"] is not None:
        assert row["deferredRiskRef"] in RISK_IDS


@pytest.mark.parametrize("row", CONTROLS, ids=lambda row: row["controlId"])
def test_every_control_names_declared_things(row: dict) -> None:
    assert row["boundaryId"] in BOUNDARY_IDS
    assert set(row["threats"]) <= THREAT_IDS
    assert row["threats"], (
        "a control that addresses no threat is a control nobody needs"
    )
    assert row["verification"]["kind"] in LEVEL_BY_KIND
    assert row["runtimeScope"] in SCOPE_IDS
    assert row["v1Status"] in STATUS_BY_ID


@pytest.mark.parametrize("row", RISKS, ids=lambda row: row["riskId"])
def test_every_deferred_risk_names_declared_things(row: dict) -> None:
    assert row["boundaryId"] in BOUNDARY_IDS
    assert set(row["threats"]) <= THREAT_IDS
    assert row["threats"]


@pytest.mark.parametrize("row", EXCEPTIONS, ids=lambda row: row["exceptionId"])
def test_every_exception_names_a_compensating_control_and_a_residual_risk(
    row: dict,
) -> None:
    assert row["compensatingControl"] in CONTROL_IDS
    assert row["residualRisk"].strip()
    assert row["revisitedWhen"].strip()
    assert (REPO_ROOT / row["acceptedIn"]).exists()
    if row["deferredRiskRef"] is not None:
        assert row["deferredRiskRef"] in RISK_IDS


def test_every_control_is_reached_by_a_threat() -> None:
    reached = {control for row in THREATS for control in row["controls"]}
    orphans = CONTROL_IDS - reached
    assert not orphans, f"controls no threat names: {sorted(orphans)}"


def test_the_threat_and_control_references_agree_in_both_directions() -> None:
    for threat in THREATS:
        for control_id in threat["controls"]:
            control = next(row for row in CONTROLS if row["controlId"] == control_id)
            assert threat["threatId"] in control["threats"], (
                f"{threat['threatId']} names {control_id}, which does not name it back"
            )
    for control in CONTROLS:
        for threat_id in control["threats"]:
            threat = next(row for row in THREATS if row["threatId"] == threat_id)
            assert control["controlId"] in threat["controls"], (
                f"{control['controlId']} names {threat_id}, which does not name it back"
            )


def test_every_deferred_risk_is_reached_by_a_threat() -> None:
    reached = {row["deferredRiskRef"] for row in THREATS if row["deferredRiskRef"]}
    orphans = RISK_IDS - reached
    assert not orphans, f"deferred risks no threat names: {sorted(orphans)}"


@pytest.mark.parametrize("row", THREATS, ids=lambda row: row["threatId"])
def test_every_threat_names_a_control_or_a_deferred_risk(row: dict) -> None:
    assert row["controls"] or row["deferredRiskRef"], (
        f"{row['threatId']} names neither a control nor a deferred risk, "
        "which makes it a threat nobody decided about"
    )


# --------------------------------------------------------------------------
# The derivation: a control's status is computed, not asserted
# --------------------------------------------------------------------------


def _derive(control: dict) -> str:
    level = LEVEL_BY_KIND[control["verification"]["kind"]]
    if level == "none":
        return "specified-only" if control["specifiedFor"] else "deferred"
    return DERIVATION[(level, control["runtimeScope"])]


@pytest.mark.parametrize("row", CONTROLS, ids=lambda row: row["controlId"])
def test_declared_control_status_equals_derived_control_status(row: dict) -> None:
    assert row["v1Status"] == _derive(row), (
        f"{row['controlId']} declares {row['v1Status']} and derives {_derive(row)}. "
        "A control's status is derived from the verification it names."
    )


@pytest.mark.parametrize("row", CONTROLS, ids=lambda row: row["controlId"])
def test_a_named_verification_exists(row: dict) -> None:
    verification = row["verification"]
    kind = verification["kind"]
    if kind in {"review", "none"}:
        assert verification["ref"] is None
        assert verification["symbol"] is None
        return

    ref = REPO_ROOT / verification["ref"]
    assert ref.exists(), (
        f"{row['controlId']} names {verification['ref']}, which is not committed"
    )
    body = ref.read_text(encoding="utf-8")
    symbol = verification["symbol"]
    if kind == "automated-test":
        assert TEST_DEF.format(symbol=symbol) in body, (
            f"{row['controlId']} names the test {symbol}, which {verification['ref']} does not define"
        )
    else:
        assert f"{symbol}()" in body, (
            f"{row['controlId']} names the guard {symbol}, which {verification['ref']} does not define"
        )


@pytest.mark.parametrize("row", CONTROLS, ids=lambda row: row["controlId"])
def test_every_evidence_reference_is_a_committed_record(row: dict) -> None:
    if row["evidenceRef"] is None:
        assert not STATUS_BY_ID[row["v1Status"]]["mayBeCalledImplemented"], (
            f"{row['controlId']} claims {row['v1Status']} and cites no evidence record"
        )
        return
    path = REPO_ROOT / row["evidenceRef"]
    assert path.exists(), (
        f"{row['controlId']} cites {row['evidenceRef']}, which is not committed"
    )
    assert path.is_relative_to(PROOF_DIR), (
        "evidence lives under docs/proof/ and nowhere else"
    )


@pytest.mark.parametrize("row", CONTROLS, ids=lambda row: row["controlId"])
def test_an_unenforced_control_says_what_it_is_specified_for_or_is_deferred(
    row: dict,
) -> None:
    level = LEVEL_BY_KIND[row["verification"]["kind"]]
    if level != "none":
        assert row["specifiedFor"] is None, (
            "a control with a verification is enforced rather than specified"
        )
        return
    if row["v1Status"] == "specified-only":
        assert row["specifiedFor"], (
            "a specification names the component it is written for"
        )
    else:
        assert row["specifiedFor"] is None


def test_no_control_claims_to_act_inside_a_running_system() -> None:
    assert BASELINE["securityStatus"]["state"] == "nothing-enforces-at-runtime"
    offenders = [
        row["controlId"] for row in CONTROLS if row["runtimeScope"] == "running-system"
    ]
    assert not offenders, (
        f"{offenders} claim to act inside a running system, and nothing here serves a request"
    )
    assert BASELINE["securityStatus"]["controlsEnforcedInARunningSystem"] == 0


def test_every_declared_status_is_used_and_the_unused_scope_is_the_absent_one() -> None:
    used_status = {row["v1Status"] for row in CONTROLS}
    assert used_status == set(STATUS_BY_ID), (
        f"declared but unused control statuses: {sorted(set(STATUS_BY_ID) - used_status)}"
    )
    used_scope = {row["runtimeScope"] for row in CONTROLS}
    assert SCOPE_IDS - used_scope == {"running-system"}, (
        "the only runtime scope no control uses is the one that would need a running system"
    )


def test_a_control_that_rests_on_a_configuration_says_what_it_does_not_verify() -> None:
    """Checked for every configuration-backed control, not for one by name.

    Hardcoding the single control that has this shape today would pass forever
    and would say nothing about the second one somebody adds.
    """
    backed = [row for row in CONTROLS if row["restsOnAConfiguration"]]
    assert backed, "no control declares that it rests on a configuration"
    for row in backed:
        assert "not a result" in row["whatItDoesNotVerify"], (
            f"{row['controlId']} rests on a configuration and does not say that a "
            "configuration is not a result"
        )
    layer = next(row for row in STRATEGY["layers"] if row["layerId"] == "security-scan")
    assert layer["v1Status"] == "planned", (
        "a scan configuration is committed and no run of the scanner is recorded, "
        "so the security-scan layer stays planned"
    )
    assert BASELINE["securityStatus"]["secretScannerRunsRecorded"] == 0


def test_the_control_that_reads_the_scan_configuration_is_the_one_that_declares_it() -> (
    None
):
    """The flag is data, so it is checked against what the verification does.

    A control could set the flag to false and keep its disclaimer-free wording,
    which is why the flag itself is held to the file the verification reads.
    """
    for row in CONTROLS:
        symbol = row["verification"]["symbol"] or ""
        reads_configuration = "secret_scan_configuration" in symbol
        assert row["restsOnAConfiguration"] == reads_configuration, (
            f"{row['controlId']} declares restsOnAConfiguration="
            f"{row['restsOnAConfiguration']} and its verification says otherwise"
        )


def test_the_status_derivation_covers_every_reachable_combination() -> None:
    for kind, level in LEVEL_BY_KIND.items():
        if level == "none":
            continue
        for scope in SCOPE_IDS:
            if scope == "running-system":
                continue
            assert (level, scope) in DERIVATION, f"no derivation for {kind} at {scope}"


# --------------------------------------------------------------------------
# The manifests: six pod-security properties and least exposure
# --------------------------------------------------------------------------


def test_the_manifests_were_actually_found() -> None:
    assert len(MANIFESTS) >= 5
    assert len(POD_SPECS) >= 4
    assert len(CONTAINERS) >= 4
    assert len(IMAGES) >= 5


@pytest.mark.parametrize("label,image", IMAGES, ids=lambda value: str(value)[:60])
def test_every_manifest_image_is_pinned_by_digest(label: str, image: str) -> None:
    assert DIGEST_PINNED.search(image), (
        f"{label} names {image}, which is a tag rather than a digest. "
        "A tag is a label that can be moved."
    )


@pytest.mark.parametrize("label,spec", POD_SPECS, ids=lambda value: str(value)[:60])
def test_every_pod_spec_carries_every_required_pod_security_field(
    label: str, spec: dict
) -> None:
    for dotted, expected in REQUIRED_POD_SECURITY.items():
        actual = _dig(spec, dotted)
        assert actual == expected, (
            f"{label} sets {dotted} to {actual!r}, expected {expected!r}"
        )
    assert _dig(spec, "securityContext.runAsUser") is not ABSENT, (
        f"{label} declares runAsNonRoot without a uid, which leaves the image to choose one"
    )


@pytest.mark.parametrize(
    "label,container", CONTAINERS, ids=lambda value: str(value)[:60]
)
def test_every_container_carries_every_required_container_security_field(
    label: str, container: dict
) -> None:
    for dotted, expected in REQUIRED_CONTAINER_SECURITY.items():
        actual = _dig(container, dotted)
        assert actual == expected, (
            f"{label} sets {dotted} to {actual!r}, expected {expected!r}"
        )
    dropped = _dig(container, "securityContext.capabilities.drop")
    assert dropped == ["ALL"], f"{label} drops {dropped!r} rather than every capability"
    added = _dig(container, "securityContext.capabilities.add")
    assert added is ABSENT, f"{label} adds capabilities back: {added!r}"


@pytest.mark.parametrize("label,document", MANIFESTS, ids=lambda value: str(value)[:60])
def test_no_manifest_exposes_a_service_outside_the_cluster(
    label: str, document: dict
) -> None:
    kind = document.get("kind")
    assert kind != "Ingress", (
        f"{label} declares an Ingress, and V1 installs no ingress controller"
    )
    if kind != "Service":
        return
    service_type = document.get("spec", {}).get("type")
    assert service_type == "ClusterIP", f"{label} is a {service_type} service"
    for port in document.get("spec", {}).get("ports") or []:
        assert "nodePort" not in port, f"{label} pins a node port"


def test_the_model_acquisition_job_pins_a_revision_and_verifies_a_hash() -> None:
    path = DEPLOY_DIR / "serving" / "feasibility" / "weights.yaml"
    body = path.read_text(encoding="utf-8")
    assert "sha256sum" in body, "the acquisition job computes no hash"
    assert "want_sha" in body and "got_sha" in body, (
        "the acquisition job does not compare a computed hash against a published one"
    )
    assert re.search(r"rev=[\"']?[0-9a-f]{40}", body), (
        "the acquisition job does not pin an immutable model revision"
    )


POD_SECURITY_CONTROLS = (
    "run-as-non-root",
    "forbid-privilege-escalation",
    "read-only-root-filesystem",
    "drop-all-capabilities",
    "seccomp-runtime-default",
    "do-not-mount-a-service-account-token",
)


@pytest.mark.parametrize("control_id", POD_SECURITY_CONTROLS)
def test_a_pod_security_control_is_a_manifest_property_and_says_so(
    control_id: str,
) -> None:
    row = next(r for r in CONTROLS if r["controlId"] == control_id)
    assert row["boundaryId"] == "B4"
    assert row["runtimeScope"] == "trial-apparatus"
    assert row["v1Status"] == "enforced-over-manifests"
    assert row["owner"] == "security"
    assert row["verification"]["ref"] == DECLARED_PATH + "/" + THIS_MODULE.name


def test_the_pod_security_gap_is_carried_by_a_deferred_risk() -> None:
    risk = next(row for row in RISKS if row["riskId"] == "DR-05")
    assert risk["boundaryId"] == "B4"
    assert "deploys no pod" in risk["whyDeferred"]
    assert risk["blocksProductionUse"] is True
    exception = next(row for row in EXCEPTIONS if row["exceptionId"] == "EX-04")
    assert exception["compensatingControl"] in POD_SECURITY_CONTROLS
    assert exception["deferredRiskRef"] == "DR-05"


# --------------------------------------------------------------------------
# The publication boundary
# --------------------------------------------------------------------------


def test_no_committed_file_is_generated_host_state() -> None:
    ignore_rules = GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
    for prefix in IGNORED_PREFIXES:
        assert prefix in ignore_rules, f"{prefix} is not ignored by version control"
    for path in REPOSITORY_FILES:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for prefix in IGNORED_PREFIXES:
            assert not rel.startswith(prefix), f"{rel} is generated host state"


def test_no_committed_file_carries_a_personal_filesystem_path() -> None:
    offenders: list[str] = []
    for path in REPOSITORY_FILES:
        if path == THIS_MODULE:
            # This module holds the pattern it searches for.
            continue
        if path.suffix.lower() in MODEL_ARTIFACT_SUFFIXES:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in PERSONAL_PATH.finditer(body):
            offenders.append(
                f"{path.relative_to(REPO_ROOT).as_posix()}: {match.group(0)}"
            )
    assert not offenders, offenders


def test_no_committed_file_is_a_model_artifact() -> None:
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in REPOSITORY_FILES
        if path.suffix.lower() in MODEL_ARTIFACT_SUFFIXES
    ]
    assert not offenders, offenders


def test_the_secret_scan_configuration_is_committed_and_its_allowlist_resolves() -> (
    None
):
    assert GITLEAKS_PATH.exists()
    body = GITLEAKS_PATH.read_text(encoding="utf-8")
    assert "[allowlist]" in body
    paths = re.findall(r'^\s*"([^"]+)",\s*$', body, flags=re.MULTILINE)
    assert paths, "the allowlist declares no paths"
    for entry in paths:
        assert (REPO_ROOT / entry).exists(), (
            f"the allowlist names {entry}, which does not exist"
        )
    exception = next(row for row in EXCEPTIONS if row["exceptionId"] == "EX-03")
    assert (
        str(len(paths)) in exception["statement"]
        or "two directories" in exception["statement"]
    )


def test_the_allowlist_exception_is_recorded_rather_than_left_implicit() -> None:
    documented = (REPO_ROOT / ".github" / "secret-scanning-allowlist.md").read_text(
        encoding="utf-8"
    )
    assert "Gitleaks Config" in documented or ".gitleaks.toml" in documented
    ids = {row["exceptionId"] for row in EXCEPTIONS}
    assert "EX-03" in ids


# --------------------------------------------------------------------------
# Agreement with the records that already exist
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "row",
    [b for b in BOUNDARIES if b["mappedInArchitecture"]],
    ids=lambda row: row["boundaryId"],
)
def test_a_mapped_boundary_matches_the_architecture_verbatim(row: dict) -> None:
    architecture = ARCHITECTURE_PATH.read_text(encoding="utf-8")
    assert row["whatCrosses"] in architecture, (
        f"{row['boundaryId']} describes what crosses it differently from the architecture"
    )
    assert row["enforcedToday"] in architecture, (
        f"{row['boundaryId']} describes what is enforced differently from the architecture"
    )


@pytest.mark.parametrize(
    "row",
    [b for b in BOUNDARIES if not b["mappedInArchitecture"]],
    ids=lambda row: row["boundaryId"],
)
def test_an_unmapped_boundary_says_why_it_extends_the_architecture(row: dict) -> None:
    assert row.get("extendsArchitecture", "").strip(), (
        f"{row['boundaryId']} is absent from the architecture and does not say why it is here"
    )


def test_every_boundary_the_architecture_maps_is_modelled_here() -> None:
    architecture = ARCHITECTURE_PATH.read_text(encoding="utf-8")
    mapped = set(re.findall(r"^\| (B\d) ", architecture, flags=re.MULTILINE))
    assert mapped, "the architecture's boundary table was not found"
    modelled = {row["boundaryId"] for row in BOUNDARIES if row["mappedInArchitecture"]}
    assert mapped <= modelled, (
        f"boundaries the architecture maps and this does not: {mapped - modelled}"
    )


def test_every_field_the_catalog_forbids_is_covered_by_a_control() -> None:
    empty = {
        row["classId"]
        for row in CATALOG["sensitivityClasses"]
        if not row["allowedPlacements"]
    }
    forbidden_classes = {row["sensitivity"] for row in CATALOG["forbiddenFields"]}
    assert forbidden_classes <= empty, (
        "the catalog forbids a field whose sensitivity class still permits a placement"
    )
    control = next(
        row
        for row in CONTROLS
        if row["controlId"] == "no-secret-or-content-has-a-telemetry-placement"
    )
    assert control["verification"]["ref"] == "tests/telemetry/test_telemetry_catalog.py"
    prose = " ".join(value for _, value in _prose_strings(BASELINE)).lower()
    for row in CATALOG["forbiddenFields"]:
        word = row["fieldId"].replace("-", " ")
        assert word in prose, (
            f"the catalog forbids {row['fieldId']} and this baseline never names it"
        )


def test_the_content_classes_the_catalog_declares_unemittable_stay_unemittable() -> (
    None
):
    empty = {
        row["classId"]
        for row in CATALOG["sensitivityClasses"]
        if not row["allowedPlacements"]
    }
    assert empty == {"user-content", "secret"}
    control = next(
        row
        for row in CONTROLS
        if row["controlId"] == "no-secret-or-content-has-a-telemetry-placement"
    )
    assert control["v1Status"] == "enforced-over-documents"


@pytest.mark.parametrize("row", CONTROLS, ids=lambda row: row["controlId"])
def test_every_control_owner_is_a_declared_evidence_owner(row: dict) -> None:
    owners = {owner["ownerId"] for owner in STRATEGY["evidenceOwners"]}
    assert row["owner"] in owners


@pytest.mark.parametrize("row", BOUNDARIES, ids=lambda row: row["boundaryId"])
def test_every_boundary_owner_is_a_declared_evidence_owner(row: dict) -> None:
    owners = {owner["ownerId"] for owner in STRATEGY["evidenceOwners"]}
    assert row["owner"] in owners


def test_this_suite_is_collected_by_the_layer_that_declares_it() -> None:
    layer = next(row for row in STRATEGY["layers"] if row["layerId"] == DECLARING_LAYER)
    assert DECLARED_PATH in layer["paths"], (
        f"{DECLARED_PATH} is not named by the {DECLARING_LAYER} layer, so the layer selects nothing here"
    )
    assert f"python -m pytest {DECLARED_PATH} -q" in layer["commands"]


def test_the_baseline_claim_is_certified_at_the_level_its_layer_can_reach() -> None:
    claim = next(row for row in STRATEGY["claims"] if row["claimId"] == BASELINE_CLAIM)
    assert claim["layers"] == [DECLARING_LAYER]
    assert claim["requiredCertification"] == "C0"
    assert claim["evidenceOwner"] == "security"
    assert claim["requiresRealModel"] is False
    assert claim["v1Status"] == "certified"
    assert (REPO_ROOT / claim["evidenceRef"]).exists()

    layer = next(row for row in STRATEGY["layers"] if row["layerId"] == DECLARING_LAYER)
    levels = [row["levelId"] for row in STRATEGY["certificationLevels"]]
    assert levels.index(layer["maxCertification"]) >= levels.index(
        claim["requiredCertification"]
    )
    assert layer["evidenceClass"] == "local-static"


def test_the_planned_security_claims_stay_planned() -> None:
    for claim_id in (
        "no-prompt-response-or-secret-reaches-a-log-or-a-metric",
        "no-credential-or-model-artifact-enters-public-history",
    ):
        claim = next(row for row in STRATEGY["claims"] if row["claimId"] == claim_id)
        assert claim["v1Status"] == "planned", (
            f"{claim_id} needs a component or a scanner run that does not exist; "
            "this baseline documents controls and certifies none of it"
        )
        assert claim["evidenceRef"] is None


# --------------------------------------------------------------------------
# Documents against data
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,pattern,expected",
    [
        (THREAT_MODEL_PATH, FIRST_TABLE_COLUMN_PLAIN, sorted(THREAT_IDS)),
        (CONTROL_MATRIX_PATH, FIRST_TABLE_COLUMN, sorted(CONTROL_IDS)),
        (DEFERRED_RISK_PATH, FIRST_TABLE_COLUMN_PLAIN, sorted(RISK_IDS)),
    ],
    ids=["threats", "controls", "deferred-risks"],
)
def test_every_identifier_in_the_data_is_published_by_its_document(
    path: Path, pattern: re.Pattern, expected: list[str]
) -> None:
    published = set(pattern.findall(path.read_text(encoding="utf-8")))
    missing = set(expected) - published
    assert not missing, f"{path.name} does not publish {sorted(missing)}"


# Every identifier vocabulary a document is allowed to publish in a first table
# column. A document publishing anything else has invented one.
PUBLISHABLE = {
    THREAT_MODEL_PATH: THREAT_IDS | BOUNDARY_IDS | ASSET_IDS | ACTOR_IDS,
    CONTROL_MATRIX_PATH: (
        CONTROL_IDS
        | {row["ruleId"] for row in PROHIBITIONS}
        | set(STATUS_BY_ID)
        | set(LEVEL_BY_KIND)
        | set(LEVEL_BY_KIND.values())
        | SCOPE_IDS
        | {row["term"] for row in RESERVED_TERMS}
    ),
    DEFERRED_RISK_PATH: RISK_IDS | {row["exceptionId"] for row in EXCEPTIONS},
}


@pytest.mark.parametrize(
    "path,pattern",
    [
        (THREAT_MODEL_PATH, FIRST_TABLE_COLUMN_PLAIN),
        (CONTROL_MATRIX_PATH, FIRST_TABLE_COLUMN),
        (DEFERRED_RISK_PATH, FIRST_TABLE_COLUMN_PLAIN),
    ],
    ids=["threats", "controls", "deferred-risks"],
)
def test_no_document_publishes_an_identifier_the_data_does_not_declare(
    path: Path, pattern: re.Pattern
) -> None:
    published = set(pattern.findall(path.read_text(encoding="utf-8")))
    invented = published - PUBLISHABLE[path]
    assert not invented, (
        f"{path.name} publishes {sorted(invented)}, which the data does not declare"
    )


def test_the_exceptions_are_published_where_a_reader_will_find_them() -> None:
    """A summary row is an index entry; the argument has to be published too.

    An exception whose row survives while its section is deleted reads as
    handled and is not, which is the failure this checks for rather than mere
    presence of the identifier somewhere in the file.
    """
    body = DEFERRED_RISK_PATH.read_text(encoding="utf-8")
    for row in EXCEPTIONS:
        assert f"| {row['exceptionId']} |" in body, (
            f"{row['exceptionId']} has no row in the exception table"
        )
        assert f"### {row['exceptionId']} " in body, (
            f"{row['exceptionId']} has a row but no section arguing it"
        )


def test_the_control_matrix_publishes_every_status_and_its_meaning() -> None:
    body = CONTROL_MATRIX_PATH.read_text(encoding="utf-8")
    for status_id in {row["v1Status"] for row in CONTROLS}:
        assert f"`{status_id}`" in body, f"the matrix does not explain {status_id}"


# Counts that appear in prose rather than in a table row. The cost method
# already establishes the rule these follow: a figure typed into a document
# that the data does not produce is a failing test. A table row is compared by
# identifier elsewhere; a sentence saying "twenty-two of thirty-two" is not
# compared by anything unless it is compared here.
NUMBER_WORDS = {
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    8: "eight",
    10: "ten",
    11: "eleven",
    12: "twelve",
    15: "fifteen",
    22: "twenty-two",
    32: "thirty-two",
}


def _word(value: int) -> str:
    assert value in NUMBER_WORDS, (
        f"no word for {value}; the data moved further than expected"
    )
    return NUMBER_WORDS[value]


def _counts() -> dict[str, int]:
    enforced = sum(
        1 for row in CONTROLS if STATUS_BY_ID[row["v1Status"]]["mayBeCalledImplemented"]
    )
    return {
        "controls": len(CONTROLS),
        "enforced": enforced,
        "unenforced": len(CONTROLS) - enforced,
        "threats": len(THREATS),
        "categories": len({row["category"] for row in THREATS}),
        "assets": len(ASSETS),
        "boundaries": len(BOUNDARIES),
        "risks": len(RISKS),
        "blocking": sum(1 for row in RISKS if row["blocksProductionUse"]),
        "exceptions": len(EXCEPTIONS),
        "rules": len(PROHIBITIONS),
        "tested_rules": sum(1 for row in PROHIBITIONS if row["enforcedBy"] == "test"),
        "review_rules": sum(1 for row in PROHIBITIONS if row["enforcedBy"] == "review"),
        "terms": len(RESERVED_TERMS),
    }


def _expected_sentences() -> list[tuple[Path, str]]:
    """Build every prose count from the data, then look for it in the document.

    Whitespace is normalised on both sides before comparing, so a sentence may
    wrap wherever it wants; the number is what has to match.
    """
    n = _counts()
    controls = _word(n["controls"])
    enforced = _word(n["enforced"])
    unenforced = _word(n["unenforced"])
    rules = _word(n["rules"])
    tested = _word(n["tested_rules"])
    review = _word(n["review_rules"])
    risks = _word(n["risks"])

    decision_controls = (
        f"**{controls.capitalize()} controls exist, and {enforced} of them are "
        "enforced by something.**"
    )
    decision_rules = (
        f"**{review.capitalize()} of {rules} rules are enforced by review alone**"
    )
    matrix_controls = (
        f"{enforced.capitalize()} of {controls} controls are enforced by something. "
        f"The other {unenforced} are the reason"
    )
    matrix_rules = (
        f"{rules.capitalize()} rules. {tested.capitalize()} are enforced by a test over "
        f"the committed baseline. {review.capitalize()} are enforced by review alone"
    )
    matrix_terms = (
        f"{_word(n['terms']).capitalize()} terms may appear in every Markdown document"
    )
    threats = (
        f"{_word(n['threats']).capitalize()}, in {_word(n['categories'])} categories."
    )
    assets = f"{_word(n['assets']).capitalize()} things worth protecting."
    blocking = (
        f"{_word(n['blocking']).capitalize()} of the {risks} block production use."
    )
    register = (
        f"{risks.capitalize()} risks V1 carries rather than reduces, and "
        f"{_word(n['exceptions'])} weaknesses"
    )
    index = (
        f"{enforced.capitalize()} of {controls} controls are enforced by something. "
        f"{unenforced.capitalize()} are not"
    )

    return [
        (DECISION_PATH, decision_controls),
        (DECISION_PATH, decision_rules),
        (CONTROL_MATRIX_PATH, matrix_controls),
        (CONTROL_MATRIX_PATH, matrix_rules),
        (CONTROL_MATRIX_PATH, matrix_terms),
        (THREAT_MODEL_PATH, threats),
        (THREAT_MODEL_PATH, assets),
        (DEFERRED_RISK_PATH, blocking),
        (DEFERRED_RISK_PATH, register),
        (SECURITY_DIR / "README.md", index),
    ]


@pytest.mark.parametrize(
    "path,sentence",
    _expected_sentences(),
    ids=lambda value: (
        value.name if isinstance(value, Path) else " ".join(str(value).split())[:60]
    ),
)
def test_every_count_a_document_states_is_recomputed_from_the_data(
    path: Path, sentence: str
) -> None:
    body = " ".join(path.read_text(encoding="utf-8").split())
    expected = " ".join(sentence.split())
    assert expected in body, (
        f"{path.name} does not contain the sentence the data produces:\n  {expected!r}\n"
        "A count typed into a document that the data does not produce is a failing test."
    )


def test_the_status_counts_the_index_publishes_match_the_data() -> None:
    body = (SECURITY_DIR / "README.md").read_text(encoding="utf-8")
    for status_id, status in STATUS_BY_ID.items():
        count = sum(1 for row in CONTROLS if row["v1Status"] == status_id)
        expected = f"| `{status_id}` | {count} |"
        assert expected in body, f"the index does not publish {expected!r}"
        published_flag = "yes" if status["mayBeCalledImplemented"] else "no"
        assert f"{expected} {published_flag} |" in body, (
            f"the index disagrees with the data on whether {status_id} may be called implemented"
        )


def test_the_decision_record_carries_the_sections_this_project_requires() -> None:
    body = DECISION_PATH.read_text(encoding="utf-8")
    for heading in (
        "## Decision status",
        "## Context",
        "## Decision criteria",
        "## Consequences",
        "## Compatibility impact",
        "## Security considerations",
        "## Evidence",
    ):
        assert heading in body, f"{DECISION_PATH.name} is missing {heading}"


# --------------------------------------------------------------------------
# Overclaiming
# --------------------------------------------------------------------------

# Every Markdown document committed here, not just the security ones.
#
# Scoping this to `docs/security/` would have been the comfortable choice and a
# defect: the documents most likely to describe a posture the project does not
# have are the ones a reader reaches first - the top-level README, SECURITY.md,
# the changelog, and an architecture record - and none of those lives under
# `docs/security/`.
SCANNED_DOCUMENTS = tuple(
    path for path in REPOSITORY_FILES if path.suffix.lower() == ".md"
)


def _reserved_pattern(term: str) -> re.Pattern:
    return re.compile(
        rf"(?<![A-Za-z0-9-]){re.escape(term)}(?![A-Za-z0-9])", flags=re.IGNORECASE
    )


def test_the_vocabulary_check_reaches_the_documents_a_reader_meets_first() -> None:
    """The scan's coverage is itself a claim, so it is checked rather than stated.

    A reserved-term check scoped to the security documents would pass while the
    top-level README described a posture this project does not have, which is
    the failure T-18 names happening inside the control for T-18.
    """
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in SCANNED_DOCUMENTS}
    for required in (
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "docs/architecture/system-architecture.md",
        "docs/security/threat-model.md",
        "docs/security/control-matrix.md",
        "docs/security/deferred-risks.md",
        "docs/security/README.md",
        "docs/architecture/decisions/ADR-0008-v1-security-baseline.md",
        "docs/proof/security/v1-s0-009-pr1-validation.md",
    ):
        assert required in scanned, f"the vocabulary check does not read {required}"
    assert len(scanned) >= 60, (
        "the walk found too few documents to be reading the repository"
    )


@pytest.mark.parametrize(
    "path", SCANNED_DOCUMENTS, ids=lambda path: path.relative_to(REPO_ROOT).as_posix()
)
def test_a_reserved_term_appears_only_where_it_is_denied(path: Path) -> None:
    prose = _strip_fences(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for sentence in _sentences(prose):
        for row in RESERVED_TERMS:
            if _reserved_pattern(row["term"]).search(sentence) and not DENIAL.search(
                sentence
            ):
                offenders.append(
                    f"{path.name}: {row['term']!r} in {sentence.strip()[:140]!r}"
                )
    assert not offenders, offenders


def test_a_reserved_term_appears_only_where_it_is_denied_in_the_data() -> None:
    offenders: list[str] = []
    for where, value in _prose_strings(BASELINE):
        for sentence in _sentences(value):
            for row in RESERVED_TERMS:
                if _reserved_pattern(row["term"]).search(
                    sentence
                ) and not DENIAL.search(sentence):
                    offenders.append(
                        f"{where}: {row['term']!r} in {sentence.strip()[:140]!r}"
                    )
    assert not offenders, offenders


@pytest.mark.parametrize("row", PROHIBITIONS, ids=lambda row: row["ruleId"])
def test_a_rule_claims_a_test_only_when_that_test_exists(row: dict) -> None:
    if row["enforcedBy"] == "review":
        assert row["testRef"] is None
        return
    assert row["testRef"], "a rule enforced by a test names one"
    body = THIS_MODULE.read_text(encoding="utf-8")
    assert TEST_DEF.format(symbol=row["testRef"]) in body, (
        f"{row['ruleId']} claims the test {row['testRef']}, which this module does not define"
    )


def test_at_least_one_rule_admits_it_is_enforced_by_review_alone() -> None:
    review_only = [
        row["ruleId"] for row in PROHIBITIONS if row["enforcedBy"] == "review"
    ]
    assert review_only, (
        "every rule claiming a test is the shape this suite exists to refuse; "
        "a rule a test cannot reach says so"
    )


def test_the_baseline_states_that_nothing_enforces_at_runtime() -> None:
    status = BASELINE["securityStatus"]
    assert status["securityAssessmentsPerformed"] == 0
    assert status["penetrationTestsPerformed"] == 0
    assert status["vulnerabilityReportsReceived"] == 0
    assert status["vulnerabilityReportsPossible"] is False
    assert "not published" in status["privateReportingChannel"]


def test_the_reporting_policy_still_publishes_no_private_channel() -> None:
    body = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "A dedicated private reporting channel is not yet published." in body
    assert BASELINE["securityStatus"]["vulnerabilityReportsPossible"] is False


def test_the_baseline_declares_a_limitation_for_every_gap_it_admits() -> None:
    statements = " ".join(row["statement"] for row in LIMITATIONS).lower()
    for phrase in (
        "no control here has ever acted inside a system serving a request",
        "no secret scanner",
        "no security assessment",
        "apparatus",
        "review alone",
        "markdown",
        "strong test from a weak one",
    ):
        assert phrase in statements, f"no limitation covers {phrase!r}"


def test_no_threat_carries_an_invented_likelihood_or_severity() -> None:
    banned = {"likelihood", "severity", "riskScore", "cvss", "priority"}
    for row in THREATS:
        assert not (banned & set(row)), f"{row['threatId']} carries an invented score"
    limitation_ids = {row["limitationId"] for row in LIMITATIONS}
    assert "no-likelihood-or-severity-score" in limitation_ids


def test_every_deferred_risk_states_what_is_not_claimed() -> None:
    for row in RISKS:
        assert row["notClaimed"].strip()
        assert row["whatWouldHaveToBeTrue"].strip()
        assert DENIAL.search(row["notClaimed"]), (
            f"{row['riskId']} states what is not claimed in a sentence that does not deny anything"
        )


def test_no_secret_shaped_string_appears_in_the_baseline() -> None:
    prefixes = re.compile(
        r"\b(?:AKIA|ASIA|ghp_|github_pat_|glpat-|hf_|xoxb-|sk-[A-Za-z0-9]{20}|AIza)",
    )
    offenders = [
        where for where, value in _prose_strings(BASELINE) if prefixes.search(value)
    ]
    assert not offenders, offenders
