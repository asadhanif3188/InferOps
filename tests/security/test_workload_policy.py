"""The V1 workload security policy, and the fixtures that establish it refuses.

Three questions, in the order they have to be asked:

1. **Does the policy accept what this project actually renders?** The two
   committed chart renders are checked as bundles and must produce no finding. A
   policy nothing passes is a policy somebody turns off.
2. **Does it refuse what it says it refuses?** Nine deliberately broken fixtures,
   each dropping one control, compared against a committed record of which rules
   each must cite -- in both directions, so a fixture failing for a *different*
   reason is a failure rather than a pass. This is the half that separates "the
   validator produced a finding" from "the validator produced this finding", and
   without it a validator whose rules all read the wrong field passes forever.
3. **Does it stay tied to the baseline?** Every rule identifier the module can
   cite is a control identifier in the committed security baseline, and every
   control the baseline says this module verifies is a rule it can cite. A rule
   that drifts out of the baseline is a check nobody decided on; a control that
   names this module and has no rule here is a claim with nothing behind it.

What none of it establishes is worth stating in the module that most invites the
confusion: **this reads files.** No cluster has installed the chart, no admission
controller applies any of these rules to a pod, and a manifest that satisfies the
policy is a manifest and not a workload. `DR-05` carries that gap and it is not
narrowed by anything here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.workload_policy import (
    RELEASE_SCOPED_RULES,
    RULE_IDS,
    check_documents,
    is_release_bundle,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

BASELINE_PATH = REPO_ROOT / "docs" / "security" / "security-baseline.v1alpha1.json"
POLICY_DOC = REPO_ROOT / "docs" / "security" / "workload-policy.md"
RENDERED_DIR = REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered"
DEPLOY_DIR = REPO_ROOT / "deploy"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "workload-policy"
INVALID_DIR = FIXTURE_DIR / "invalid"
EXPECTED_PATH = INVALID_DIR / "expected-rejections.json"

#: The module the baseline names as the verification for every control this
#: policy enforces. Written as the repository-relative path the baseline uses.
THIS_MODULE_REF = "tests/security/test_workload_policy.py"

#: Controls this module verifies that are not rules applied to a manifest.
#:
#: Exactly one, and it is named rather than derived so that it cannot grow
#: quietly: `refuse-a-workload-manifest-that-omits-a-required-control` is the
#: control that the validator has been *watched refusing*, which is a property of
#: the fixtures and the expectation record rather than a field in a pod
#: specification. Every other control naming this module is a rule the validator
#: can cite, and the test below fails if a second entry appears here without
#: somebody deciding it belongs.
NON_RULE_CONTROLS = frozenset(
    {"refuse-a-workload-manifest-that-omits-a-required-control"}
)


def _documents(path: Path) -> list[dict]:
    return [
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(document, dict)
    ]


BASELINE: dict[str, Any] = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
CONTROLS: list[dict] = BASELINE["controls"]
EXPECTED: dict[str, Any] = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))

RENDERS = {
    profile: _documents(RENDERED_DIR / f"{profile}.expected.yaml")
    for profile in ("mock", "real")
}

INVALID_FIXTURES = sorted(path.name for path in INVALID_DIR.glob("*.yaml"))
EXPECTED_BY_FIXTURE = {row["fixture"]: row for row in EXPECTED["fixtures"]}


# --------------------------------------------------------------------------
# The inputs were found
# --------------------------------------------------------------------------


def test_the_policy_inputs_were_actually_found() -> None:
    """A suite that found nothing passes every other test in this module."""
    assert len(RENDERS["mock"]) >= 4
    assert len(RENDERS["real"]) >= 8
    assert len(INVALID_FIXTURES) >= 8
    assert len(RULE_IDS) >= 10
    assert POLICY_DOC.exists(), "the policy document the rules are published in"


# --------------------------------------------------------------------------
# What the project renders satisfies the policy
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile", sorted(RENDERS))
def test_every_committed_render_satisfies_the_workload_policy(profile: str) -> None:
    findings = check_documents(RENDERS[profile])
    assert not findings, (
        f"the {profile} render is refused by the workload policy:\n"
        + "\n".join(f"  {finding}" for finding in findings)
    )


@pytest.mark.parametrize("profile", sorted(RENDERS))
def test_every_committed_render_is_recognised_as_a_release(profile: str) -> None:
    """The scope is derived, so the derivation is what has to be checked.

    Two of the rules apply only inside a release. If the renders stopped
    carrying the lifecycle label, those two rules would stop applying to them and
    every other test here would still pass -- which is the quiet failure this
    guards against rather than a theoretical one.
    """
    assert is_release_bundle(RENDERS[profile]), (
        f"the {profile} render carries no {'inferops.io/lifecycle'} label, so the "
        "release-scoped rules would silently stop applying to it"
    )


def test_the_trial_apparatus_satisfies_every_rule_that_reaches_it() -> None:
    """`deploy/` is smoke and trial apparatus, and it is held to the rest.

    A one-shot Job run by hand in a smoke namespace has no service to reach and
    nothing to reach it, so the two release-scoped rules do not apply. Every
    other rule does, and this is where that is established rather than assumed --
    including that the exemption is exactly two rules wide and not wider.
    """
    documents = [
        document
        for path in sorted(DEPLOY_DIR.rglob("*.yaml"))
        for document in _documents(path)
    ]
    assert documents, "no manifest was found under deploy/"
    assert not is_release_bundle(documents), (
        "a manifest under deploy/ carries the release lifecycle label; the "
        "apparatus and the release layer are meant to be distinguishable"
    )
    findings = check_documents(documents)
    assert not findings, (
        "the trial apparatus is refused by a rule that reaches it:\n"
        + "\n".join(f"  {finding}" for finding in findings)
    )


# --------------------------------------------------------------------------
# The fixtures are refused, and refused for the stated reason
# --------------------------------------------------------------------------


def test_every_invalid_fixture_has_a_recorded_expectation() -> None:
    """In both directions: no unrecorded fixture, no fixture-less record."""
    assert set(INVALID_FIXTURES) == set(EXPECTED_BY_FIXTURE), (
        "the fixture directory and expected-rejections.json disagree about which "
        f"fixtures exist: {set(INVALID_FIXTURES) ^ set(EXPECTED_BY_FIXTURE)}"
    )
    for row in EXPECTED["fixtures"]:
        assert row["rules"], f"{row['fixture']} records no expected rule"
        assert row["drops"].strip(), f"{row['fixture']} does not say what it drops"
        assert set(row["rules"]) <= set(RULE_IDS), (
            f"{row['fixture']} expects a rule the validator cannot cite"
        )


@pytest.mark.parametrize("fixture", INVALID_FIXTURES)
def test_an_insecure_fixture_is_refused_by_exactly_the_rules_it_records(
    fixture: str,
) -> None:
    findings = check_documents(_documents(INVALID_DIR / fixture))
    assert findings, (
        f"{fixture} is deliberately broken and the policy accepted it, which "
        "makes every passing result in this module unfalsifiable"
    )
    produced = {finding.rule for finding in findings}
    expected = set(EXPECTED_BY_FIXTURE[fixture]["rules"])
    assert produced == expected, (
        f"{fixture} is refused by {sorted(produced)} and records {sorted(expected)}. "
        "A fixture refused for a different reason is not the fixture that was "
        "written, so this is a failure rather than a pass."
    )


def test_no_finding_quotes_a_value_read_out_of_a_manifest() -> None:
    """A refusal is the string most likely to be pasted into a ticket.

    The secret fixture carries a placeholder that is not a credential, and the
    check is that the placeholder never appears in a finding: the rule fires on
    an environment name carrying a value, so the value is what must not travel.
    """
    fixture = "secret-value-in-a-manifest.yaml"
    documents = _documents(INVALID_DIR / fixture)
    literal = next(
        entry["value"]
        for document in documents
        if document.get("kind") == "Deployment"
        for container in document["spec"]["template"]["spec"]["containers"]
        for entry in container.get("env") or []
        if "value" in entry
    )
    assert literal, "the fixture no longer carries the literal this test reads"
    for finding in check_documents(documents):
        rendered = " ".join(finding.as_dict().values())
        assert literal not in rendered, (
            f"a finding for {fixture} quotes the value it refused"
        )


def test_the_fixtures_between_them_exercise_every_rule() -> None:
    """A rule no fixture reaches is a rule nobody has watched fire."""
    exercised = {rule for row in EXPECTED["fixtures"] for rule in row["rules"]}
    assert exercised == set(RULE_IDS), (
        "rules no fixture exercises: "
        f"{sorted(set(RULE_IDS) - exercised)}; fixtures citing an unknown rule: "
        f"{sorted(exercised - set(RULE_IDS))}"
    )


# --------------------------------------------------------------------------
# The policy and the baseline are one vocabulary
# --------------------------------------------------------------------------


def test_every_rule_the_validator_cites_is_a_control_the_baseline_declares() -> None:
    declared = {row["controlId"] for row in CONTROLS}
    invented = set(RULE_IDS) - declared
    assert not invented, (
        f"the validator can cite {sorted(invented)}, which the security baseline "
        "does not declare as a control"
    )


def test_every_control_that_names_this_module_is_a_rule_the_validator_cites() -> None:
    """The other direction, which is the one that catches a hollow claim.

    A control naming this module as its verification and having no rule here
    would derive an implemented status from a check that does not exist. The
    baseline's own suite confirms the named *function* is defined; this confirms
    the named *rule* is applied.
    """
    named = {
        row["controlId"]
        for row in CONTROLS
        if row["verification"]["ref"] == THIS_MODULE_REF
    }
    assert named, "no control names this module, so nothing in the baseline rests on it"
    missing = named - set(RULE_IDS) - NON_RULE_CONTROLS
    assert not missing, (
        f"{sorted(missing)} name this module as their verification and the "
        "validator cites no such rule"
    )
    assert named >= NON_RULE_CONTROLS, (
        "a control is excused from being a rule and the baseline no longer names "
        "this module for it"
    )
    assert not (NON_RULE_CONTROLS & set(RULE_IDS)), (
        "a control excused from being a rule is also a rule, so the exclusion is "
        "hiding nothing and should be removed"
    )


def test_a_release_scoped_rule_says_so_in_the_published_policy() -> None:
    """The exemption is a decision, so it is published rather than only coded."""
    body = POLICY_DOC.read_text(encoding="utf-8")
    for rule in sorted(RELEASE_SCOPED_RULES):
        assert f"`{rule}`" in body, (
            f"{rule} applies only inside a release and the policy document does "
            "not name it"
        )


@pytest.mark.parametrize("rule", sorted(RULE_IDS))
def test_the_policy_document_publishes_every_rule(rule: str) -> None:
    assert f"`{rule}`" in POLICY_DOC.read_text(encoding="utf-8"), (
        f"{rule} is enforced and the policy document does not publish it"
    )


# --------------------------------------------------------------------------
# The command line behaves as a gate
# --------------------------------------------------------------------------


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.workload_policy", *arguments],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


def test_the_command_exits_zero_on_the_committed_renders() -> None:
    result = _run(*(str(RENDERED_DIR / f"{p}.expected.yaml") for p in RENDERS))
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_command_exits_non_zero_on_an_insecure_fixture() -> None:
    """A gate that reports a refusal and exits zero is not a gate.

    This is checked through the process rather than through the function,
    because the exit status is the part a caller in a script actually reads and
    it is the part a refactor can drop without any test noticing.
    """
    result = _run(str(INVALID_DIR / "root-and-privileged-container.yaml"))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "run-as-non-root" in result.stdout


def test_the_command_emits_a_stable_json_report() -> None:
    result = _run("--json", str(INVALID_DIR / "unbounded-resources.yaml"))
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["valid"] is False
    assert {finding["rule"] for finding in report["findings"]} == {
        "declare-explicit-resource-requests-and-limits"
    }
    again = _run("--json", str(INVALID_DIR / "unbounded-resources.yaml"))
    assert again.stdout == result.stdout, "two runs over one input disagree"
