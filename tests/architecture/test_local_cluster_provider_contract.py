"""Deterministic checks over the local Kubernetes cluster provider contract.

Every check here reads files from this repository and nothing else. No network,
no cluster, no container engine, no clock, no randomness. Nothing is executed:
the scripts are read as text.

ADR 0011 moved the cluster out of InferOps's ownership and wrote down how an
existing one is selected, identified, handed on, and refused. Most of that
contract is implemented by nothing yet -- on the Docker Desktop side, all of it --
and the contract says so row by row. What this suite checks is that it keeps
saying so accurately: a check, refusal, or rule claimed as enforced names a guard
or a test that exists, and one claimed as unenforced says who owes it; every
capability answer states how it is known and cites a record about the provider it
describes; Terraform and Helm are handed an address rather than a provider; the
contract, its document, and the ownership inventory publish the same identifiers;
and no platform workflow creates or deletes a cluster.

It also pins the gaps. The Terraform environment root still accepts only kind
contexts, nothing identifies a Docker Desktop cluster, and three Docker Desktop
capabilities are unknown. Tests below assert that each of those is still true, so
the change that closes one has to update the contract in the same commit rather
than leave it describing the past.

What it establishes about whether any cluster is correctly identified or refused:
nothing. That is a runtime question, and reading a guard is not running it against
the wrong cluster.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
THIS_MODULE = Path(__file__)
THIS_MODULE_REL = "tests/architecture/test_local_cluster_provider_contract.py"
ENVIRONMENT_DOCS = REPO_ROOT / "docs" / "environment"
CONTRACT_PATH = ENVIRONMENT_DOCS / "local-cluster-provider-contract.v1alpha1.json"
DOCUMENT_PATH = ENVIRONMENT_DOCS / "local-cluster-provider-contract.md"
DECISIONS_DIR = REPO_ROOT / "docs" / "architecture" / "decisions"
DECISION_PATH = DECISIONS_DIR / "ADR-0011-external-local-cluster-provider-contract.md"
SUPERSEDED_PATH = DECISIONS_DIR / "ADR-0001-local-development-environment.md"
ARCHITECTURE_INDEX_PATH = REPO_ROOT / "docs" / "architecture" / "README.md"
OWNERSHIP_PATH = (
    REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
)
SCRIPT_DIR = REPO_ROOT / "scripts" / "environment"
LIB_PATH = SCRIPT_DIR / "lib.sh"
TERRAFORM_MODULE_DIR = (
    REPO_ROOT / "infra" / "terraform" / "modules" / "platform-prerequisites"
)
TERRAFORM_ENVIRONMENT_VARIABLES = (
    REPO_ROOT / "infra" / "terraform" / "environments" / "local" / "variables.tf"
)

EXPECTED_CONTRACT_ID = (
    "https://inferops.io/environment/local-cluster-provider-contract.v1alpha1.json"
)
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

SUPPORTED_PROVIDERS = ("kind", "docker-desktop")
EXTERNAL_LIFECYCLE = ("create", "enable", "reset", "reconfigure", "delete")

# The nine cases ADR 0011 D6 names. A refusal added to the data without the
# decision naming it, or dropped from the data while the decision still does,
# fails here.
EXPECTED_REFUSALS = frozenset(
    {
        "no-provider-selected",
        "unsupported-provider",
        "ambiguous-target",
        "target-missing",
        "target-unreachable",
        "unexpected-context",
        "provider-mismatch",
        "capability-unknown-or-insufficient",
        "client-outside-skew",
    }
)

# The only facts Terraform and Helm may receive. Handing either of them the
# provider is how provider-specific lifecycle logic starts to accrete in a module.
TARGET_ADDRESS = frozenset({"kubeconfigPath", "kubeContext"})

# The scripts a platform workflow runs, and the kind helper an operator may run
# instead of the kind CLI. Every committed script is one or the other, and a test
# refuses a new script that is neither -- an unclassified script is one the
# lifecycle rule below never reads.
PLATFORM_WORKFLOWS = (
    "terraform-prerequisites.sh",
    "helm-lifecycle.sh",
    "kubernetes-certification.sh",
    "kubernetes-multi-replica-certification.sh",
    "helm-upgrade-rollback.sh",
    "api-image.sh",
    "model-seed-image.sh",
    "target-detect.sh",
)

# The seven platform workflows that mutate a target, as distinct from
# target-detect.sh, which only ever reports. Every one of these must call the
# provider-aware guard before its first mutation, and every certification or
# experiment script relies on the front-door check even though its own descriptor
# and evidence tooling remain kind-pinned (V1-S3-011 ports them).
MUTATING_PLATFORM_WORKFLOWS = (
    "terraform-prerequisites.sh",
    "helm-lifecycle.sh",
    "kubernetes-certification.sh",
    "kubernetes-multi-replica-certification.sh",
    "helm-upgrade-rollback.sh",
    "api-image.sh",
    "model-seed-image.sh",
)
KIND_HELPER = (
    "preflight.sh",
    "cluster-up.sh",
    "cluster-verify.sh",
    "smoke.sh",
    "cluster-down.sh",
    "verify-clean.sh",
    "proof.sh",
)

# A command that changes a cluster's lifecycle, or that runs a helper script which
# does. Matched against lines that are not comments, so a refusal message naming
# `cluster-up.sh` as the recovery is not mistaken for running it.
CLUSTER_LIFECYCLE_COMMAND = re.compile(
    r"\bkind\s+(?:create|delete)\s+cluster\b"
    r"|\bdocker\s+desktop\b"
    r"|^\s*(?:(?:bash|sh|exec|source|\.)\s+)?\"?[^\s\"]*"
    r"(?:cluster-up|cluster-down|proof|smoke)\.sh\b"
)

EVIDENCE_CLASSES = frozenset(
    {"observed", "inferred", "implemented-not-executed", "documented", "unknown"}
)
IDENTITY_STATUSES = frozenset({"implemented", "specified", "undecided"})
ENFORCEMENT_KINDS = frozenset({"test", "script", "review", "unimplemented"})
FACT_SOURCES = frozenset({"selection", "verification"})

# What a record about each provider says, so that an observation cannot cite a
# record made on the other one.
PROVIDER_MARKERS = {
    "kind": ("inferops-dev",),
    "docker-desktop": ("Docker Desktop", "container desktop"),
}

REQUIRED_CHECK_FIELDS = (
    "checkId",
    "statement",
    "status",
    "enforcedBy",
    "gap",
    "owedBy",
)
REQUIRED_CAPABILITY_FIELDS = ("value", "evidence", "source", "owedBy")
REQUIRED_FACT_FIELDS = (
    "factId",
    "statement",
    "source",
    "consumers",
    "recordedInEvidence",
)
REQUIRED_REFUSAL_FIELDS = (
    "refusalId",
    "when",
    "implementedFor",
    "enforcedBy",
    "owedBy",
)
REQUIRED_RULE_FIELDS = (
    "ruleId",
    "statement",
    "rationale",
    "enforcement",
    "enforcedBy",
    "owedBy",
)
REQUIRED_LEDGER_FIELDS = ("recordPath", "provider", "clusterMarker", "establishes")

SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
FIELD_NAME = re.compile(r"^[a-z][A-Za-z0-9]*$")
LIB_FUNCTION = re.compile(r"^(inferops::[a-z_]+)\(\) \{$", flags=re.MULTILINE)

# An identifier as the document publishes it: an inline code span in the first
# column of a Markdown table row.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([A-Za-z0-9][A-Za-z0-9-]*)`\s*\|", flags=re.MULTILINE
)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CREDENTIAL_WORDS = re.compile(
    r"token|cert|secret|password|credential|address|url", flags=re.IGNORECASE
)

NUMBER_WORDS = {
    0: "no",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


CONTRACT = load_json(CONTRACT_PATH)
PROVIDERS = CONTRACT["providers"]
PROVIDER_BY_ID = {provider["providerId"]: provider for provider in PROVIDERS}
FACTS = CONTRACT["targetFacts"]
REFUSALS = CONTRACT["refusals"]
RULES = CONTRACT["rules"]
LEDGER = CONTRACT["evidenceLedger"]
CHECKS = [
    (provider["providerId"], check)
    for provider in PROVIDERS
    for check in provider["identityChecks"]
]
CAPABILITIES = [
    (provider["providerId"], question, provider["capabilities"][question])
    for provider in PROVIDERS
    for question in CONTRACT["capabilityQuestions"]
    if question in provider["capabilities"]
]


def check_id(case: tuple[str, dict]) -> str:
    return f"{case[0]}:{case[1]['checkId']}"


def capability_id(case: tuple[str, str, dict]) -> str:
    return f"{case[0]}:{case[1]}"


def lib_functions() -> set[str]:
    return set(LIB_FUNCTION.findall(LIB_PATH.read_text(encoding="utf-8")))


def code_lines(script: str) -> list[str]:
    """The lines of a script that are not comments."""
    text = (SCRIPT_DIR / script).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def lifecycle_commands(script: str) -> list[str]:
    return [
        line for line in code_lines(script) if CLUSTER_LIFECYCLE_COMMAND.search(line)
    ]


def outside_fences(text: str) -> str:
    """The text of a Markdown document with every fenced block removed."""
    kept, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def declared_identifiers() -> set[str]:
    """Every identifier the contract declares that its document should publish."""
    identifiers = set(SUPPORTED_PROVIDERS)
    identifiers |= {check["checkId"] for _, check in CHECKS}
    identifiers |= {refusal["refusalId"] for refusal in REFUSALS}
    identifiers |= {rule["ruleId"] for rule in RULES}
    identifiers |= {fact["factId"] for fact in FACTS}
    identifiers |= set(CONTRACT["capabilityQuestions"])
    return identifiers


@pytest.fixture(scope="module")
def document() -> str:
    return DOCUMENT_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_the_contract_declares_its_identity_and_version() -> None:
    assert CONTRACT["$id"] == EXPECTED_CONTRACT_ID
    assert CONTRACT["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_the_contract_references_documents_that_exist() -> None:
    for key in ("decisionRef", "documentRef"):
        assert (REPO_ROOT / CONTRACT[key]).is_file(), CONTRACT[key]


def test_the_supported_providers_are_exactly_kind_and_docker_desktop() -> None:
    """A third provider is a decision record, not a new row (ADR 0011 D2)."""
    ids = [provider["providerId"] for provider in PROVIDERS]
    assert tuple(ids) == SUPPORTED_PROVIDERS, ids


def test_the_reference_provider_is_a_supported_one() -> None:
    assert CONTRACT["referenceProviderId"] in SUPPORTED_PROVIDERS


def test_every_lifecycle_operation_belongs_to_the_operator() -> None:
    assert tuple(CONTRACT["externalLifecycleOperations"]) == EXTERNAL_LIFECYCLE


def test_identifiers_are_well_formed_and_unique() -> None:
    for identifiers, pattern in (
        ([check["checkId"] for _, check in CHECKS], SLUG),
        ([refusal["refusalId"] for refusal in REFUSALS], SLUG),
        ([rule["ruleId"] for rule in RULES], SLUG),
        ([fact["factId"] for fact in FACTS], FIELD_NAME),
        (list(CONTRACT["capabilityQuestions"]), FIELD_NAME),
    ):
        assert len(identifiers) == len(set(identifiers)), identifiers
        for identifier in identifiers:
            assert pattern.match(identifier), identifier


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------


def test_no_selection_input_has_a_default() -> None:
    """A default is a selection somebody else made (ADR 0011 D3)."""
    for provider in PROVIDERS:
        for selection_input in provider["selectionInputs"]:
            assert selection_input["default"] is None, (
                provider["providerId"],
                selection_input["name"],
            )


def test_kind_needs_a_cluster_name_and_docker_desktop_takes_none() -> None:
    names = {
        provider["providerId"]: [item["name"] for item in provider["selectionInputs"]]
        for provider in PROVIDERS
    }
    assert names == {
        "kind": ["provider", "clusterName"],
        "docker-desktop": ["provider"],
    }


# --------------------------------------------------------------------------
# What verification hands on
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fact", FACTS, ids=lambda fact: fact["factId"])
def test_every_target_fact_declares_every_required_field(fact: dict) -> None:
    assert set(fact) == set(REQUIRED_FACT_FIELDS), fact["factId"]
    assert fact["statement"].strip(), fact["factId"]
    assert fact["source"] in FACT_SOURCES, fact["factId"]
    assert fact["consumers"], fact["factId"]
    assert set(fact["consumers"]) <= set(CONTRACT["consumers"]), fact["factId"]


def test_terraform_and_helm_are_handed_an_address_and_nothing_else() -> None:
    """ADR 0011 D4. Neither layer may learn which provider it is on."""
    for consumer in ("terraform", "helm"):
        handed = {fact["factId"] for fact in FACTS if consumer in fact["consumers"]}
        assert handed == TARGET_ADDRESS, (consumer, sorted(handed))


@pytest.mark.parametrize("fact", FACTS, ids=lambda fact: fact["factId"])
def test_a_fact_is_in_evidence_exactly_when_evidence_consumes_it(fact: dict) -> None:
    assert fact["recordedInEvidence"] == ("evidence" in fact["consumers"]), fact[
        "factId"
    ]


def test_the_kubeconfig_path_never_reaches_a_record() -> None:
    by_id = {fact["factId"]: fact for fact in FACTS}
    assert by_id["kubeconfigPath"]["recordedInEvidence"] is False
    never = " ".join(CONTRACT["neverRecorded"]).lower()
    for phrase in ("certificate", "token", "kubeconfig", "address"):
        assert phrase in never, phrase


def test_no_fact_is_credential_material() -> None:
    for fact in FACTS:
        assert not CREDENTIAL_WORDS.search(fact["factId"]), fact["factId"]


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case", CHECKS, ids=check_id)
def test_every_identity_check_declares_every_required_field(
    case: tuple[str, dict],
) -> None:
    _, check = case
    assert set(check) == set(REQUIRED_CHECK_FIELDS), check["checkId"]
    assert check["statement"].strip(), check["checkId"]
    assert check["status"] in IDENTITY_STATUSES, check["checkId"]


@pytest.mark.parametrize("case", CHECKS, ids=check_id)
def test_an_implemented_check_names_a_guard_lib_sh_defines(
    case: tuple[str, dict],
) -> None:
    _, check = case
    if check["status"] == "implemented":
        assert check["enforcedBy"] in lib_functions(), (
            f"check '{check['checkId']}' claims '{check['enforcedBy']}', "
            "which lib.sh does not define"
        )
    else:
        assert check["enforcedBy"] is None, check["checkId"]


@pytest.mark.parametrize("case", CHECKS, ids=check_id)
def test_an_unfinished_check_says_who_owes_it(case: tuple[str, dict]) -> None:
    _, check = case
    if check["status"] != "implemented" or check["gap"]:
        assert check["gap"], check["checkId"]
        assert check["owedBy"], check["checkId"]


def test_no_provider_is_identified_by_a_context_name_alone() -> None:
    """Each provider has at least one check that is about something else."""
    for provider in PROVIDERS:
        other = [
            check["checkId"]
            for check in provider["identityChecks"]
            if "context" not in check["checkId"]
        ]
        assert other, provider["providerId"]


def test_docker_desktop_has_two_implemented_checks_and_one_undecided() -> None:
    """V1-S3-010-PR2 closed two of the three Docker Desktop identity checks.

    The third, binding the reachable nodes to this machine's engine, stays
    undecided on purpose: whether that is even observable has not been
    established, and the other two are implemented without pretending to answer
    it. A guard that is a name-and-shape check is weaker than kind's, and this
    pins that it is described as such rather than as complete.
    """
    statuses = {
        check["checkId"]: check["status"]
        for check in PROVIDER_BY_ID["docker-desktop"]["identityChecks"]
    }
    assert statuses["the-docker-desktop-context-exists"] == "implemented"
    assert statuses["every-node-has-an-observed-docker-desktop-shape"] == "implemented"
    assert statuses["the-nodes-are-bound-to-the-local-engine"] == "undecided"
    assert "docker-desktop" in LIB_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------


@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda refusal: refusal["refusalId"])
def test_every_refusal_declares_every_required_field(refusal: dict) -> None:
    assert set(refusal) == set(REQUIRED_REFUSAL_FIELDS), refusal["refusalId"]
    assert refusal["when"].strip(), refusal["refusalId"]


def test_the_refusals_are_the_nine_the_decision_names() -> None:
    assert {refusal["refusalId"] for refusal in REFUSALS} == EXPECTED_REFUSALS


@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda refusal: refusal["refusalId"])
def test_a_refusal_claims_a_provider_only_with_a_guard_behind_it(refusal: dict) -> None:
    implemented = refusal["implementedFor"]
    assert set(implemented) <= set(SUPPORTED_PROVIDERS), refusal["refusalId"]
    if implemented:
        assert refusal["enforcedBy"] in lib_functions(), refusal["refusalId"]
    else:
        assert refusal["enforcedBy"] is None, refusal["refusalId"]
    if set(implemented) != set(SUPPORTED_PROVIDERS):
        assert refusal["owedBy"], refusal["refusalId"]


def test_every_refusal_but_one_is_implemented_for_both_providers() -> None:
    """V1-S3-010-PR2: eight of the nine refusals now guard both providers.

    `unexpected-context` is the exception, and its own row says why: the
    provider-aware target verification rewrites the project-scoped kubeconfig
    from the operator's kubeconfig on every call, so there is no separately
    long-lived file whose context could have drifted for either provider.
    """
    for refusal in REFUSALS:
        if refusal["refusalId"] == "unexpected-context":
            assert refusal["implementedFor"] == [], refusal["refusalId"]
            continue
        assert set(refusal["implementedFor"]) == set(SUPPORTED_PROVIDERS), refusal[
            "refusalId"
        ]


# --------------------------------------------------------------------------
# Where the providers differ
# --------------------------------------------------------------------------


def test_both_providers_answer_every_capability_question() -> None:
    for provider in PROVIDERS:
        assert list(provider["capabilities"]) == CONTRACT["capabilityQuestions"], (
            provider["providerId"]
        )


@pytest.mark.parametrize("case", CAPABILITIES, ids=capability_id)
def test_every_capability_states_how_it_is_known(case: tuple[str, str, dict]) -> None:
    """ADR 0011 D8. An unknown is written as unknown, never borrowed."""
    provider_id, question, answer = case
    where = f"{provider_id}:{question}"
    assert set(answer) == set(REQUIRED_CAPABILITY_FIELDS), where
    assert answer["value"].strip(), where
    assert answer["evidence"] in EVIDENCE_CLASSES, where
    if answer["evidence"] == "unknown":
        assert answer["source"] is None, where
        assert answer["owedBy"], where
        return
    assert answer["owedBy"] is None, where
    assert answer["source"], where
    assert (REPO_ROOT / answer["source"]).is_file(), (where, answer["source"])
    if answer["evidence"] in ("observed", "inferred"):
        assert answer["source"].startswith("docs/proof/"), where
    if answer["evidence"] == "implemented-not-executed":
        assert not answer["source"].startswith("docs/"), where


@pytest.mark.parametrize(
    "case",
    [case for case in CAPABILITIES if case[2]["evidence"] in ("observed", "inferred")],
    ids=capability_id,
)
def test_an_observation_cites_a_record_about_the_provider_it_was_made_on(
    case: tuple[str, str, dict],
) -> None:
    """A kind answer may not cite a Docker Desktop record as though it were kind's.

    An inference is the one permitted crossing, and it has to say so: the answer
    names the provider the measurement was actually made on.
    """
    provider_id, question, answer = case
    record = (REPO_ROOT / answer["source"]).read_text(encoding="utf-8")
    if answer["evidence"] == "observed":
        assert any(marker in record for marker in PROVIDER_MARKERS[provider_id]), (
            provider_id,
            question,
        )
    else:
        other = next(p for p in SUPPORTED_PROVIDERS if p != provider_id)
        assert any(marker in record for marker in PROVIDER_MARKERS[other]), question
        assert any(marker in answer["value"] for marker in PROVIDER_MARKERS[other]), (
            f"'{provider_id}:{question}' is inferred from another provider "
            "without saying which"
        )


def test_the_docker_desktop_unknowns_are_still_unknown() -> None:
    """A pinned gap. Establishing one of these has to update the contract."""
    capabilities = PROVIDER_BY_ID["docker-desktop"]["capabilities"]
    unknown = sorted(
        question
        for question, answer in capabilities.items()
        if answer["evidence"] == "unknown"
    )
    assert unknown == ["capacity", "imagePreparation", "wholeClusterCleanup"], unknown


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule["ruleId"])
def test_every_rule_declares_every_required_field(rule: dict) -> None:
    assert set(rule) == set(REQUIRED_RULE_FIELDS), rule["ruleId"]
    assert rule["statement"].strip(), rule["ruleId"]
    assert rule["rationale"].strip(), rule["ruleId"]
    assert rule["enforcement"] in ENFORCEMENT_KINDS, rule["ruleId"]


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule["ruleId"])
def test_a_rule_claims_an_enforcer_only_when_the_enforcer_exists(rule: dict) -> None:
    enforcement, enforcer = rule["enforcement"], rule["enforcedBy"]
    if enforcement == "test":
        path, _, function = enforcer.partition("::")
        module = REPO_ROOT / path
        assert module.is_file(), (rule["ruleId"], path)
        assert f"def {function}(" in module.read_text(encoding="utf-8"), (
            f"rule '{rule['ruleId']}' names '{enforcer}', which does not exist"
        )
    elif enforcement == "script":
        assert enforcer in lib_functions(), (rule["ruleId"], enforcer)
    else:
        assert enforcer is None, rule["ruleId"]
    if enforcement == "unimplemented":
        assert rule["owedBy"], rule["ruleId"]


def test_some_rules_admit_that_nothing_enforces_them() -> None:
    """A contract whose every rule claims an enforcer has mislabelled one."""
    kinds = {rule["enforcement"] for rule in RULES}
    assert {"review", "unimplemented"} <= kinds, sorted(kinds)


def test_the_document_counts_the_rules_correctly(document: str) -> None:
    """A published count is a claim, and counts in this repository drift."""

    def count(enforcement: str, here: bool | None = None) -> int:
        return sum(
            1
            for rule in RULES
            if rule["enforcement"] == enforcement
            and (
                here is None
                or rule["enforcedBy"].startswith(f"{THIS_MODULE_REL}::") == here
            )
        )

    expected = (
        f"{NUMBER_WORDS[len(RULES)].capitalize()} rules: "
        f"{NUMBER_WORDS[count('test', here=True)]} enforced by a test, "
        f"{NUMBER_WORDS[count('script')]} by a shell guard, "
        f"{NUMBER_WORDS[count('unimplemented')]} by nothing, "
        f"{NUMBER_WORDS[count('test', here=False)]} by another suite's test, and "
        f"{NUMBER_WORDS[count('review')]} by review alone."
    )
    assert expected in " ".join(document.split()), expected


def test_every_script_rule_now_covers_both_providers() -> None:
    """V1-S3-010-PR2: every shell guard now dispatches on the selected provider.

    Before this PR every shell guard was the kind one, pinned to one cluster
    name, and none of them was complete for Docker Desktop. That gap is why the
    predecessor of this test asserted the opposite of what it asserts now, and
    it is pinned here the same way: the change that regresses a `script` rule
    back to a single provider has to update this test to say so again.
    """
    for rule in RULES:
        if rule["enforcement"] == "script":
            assert not rule["owedBy"], rule["ruleId"]


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------


@pytest.mark.parametrize("entry", LEDGER, ids=lambda entry: entry["recordPath"])
def test_every_ledger_record_exists_and_names_its_cluster(entry: dict) -> None:
    assert set(entry) == set(REQUIRED_LEDGER_FIELDS), entry["recordPath"]
    assert entry["provider"] in SUPPORTED_PROVIDERS, entry["recordPath"]
    assert entry["clusterMarker"] in PROVIDER_MARKERS[entry["provider"]], entry[
        "recordPath"
    ]
    record = REPO_ROOT / entry["recordPath"]
    assert record.is_file(), entry["recordPath"]
    assert entry["clusterMarker"] in record.read_text(encoding="utf-8"), entry[
        "recordPath"
    ]


def test_each_provider_has_its_own_evidence_and_no_record_is_claimed_twice() -> None:
    paths = [entry["recordPath"] for entry in LEDGER]
    assert len(paths) == len(set(paths)), paths
    assert {entry["provider"] for entry in LEDGER} == set(SUPPORTED_PROVIDERS)


def test_the_document_publishes_the_ledger(document: str) -> None:
    for entry in LEDGER:
        assert Path(entry["recordPath"]).name in document, entry["recordPath"]


# --------------------------------------------------------------------------
# The repository the contract describes
# --------------------------------------------------------------------------


def test_every_environment_script_is_classified() -> None:
    """A script neither list names is one the lifecycle rule below never reads."""
    committed = {path.name for path in SCRIPT_DIR.glob("*.sh") if path.name != "lib.sh"}
    classified = set(PLATFORM_WORKFLOWS) | set(KIND_HELPER)
    assert not set(PLATFORM_WORKFLOWS) & set(KIND_HELPER)
    assert committed == classified, sorted(committed ^ classified)


@pytest.mark.parametrize("script", PLATFORM_WORKFLOWS)
def test_no_platform_workflow_creates_or_deletes_a_cluster(script: str) -> None:
    """ADR 0011 D1 and D11, read from the scripts rather than trusted.

    Two of these load images with `kind load`, which prepares an image and changes
    no cluster's lifecycle; that is image preparation, recorded as the kind
    provider's own path, and it is not matched here.
    """
    assert not lifecycle_commands(script), (script, lifecycle_commands(script))


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("cluster-up.sh", "kind create cluster"),
        ("cluster-down.sh", "kind delete cluster"),
        ("proof.sh", "cluster-up.sh"),
    ],
)
def test_the_lifecycle_pattern_catches_the_helper_that_does_it(
    script: str, expected: str
) -> None:
    """The control case. Without it every negative result above could be vacuous."""
    found = lifecycle_commands(script)
    assert any(expected in line for line in found), (script, found)


@pytest.mark.parametrize(
    "line",
    [
        "docker desktop restart",
        "  docker desktop stop",
        'bash "${here}/cluster-down.sh" --workload',
        "  scripts/environment/smoke.sh",
    ],
)
def test_the_lifecycle_pattern_catches_forms_no_committed_script_uses(
    line: str,
) -> None:
    """The control case for the alternatives the scripts above never exercise.

    No committed script calls Docker Desktop's CLI, so without a literal here the
    `docker desktop` alternative could match nothing, ever, and nobody would know.
    """
    assert CLUSTER_LIFECYCLE_COMMAND.search(line), line


@pytest.mark.parametrize(
    "line",
    [
        '  inferops::fail "no project kubeconfig. Bring the cluster up first: '
        'scripts/environment/cluster-up.sh"',
        '    kind load docker-image "${INFEROPS_API_IMAGE_REF}" \\',
    ],
)
def test_the_lifecycle_pattern_ignores_what_changes_no_lifecycle(line: str) -> None:
    """The other direction: a refusal naming the helper, and an image load.

    Both appear in platform workflows today. If either matched, the rule could only
    be satisfied by deleting a useful recovery message or the kind image path.
    """
    assert not CLUSTER_LIFECYCLE_COMMAND.search(line), line


def test_the_detection_script_never_selects_or_mutates() -> None:
    """`detection-never-selects` (ADR 0011): a report, never a decision.

    target-detect.sh may read the operator's own kubeconfig and ask kind and
    docker what they see, but it may not resolve a target, write the
    project-scoped kubeconfig, or run anything that mutates a cluster.
    """
    lines = code_lines("target-detect.sh")
    forbidden = (
        "inferops::resolve_target",
        "inferops::target_kubectl",
        "inferops::target_helm",
        "inferops::kubectl",
        "inferops::helm",
        "terraform",
        "kind create",
        "kind delete",
        "kind load",
    )
    for line in lines:
        for phrase in forbidden:
            assert phrase not in line, (phrase, line)


MUTATING_TARGET_CALL = re.compile(
    r"inferops::target_kubectl|inferops::target_helm|kind load docker-image"
    r"|\bterraform\b.*\b(apply|destroy)\b"
)

# A line that only prints -- usage text, a diagnostic, a recovery instruction --
# runs no tool. `terraform-prerequisites.sh`'s own usage string names
# `apply|destroy` as argument choices, which is exactly the kind of line
# MUTATING_TARGET_CALL must not mistake for one that runs either.
PRINTS_ONLY = re.compile(r"^inferops::(log|warn|fail)\s")


def prints_rather_than_runs(line: str) -> bool:
    return PRINTS_ONLY.match(line.strip()) is not None and "$(" not in line


@pytest.mark.parametrize("script", MUTATING_PLATFORM_WORKFLOWS)
def test_every_mutating_workflow_resolves_a_target_first(script: str) -> None:
    """`selection-is-explicit` and `verification-precedes-every-mutation`.

    Every platform workflow that can act on a cluster calls
    inferops::resolve_target -- which fails closed on no-provider-selected,
    unsupported-provider, ambiguous-target, target-missing,
    target-unreachable, and provider-mismatch -- and nothing in the script
    reaches the target-scoped kubectl/helm wrappers, a kind image load, or a
    Terraform apply/destroy before that call has returned successfully.
    """
    lines = code_lines(script)
    resolved_at = next(
        (i for i, line in enumerate(lines) if "inferops::resolve_target" in line),
        None,
    )
    assert resolved_at is not None, f"{script} never calls inferops::resolve_target"

    first_mutating = next(
        (
            i
            for i, line in enumerate(lines)
            if MUTATING_TARGET_CALL.search(line) and not prints_rather_than_runs(line)
        ),
        None,
    )
    if first_mutating is not None:
        assert resolved_at < first_mutating, (
            script,
            "resolved at line-index",
            resolved_at,
            "but acted at",
            first_mutating,
        )


def test_the_terraform_module_names_no_provider() -> None:
    """ADR 0011 D4: the module is given an address and never learns the provider."""
    sources = sorted(TERRAFORM_MODULE_DIR.glob("*.tf"))
    assert sources, "the prerequisite module has no configuration to check"
    provider_word = re.compile(r"\bkind\b|docker.?desktop", flags=re.IGNORECASE)
    for source in sources:
        text = source.read_text(encoding="utf-8")
        assert not provider_word.search(text), source.name


def test_the_terraform_environment_root_accepts_either_providers_context() -> None:
    """V1-S3-010-PR2 closed this gap: the environment root no longer pins kind.

    The validation is still a name check and nothing more -- it cannot establish
    that the cluster on the other end is really the selected provider's, which is
    scripts/environment/lib.sh's job -- but it no longer refuses a
    correctly-verified docker-desktop target by name alone.
    """
    text = TERRAFORM_ENVIRONMENT_VARIABLES.read_text(encoding="utf-8")
    assert "^kind-inferops-" not in text
    assert "docker-desktop" in text
    rule = next(
        rule
        for rule in RULES
        if rule["ruleId"] == "terraform-and-helm-receive-an-address-never-a-provider"
    )
    assert not rule["owedBy"], "the gap is closed; nobody should still owe it"


def test_the_inventory_gives_every_cluster_to_its_operator() -> None:
    """ADR 0011 D1: one cluster row per provider, both owned by the operator."""
    inventory = load_json(OWNERSHIP_PATH)
    owners = {owner["ownerId"]: owner for owner in inventory["owners"]}
    clusters = {
        resource["resourceId"]: resource
        for resource in inventory["resources"]
        if resource["resourceId"].endswith("-cluster")
    }
    assert set(clusters) == {f"{provider}-cluster" for provider in SUPPORTED_PROVIDERS}
    for resource in clusters.values():
        assert resource["owner"] == "cluster-operator", resource["resourceId"]
        assert "cluster teardown" not in resource["survives"], resource["resourceId"]
    assert owners["cluster-operator"]["lifecycle"] == "operator-provided"
    tool_owned = {
        resource["resourceId"]
        for resource in inventory["resources"]
        if resource["owner"] in ("terraform", "helm", "contributor-host")
    }
    assert not tool_owned & set(clusters)


def test_the_docker_desktop_cluster_is_planned_rather_than_implemented() -> None:
    """A pinned gap: the inventory must not average the two providers' evidence."""
    inventory = load_json(OWNERSHIP_PATH)
    status = {
        resource["resourceId"]: (resource["v1Status"], resource["evidenceRef"])
        for resource in inventory["resources"]
    }
    assert status["kind-cluster"][0] == "implemented"
    assert status["docker-desktop-cluster"] == ("planned", None)


# --------------------------------------------------------------------------
# The contract and its documents cannot drift apart
# --------------------------------------------------------------------------


@pytest.mark.parametrize("identifier", sorted(declared_identifiers()))
def test_the_document_publishes_every_identifier_the_contract_declares(
    identifier: str, document: str
) -> None:
    assert f"`{identifier}`" in document, identifier


def test_the_document_publishes_no_identifier_the_contract_lacks(document: str) -> None:
    published = set(FIRST_TABLE_COLUMN.findall(document))
    assert published, "no identifier column found; the document layout changed"
    assert published <= declared_identifiers(), sorted(
        published - declared_identifiers()
    )


@pytest.mark.parametrize(
    "path", [DOCUMENT_PATH, DECISION_PATH], ids=lambda path: path.name
)
def test_every_relative_link_resolves(path: Path) -> None:
    for target in MARKDOWN_LINK.findall(outside_fences(path.read_text("utf-8"))):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        assert resolved.exists(), (path.name, target)


def test_the_decision_record_carries_the_sections_this_project_requires() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    for heading in (
        "## Decision status",
        "## Context",
        "## Decision criteria",
        "## Consequences",
        "## Compatibility impact",
        "## Security considerations",
        "## Evidence",
    ):
        assert f"\n{heading}\n" in decision, heading


def test_the_superseded_record_and_the_index_point_at_this_one() -> None:
    """Two accepted records may not disagree about which of them governs."""
    decision = DECISION_PATH.read_text(encoding="utf-8")
    head = decision[: decision.index("## Decision status")]
    assert (
        "| Supersedes | ADR 0001 D2, D5, and D6, in part; amends ADR 0004 D3 |" in head
    )
    superseded = SUPERSEDED_PATH.read_text(encoding="utf-8")
    superseded_head = superseded[: superseded.index("## Decision status")]
    assert "ADR-0011-external-local-cluster-provider-contract.md" in superseded_head
    assert DECISION_PATH.name in ARCHITECTURE_INDEX_PATH.read_text(encoding="utf-8")
