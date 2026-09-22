"""The V1 operator runbook, held to the repository it tells an operator to act on.

A runbook is read by somebody whose release is already failing, and it is followed
rather than checked. It rots in its own ways, and each group below covers one:

1. **The incidents it promises.** Every incident the story requires has a section,
   and every section answers the same six questions in the same order: detection,
   user impact, automatic recovery, human action, validation, and escalation. The
   recovery each one states, automatic or human, is the one the record gives it,
   both in the section and in the table at the top.
2. **The alerts that send people here.** Every alert in the alert record points at
   its own section of this page, the section is headed with the alert's name,
   starts with a command, and links to every incident the record routes it to. The
   alert document's table and both rendered rule files point at the same place.
3. **The commands.** Every tool command names a real module and a real
   subcommand. Every script exists and accepts the subcommand printed. Every
   ``kubectl`` and ``helm`` sample names the target file, the context, and the
   namespace. Every fenced block opens with a safety label its commands do not
   contradict, and nothing carries a credential, a force flag, or a namespace
   deletion.
4. **The values it quotes.** The target, the object names, the ports, the
   containers, and the defaults are compared against the file that owns each one.
5. **The figures it quotes.** Each one is read back from the record it came from,
   by JSON pointer where the record is data, and no grouped number appears on the
   page that is not declared.
6. **The links and the statements it may not drop.**

None of this establishes that following the page repairs anything. Every check reads
files from this repository and nothing else: no cluster, no engine, no network.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.inference_alerts import runbook_anchors

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_DIR = REPO_ROOT / "docs" / "environment"
DOCUMENT_PATH = ENVIRONMENT_DIR / "operator-runbook.md"
RECORD_PATH = ENVIRONMENT_DIR / "operator-runbook.v1alpha1.json"
ALERT_RECORD_PATH = REPO_ROOT / "docs" / "telemetry" / "inference-alerts.v1alpha1.json"
ALERT_DOCUMENT_PATH = REPO_ROOT / "docs" / "telemetry" / "inference-alerts.md"
LIB_PATH = REPO_ROOT / "scripts" / "environment" / "lib.sh"
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
RENDERED_REAL_PATH = CHART_DIR / "ci" / "rendered" / "real.expected.yaml"

DOCUMENT = DOCUMENT_PATH.read_text(encoding="utf-8")
RECORD: dict[str, Any] = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
ALERT_RECORD: dict[str, Any] = json.loads(ALERT_RECORD_PATH.read_text(encoding="utf-8"))
VALUES: dict[str, Any] = yaml.safe_load(
    (CHART_DIR / "values.yaml").read_text(encoding="utf-8")
)
REAL_VALUES: dict[str, Any] = yaml.safe_load(
    (CHART_DIR / "ci" / "real-values.yaml").read_text(encoding="utf-8")
)
RENDERED_REAL: list[dict[str, Any]] = [
    document
    for document in yaml.safe_load_all(RENDERED_REAL_PATH.read_text(encoding="utf-8"))
    if isinstance(document, dict)
]

FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$")


def _slug(text: str) -> str:
    """GitHub's fragment for a heading, the same rule the alert policy applies."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", text).strip().lower())


def _split(text: str) -> tuple[str, list[str]]:
    """The prose outside fenced blocks, and each fenced block's body."""
    prose: list[str] = []
    blocks: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if FENCE.match(line):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
            continue
        if current is None:
            prose.append(line)
        else:
            current.append(line)
    return "\n".join(prose), blocks


PROSE, BLOCKS = _split(DOCUMENT)
FENCED = "\n".join(BLOCKS)

#: The prose as one line without emphasis or code markers, so that reflowing a
#: paragraph or emphasising a phrase inside it neither fails a check nor evades one.
FLOWED = " ".join(PROSE.replace("**", "").replace("`", "").split())


def _section(slug: str) -> str:
    """One heading's own text, up to the next heading at its level or above."""
    collected: list[str] = []
    depth = 0
    fenced = False
    for line in DOCUMENT.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            if depth:
                collected.append(line)
            continue
        heading = None if fenced else HEADING.match(line)
        if heading is not None:
            level = len(heading.group("hashes"))
            if depth and level <= depth:
                break
            if not depth and _slug(heading.group("text")) == slug:
                depth = level
        if depth:
            collected.append(line)
    assert collected, f"no section #{slug} in the runbook"
    return "\n".join(collected)


def _headings(level: int) -> list[str]:
    found: list[str] = []
    fenced = False
    for line in DOCUMENT.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        heading = None if fenced else HEADING.match(line)
        if heading is not None and len(heading.group("hashes")) == level:
            found.append(heading.group("text"))
    return found


def _table_rows(text: str) -> list[list[str]]:
    """Every Markdown table row in ``text``, as its stripped cells."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= {"|", "-", " "}:
            continue
        rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    return rows


def _joined_commands(block: str) -> list[str]:
    """One string per command in a fenced block, continuation lines joined."""
    commands: list[str] = []
    continued = ""
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            continued += stripped[:-1] + " "
            continue
        commands.append(" ".join((continued + stripped).split()))
        continued = ""
    if continued:
        commands.append(" ".join(continued.split()))
    return commands


COMMANDS = [command for block in BLOCKS for command in _joined_commands(block)]

INCIDENTS: dict[str, dict[str, Any]] = {
    incident["incidentId"]: incident for incident in RECORD["incidents"]
}
ALERTS: dict[str, dict[str, Any]] = {
    alert["alertId"]: alert for alert in ALERT_RECORD["alerts"]
}
ROUTES: dict[str, dict[str, Any]] = {
    route["alertId"]: route for route in RECORD["alertRoutes"]
}


def _lib_constant(name: str) -> str:
    source = LIB_PATH.read_text(encoding="utf-8")
    match = re.search(
        rf'^readonly {re.escape(name)}="(?P<value>[^"]*)"', source, re.MULTILINE
    )
    assert match is not None, f"{name} is not defined in scripts/environment/lib.sh"
    return match.group("value")


def _rendered(kind: str, name: str) -> dict[str, Any]:
    for document in RENDERED_REAL:
        if (
            document.get("kind") == kind
            and document.get("metadata", {}).get("name") == name
        ):
            return document
    raise AssertionError(f"{kind}/{name} is not in the committed real render")


# --------------------------------------------------------------------------
# The record itself
# --------------------------------------------------------------------------


def test_the_record_declares_its_identity_and_contract_version() -> None:
    assert RECORD["$id"].endswith("/environment/operator-runbook.v1alpha1.json")
    assert RECORD["contractVersion"] == "inferops.io/v1alpha1"
    assert RECORD["documentRef"] == "docs/environment/operator-runbook.md"


def test_every_reference_the_record_makes_resolves() -> None:
    references = [
        RECORD["documentRef"],
        RECORD["alertRecordRef"],
        RECORD["troubleshootingRef"],
        RECORD["providerContractRef"],
        RECORD["evidenceRef"],
    ]
    for incident in RECORD["incidents"]:
        references += incident["evidenceRefs"]
    references += [figure["file"] for figure in RECORD["figures"]]
    for reference in references:
        assert (REPO_ROOT / reference).is_file(), reference


def test_the_page_names_its_record() -> None:
    assert "(operator-runbook.v1alpha1.json)" in DOCUMENT


# --------------------------------------------------------------------------
# 1. The incidents
# --------------------------------------------------------------------------


def test_every_incident_the_story_requires_has_a_procedure() -> None:
    """Pod loss, an unready model, latency and errors, resource pressure, a
    telemetry gap, a bad release, and a cost anomaly. Dropping one is a failure."""
    assert set(RECORD["requiredIncidents"]) == {
        "pod-loss",
        "unready-model",
        "latency-and-errors",
        "resource-pressure-and-out-of-memory",
        "telemetry-gap",
        "bad-release",
        "cost-anomaly",
    }
    assert set(RECORD["requiredIncidents"]) <= set(INCIDENTS)


def test_the_incident_headings_are_the_incidents_the_record_has() -> None:
    incidents_section = _section("incidents")
    headings = [
        _slug(match.group("text"))
        for match in (HEADING.match(line) for line in incidents_section.splitlines())
        if match is not None and len(match.group("hashes")) == 3
    ]
    assert headings == [incident["section"] for incident in RECORD["incidents"]]
    for incident in RECORD["incidents"]:
        assert _slug(incident["title"]) == incident["section"], incident["incidentId"]


@pytest.mark.parametrize("incident_id", sorted(INCIDENTS))
def test_every_incident_answers_the_six_questions_in_order(incident_id: str) -> None:
    section = _section(INCIDENTS[incident_id]["section"])
    questions = [row[0] for row in _table_rows(section) if len(row) == 2]
    # The first table in a section is its answer table; its header row is empty.
    answered = [question for question in questions if question]
    assert answered[: len(RECORD["incidentQuestions"])] == RECORD["incidentQuestions"]
    for row in _table_rows(section):
        if len(row) == 2 and row[0] in RECORD["incidentQuestions"]:
            assert len(row[1]) > 40, (incident_id, row[0])


def _answer(incident_id: str, question: str) -> str:
    section = _section(INCIDENTS[incident_id]["section"])
    for row in _table_rows(section):
        if len(row) == 2 and row[0] == question:
            return row[1]
    raise AssertionError(f"{incident_id} does not answer {question}")


#: How each recovery kind is written, at the start of the answer and in the
#: summary table. A section that says "Yes" for a kind the record calls "none"
#: is the overclaim this page exists not to make.
IN_SECTION = {"automatic": "**Yes", "partial": "**Partly", "none": "**None"}
IN_SUMMARY = {"automatic": "**Yes", "partial": "**Partly", "none": "**No"}


@pytest.mark.parametrize("incident_id", sorted(INCIDENTS))
def test_the_recovery_each_section_states_is_the_record_s(incident_id: str) -> None:
    incident = INCIDENTS[incident_id]
    kind = incident["automaticRecovery"]
    assert kind in {entry["kindId"] for entry in RECORD["recoveryKinds"]}
    assert _answer(incident_id, "Automatic recovery").startswith(IN_SECTION[kind])
    assert (kind == "automatic") is (not incident["humanActionRequired"])


def test_the_summary_table_states_the_same_recovery_and_evidence() -> None:
    rows = _table_rows(_section("automatic-and-human-recovery-at-a-glance"))
    by_section: dict[str, list[str]] = {}
    for row in rows:
        link = re.match(r"\[[^\]]+\]\(#(?P<slug>[^)]+)\)", row[0])
        if link is not None:
            by_section[link.group("slug")] = row
    assert set(by_section) == {incident["section"] for incident in RECORD["incidents"]}
    for incident in RECORD["incidents"]:
        row = by_section[incident["section"]]
        assert row[1].startswith(IN_SUMMARY[incident["automaticRecovery"]]), row
        assert incident["evidenceLabel"] in row[3], row


@pytest.mark.parametrize("incident_id", sorted(INCIDENTS))
def test_every_incident_names_its_evidence_label(incident_id: str) -> None:
    incident = INCIDENTS[incident_id]
    section = " ".join(_section(incident["section"]).replace("`", "").split())
    assert "Evidence: " in section, incident_id
    evidence = section.split("Evidence: ", 1)[1]
    if incident["evidenceLabel"] != "described":
        assert incident["evidenceLabel"] in evidence, incident_id
    else:
        assert "described" in evidence, incident_id


@pytest.mark.parametrize("incident_id", sorted(INCIDENTS))
def test_every_incident_names_the_alerts_that_detect_it(incident_id: str) -> None:
    incident = INCIDENTS[incident_id]
    detection = _answer(incident_id, "Detection")
    for alert_id in incident["alerts"]:
        assert alert_id in ALERTS, alert_id
        assert ALERTS[alert_id]["name"] in detection, (incident_id, alert_id)
        assert incident_id in ROUTES[alert_id]["routesTo"], (incident_id, alert_id)
    if not incident["alerts"]:
        assert incident.get("noAlertBecause"), incident_id


def test_every_deferred_alert_is_named_by_an_incident_it_would_have_detected() -> None:
    deferred = {entry["deferredId"] for entry in ALERT_RECORD["deferredAlerts"]}
    named = {
        deferred_id
        for incident in RECORD["incidents"]
        for deferred_id in incident["deferredAlerts"]
    }
    assert named <= deferred, sorted(named - deferred)
    assert named == deferred, sorted(deferred - named)


def test_every_incident_with_an_owner_names_one_the_alert_record_has() -> None:
    owners = {owner["ownerId"] for owner in ALERT_RECORD["owners"]}
    for incident in RECORD["incidents"]:
        assert incident["owner"] in owners | {None}, incident["incidentId"]


def test_an_incident_claimed_as_observed_carries_local_real_evidence() -> None:
    for incident in RECORD["incidents"]:
        if incident["observed"]:
            assert incident["evidenceLabel"] == "local-real-cpu", incident["incidentId"]
            assert any(
                ref.startswith("docs/proof/") for ref in incident["evidenceRefs"]
            ), incident["incidentId"]


# --------------------------------------------------------------------------
# 2. The alerts
# --------------------------------------------------------------------------


def test_every_alert_has_exactly_one_route() -> None:
    assert sorted(ROUTES) == sorted(ALERTS)
    assert len(RECORD["alertRoutes"]) == len(ROUTES)


@pytest.mark.parametrize("alert_id", sorted(ALERTS))
def test_every_alert_points_at_its_own_section_of_this_page(alert_id: str) -> None:
    route = ROUTES[alert_id]
    alert = ALERTS[alert_id]
    assert (
        alert["runbookRef"]
        == f"docs/environment/operator-runbook.md#{route['section']}"
    )
    assert route["section"] == _slug(alert["name"])
    assert route["section"] in runbook_anchors(DOCUMENT_PATH)
    assert alert["name"] in _headings(3)


@pytest.mark.parametrize("alert_id", sorted(ALERTS))
def test_every_alert_section_opens_with_a_read_only_command(alert_id: str) -> None:
    section = _section(ROUTES[alert_id]["section"])
    _, blocks = _split(section)
    assert blocks, alert_id
    assert blocks[0].lstrip().startswith("# read-only"), alert_id
    assert re.search(r"\b(kubectl|helm|docker|uv)\b", blocks[0]), alert_id


@pytest.mark.parametrize("alert_id", sorted(ALERTS))
def test_every_alert_section_links_every_incident_it_routes_to(alert_id: str) -> None:
    section = _section(ROUTES[alert_id]["section"])
    linked = set(re.findall(r"\]\(#(?P<slug>[a-z0-9-]+)\)", section))
    for incident_id in ROUTES[alert_id]["routesTo"]:
        assert INCIDENTS[incident_id]["section"] in linked, (alert_id, incident_id)
    incident_sections = {incident["section"] for incident in RECORD["incidents"]}
    assert linked & incident_sections == {
        INCIDENTS[incident_id]["section"]
        for incident_id in ROUTES[alert_id]["routesTo"]
    }, alert_id


@pytest.mark.parametrize("alert_id", sorted(ALERTS))
def test_every_alert_section_states_its_severity_and_owner(alert_id: str) -> None:
    alert = ALERTS[alert_id]
    section = _section(ROUTES[alert_id]["section"])
    assert f"{alert['severity'].capitalize()}" in section, alert_id
    owner = "serving path" if alert["owner"] == "serving" else "collection"
    assert f"Owner: the {owner}" in section, alert_id


def test_the_alert_document_s_table_points_where_the_record_does() -> None:
    text = ALERT_DOCUMENT_PATH.read_text(encoding="utf-8")
    for alert in ALERTS.values():
        row = next(
            line
            for line in text.splitlines()
            if f"| `{alert['name']}` | " in line and "](" in line
        )
        target = (
            "../environment/operator-runbook.md#" + alert["runbookRef"].split("#")[1]
        )
        assert f"]({target})" in row, alert["alertId"]


@pytest.mark.parametrize("profile", ["mock", "real"])
def test_both_rendered_rule_files_point_where_the_record_does(profile: str) -> None:
    rendered = yaml.safe_load(
        (
            REPO_ROOT
            / "deploy"
            / "prometheus"
            / f"inferops-inference-alerts.{profile}.yaml"
        ).read_text(encoding="utf-8")
    )
    by_name = {
        rule["alert"]: rule["annotations"]["runbook"]
        for group in rendered["groups"]
        for rule in group["rules"]
    }
    for alert in ALERTS.values():
        if profile in alert["profiles"]:
            assert by_name[alert["name"]] == alert["runbookRef"], alert["alertId"]


def test_the_page_does_not_claim_a_release_evaluates_the_alerts() -> None:
    """The release's collector loads recording rules and not the alert rule files.

    A first draft of this page sent the reader to the collector's own alerts page to
    see which alerts were firing. That page lists nothing: no chart here loads the
    rule files into any Prometheus. The chart is read to keep it that way.
    """
    collector = (CHART_DIR / "templates" / "telemetry-collector.yaml").read_text(
        encoding="utf-8"
    )
    rule_files = re.search(r"rule_files:\n((?:\s+- .+\n)+)", collector)
    assert rule_files is not None
    assert "alert" not in rule_files.group(1)
    assert "No installed release evaluates the alerts" in FLOWED
    assert "/alerts" not in DOCUMENT


# --------------------------------------------------------------------------
# 3. The commands
# --------------------------------------------------------------------------

TOOL_COMMAND = re.compile(
    r"python -m tools\.(?P<module>[a-z_]+)(?P<tail>(?: +[^\s`\"']+)*)"
)


def _accepted_subcommands(module: str) -> set[str]:
    """The subcommands a tool's ``__main__`` accepts, read from its parser."""
    source = (REPO_ROOT / "tools" / module / "__main__.py").read_text(encoding="utf-8")
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(str(node.args[0].value))
        for keyword in node.keywords:
            if keyword.arg == "choices" and isinstance(
                keyword.value, ast.Tuple | ast.List
            ):
                names.update(
                    str(element.value)
                    for element in keyword.value.elts
                    if isinstance(element, ast.Constant)
                )
    return names


TOOL_COMMANDS = sorted(
    {
        (
            match.group("module"),
            next(
                (
                    word
                    for word in match.group("tail").split()
                    if not word.startswith("-")
                ),
                "",
            ),
        )
        for match in TOOL_COMMAND.finditer(DOCUMENT)
    }
)


@pytest.mark.parametrize(
    "command", TOOL_COMMANDS, ids=lambda pair: f"{pair[0]}:{pair[1] or '<none>'}"
)
def test_every_tool_command_names_a_real_module_and_subcommand(
    command: tuple[str, str],
) -> None:
    module, argument = command
    if module == "pytest":
        return
    assert (REPO_ROOT / "tools" / module / "__main__.py").is_file(), module
    accepted = _accepted_subcommands(module)
    if accepted:
        # A tool whose only positional is a choice may be run with a flag alone.
        assert argument in accepted or argument == "", (
            module,
            argument,
            sorted(accepted),
        )
        return
    assert argument, (module, "takes a path and none was printed")
    assert (REPO_ROOT / argument).exists() or argument.startswith(".artifacts/"), (
        module,
        argument,
    )


def test_every_fenced_tool_command_runs_from_the_locked_environment() -> None:
    for command in COMMANDS:
        if "python -m " in command:
            assert command.startswith("uv run --locked python -m "), command


SCRIPT = re.compile(r"scripts/environment/(?P<name>[a-z0-9-]+\.sh)(?P<tail>[^\n]*)")


def test_every_script_the_page_names_exists() -> None:
    names = {match.group("name") for match in SCRIPT.finditer(DOCUMENT)}
    assert names
    for name in names:
        assert (REPO_ROOT / "scripts" / "environment" / name).is_file(), name


def _script_invocations() -> list[tuple[str, str, str]]:
    """``(script, subcommand or "", whole command)`` for every fenced invocation."""
    found: list[tuple[str, str, str]] = []
    for command in COMMANDS:
        match = SCRIPT.search(command)
        if match is None:
            continue
        words = match.group("tail").split()
        sub = words[0] if words and re.fullmatch(r"[a-z-]+", words[0]) else ""
        found.append((match.group("name"), sub, command))
    return found


@pytest.mark.parametrize(
    "invocation",
    _script_invocations(),
    ids=lambda item: f"{item[0]}:{item[1] or '<none>'}",
)
def test_every_script_subcommand_is_one_the_script_accepts(
    invocation: tuple[str, str, str],
) -> None:
    script, sub, _ = invocation
    if not sub:
        return
    text = (REPO_ROOT / "scripts" / "environment" / script).read_text(encoding="utf-8")
    usage = re.search(
        rf"^#.*{re.escape(script)}\s+{re.escape(sub)}\b", text, re.MULTILINE
    )
    case = re.search(rf"^\s*{re.escape(sub)}\)", text, re.MULTILINE)
    assert usage or case, (script, sub)


@pytest.mark.parametrize(
    "invocation",
    _script_invocations(),
    ids=lambda item: f"{item[0]}:{item[1] or '<none>'}",
)
def test_every_script_that_selects_a_target_is_given_the_provider(
    invocation: tuple[str, str, str],
) -> None:
    """No input has a default. A workflow run without one refuses, and a runbook
    that omitted it would hand the reader a refusal at the worst moment."""
    script, sub, command = invocation
    text = (REPO_ROOT / "scripts" / "environment" / script).read_text(encoding="utf-8")
    selects = re.search(r"^\s*inferops::resolve_target\s*$", text, re.MULTILINE)
    if selects is None or sub == "check":
        return
    assert command.startswith("INFEROPS_PROVIDER=docker-desktop "), command


def test_every_kubectl_and_helm_sample_is_scoped_to_the_target() -> None:
    kubeconfig = _lib_constant("INFEROPS_TARGET_KUBECONFIG_REL")
    namespace = _lib_constant("INFEROPS_RELEASE_NAMESPACE")
    seen = 0
    for command in COMMANDS:
        if not command.startswith(("kubectl ", "helm ")):
            continue
        seen += 1
        assert f"--kubeconfig {kubeconfig}" in command, command
        assert (
            "--context docker-desktop" in command
            or "--kube-context docker-desktop" in command
        ), command
        assert f"-n {namespace}" in command or f"--namespace {namespace}" in command, (
            command
        )
    assert seen >= 20


FORBIDDEN = (
    "--token",
    "--password",
    "--header",
    "--api-key",
    "--bearer",
    "--server",
    "--insecure-skip-tls-verify",
    "--force",
    "--create-namespace",
    "--all-namespaces",
    " -A ",
    "kubectl delete namespace",
    "docker system prune",
    "--grace-period=0",
)


@pytest.mark.parametrize("forbidden", FORBIDDEN)
def test_no_sample_carries_a_credential_a_force_or_a_wide_deletion(
    forbidden: str,
) -> None:
    assert forbidden not in FENCED, forbidden


LABELS = ("# read-only", "# mutating", "# destructive")

#: What makes a command change something. Read per command, after the flags that
#: scope it, so that a namespace called "install" could never satisfy it.
KUBECTL_MUTATING = {
    "apply",
    "create",
    "delete",
    "replace",
    "patch",
    "edit",
    "scale",
    "label",
    "annotate",
    "cordon",
    "drain",
    "taint",
    "set",
    "cp",
    "exec",
}
HELM_MUTATING = {"install", "upgrade", "rollback", "uninstall", "test"}
SCRIPT_MUTATING = {"apply", "destroy", "run", "certify", "build", "load", "cleanup"}
DESTRUCTIVE = ("uninstall", "destroy", "clean --confirm", "cluster-down.sh")


def _verb(command: str) -> str:
    words = command.split()
    rest: list[str] = []
    skip = False
    for word in words[1:]:
        if skip:
            skip = False
            continue
        if word in {"--kubeconfig", "--context", "--kube-context", "-n", "--namespace"}:
            skip = True
            continue
        rest.append(word)
    return " ".join(rest[:2])


def _mutates(command: str) -> bool:
    if command.startswith("kubectl "):
        verb = _verb(command)
        return verb.split()[0] in KUBECTL_MUTATING or verb in {
            "rollout restart",
            "rollout undo",
        }
    if command.startswith("helm "):
        return _verb(command).split()[0] in HELM_MUTATING
    script = SCRIPT.search(command)
    if script is not None:
        words = script.group("tail").split()
        if script.group("name") in {"cluster-down.sh", "cluster-up.sh"}:
            return True
        return bool(words) and words[0] in SCRIPT_MUTATING
    if "tools.model_acquisition acquire" in command or "clean --confirm" in command:
        return True
    return "tools.llm_load run" in command


def test_every_block_opens_with_a_safety_label() -> None:
    for block in BLOCKS:
        assert block.lstrip().startswith(LABELS), block


def test_no_block_labelled_read_only_changes_anything() -> None:
    for block in BLOCKS:
        if not block.lstrip().startswith("# read-only"):
            continue
        for command in _joined_commands(block):
            assert not _mutates(command), command


def test_every_block_that_changes_something_says_so() -> None:
    changing = 0
    for block in BLOCKS:
        commands = _joined_commands(block)
        if any(_mutates(command) for command in commands):
            changing += 1
            assert block.lstrip().startswith(("# mutating", "# destructive")), block
        if any(token in command for command in commands for token in DESTRUCTIVE):
            assert block.lstrip().startswith("# destructive") or (
                "--confirm" not in block and "clean" in block
            ), block
    assert changing >= 8


def test_the_mutating_detector_is_not_vacuous() -> None:
    """A detector that recognised nothing would pass every block above."""
    assert _mutates(
        "helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop "
        "uninstall inferops --namespace inferops-release"
    )
    assert _mutates(
        "kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop "
        "-n inferops-release delete pod x"
    )
    assert not _mutates(
        "kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop "
        "-n inferops-release get pods"
    )
    assert _mutates(
        "INFEROPS_PROVIDER=docker-desktop scripts/environment/terraform-prerequisites.sh apply"
    )
    assert not _mutates("scripts/environment/performance-scenarios.sh check")


def test_the_destroy_sample_carries_the_confirmation_the_wrapper_requires() -> None:
    destroys = [
        command
        for command in COMMANDS
        if "terraform-prerequisites.sh destroy" in command
    ]
    assert destroys
    for command in destroys:
        assert command.endswith("--confirm"), command


# --------------------------------------------------------------------------
# 4. The values
# --------------------------------------------------------------------------


def test_the_target_is_the_one_lib_defines() -> None:
    target = RECORD["target"]
    assert target["kubeconfig"] == _lib_constant("INFEROPS_TARGET_KUBECONFIG_REL")
    assert target["namespace"] == _lib_constant("INFEROPS_RELEASE_NAMESPACE")
    assert target["release"] == _lib_constant("INFEROPS_RELEASE_NAME")
    lib = LIB_PATH.read_text(encoding="utf-8")
    assert 'INFEROPS_TARGET_CONTEXT="docker-desktop"' in lib
    assert 'INFEROPS_TARGET_CONTEXT="kind-${INFEROPS_KIND_CLUSTER_NAME}"' in lib
    rows = {
        row[0]: row[1] for row in _table_rows(_section("the-target")) if len(row) == 3
    }
    assert f"`{target['kubeconfig']}`" in rows["Kubeconfig"]
    assert f"`{target['namespace']}`" in rows["Namespace"]
    assert f"`{target['release']}`" in rows["Release"]
    assert "`docker-desktop`" in rows["Context"] and "`kind-`" in rows["Context"]


@pytest.mark.parametrize(
    ("row", "deployment", "container", "service", "port"),
    [
        ("Platform API", "inferops-inferops-llm", "api", "inferops-inferops-llm", 8090),
        (
            "Serving runtime",
            "inferops-inferops-llm-runtime",
            "runtime",
            "inferops-inferops-llm-runtime",
            8080,
        ),
        (
            "Collector",
            "inferops-inferops-llm-collector",
            "collector",
            "inferops-inferops-llm-collector",
            9090,
        ),
    ],
)
def test_every_object_the_target_table_names_is_the_rendered_one(
    row: str, deployment: str, container: str, service: str, port: int
) -> None:
    rows = {
        cells[0]: cells[1]
        for cells in _table_rows(_section("the-target"))
        if len(cells) == 3
    }
    cell = rows[row]
    rendered = _rendered("Deployment", deployment)
    containers = [c["name"] for c in rendered["spec"]["template"]["spec"]["containers"]]
    assert containers == [container]
    ports = [p["port"] for p in _rendered("Service", service)["spec"]["ports"]]
    assert ports == [port]
    for literal in (deployment, container, str(port)):
        assert f"`{literal}`" in cell, (row, literal)


def test_the_init_container_and_the_claim_are_the_rendered_and_declared_ones() -> None:
    runtime = _rendered("Deployment", "inferops-inferops-llm-runtime")
    init = [c["name"] for c in runtime["spec"]["template"]["spec"]["initContainers"]]
    assert init == ["verify-model"]
    assert REAL_VALUES["model"]["cache"]["claimName"] == "inferops-model-cache"
    assert "`inferops-model-cache`" in DOCUMENT


def test_every_object_a_command_addresses_is_one_the_chart_renders() -> None:
    names = {
        document["metadata"]["name"]
        for document in RENDERED_REAL
        if document.get("kind") in {"Deployment", "Service"}
    }
    for match in re.finditer(r"(?:deployment|svc)/(?P<name>[a-z0-9-]+)", FENCED):
        assert match.group("name") in names, match.group(0)
    for match in re.finditer(
        r"kubernetes\.io/service-name=(?P<name>[a-z0-9-]+)", FENCED
    ):
        assert match.group("name") in names, match.group(0)
    components = {
        document["metadata"]["labels"]["app.kubernetes.io/component"]
        for document in RENDERED_REAL
        if document.get("kind") == "Deployment"
    }
    for match in re.finditer(
        r"app\.kubernetes\.io/component=(?P<value>[a-z-]+)", FENCED
    ):
        assert match.group("value") in components, match.group(0)


def test_every_container_a_command_names_belongs_to_the_deployment_it_names() -> None:
    """A container name is only meaningful beside the workload that has it.

    Independent review found the first form of this check read every ``-c`` value
    against one allow-list of all four names, so ``logs deployment/inferops-inferops-llm
    -c verify-model`` -- an init container the API does not have -- would have
    passed. Each one is now read against the rendered pod template of the
    Deployment named in the same command.
    """
    paired = 0
    for command in COMMANDS:
        container = re.search(r" -c (?P<name>[a-z-]+)", command)
        if container is None:
            continue
        deployment = re.search(r"deployment/(?P<name>[a-z0-9-]+)", command)
        assert deployment is not None, command
        spec = _rendered("Deployment", deployment.group("name"))["spec"]["template"][
            "spec"
        ]
        names = {c["name"] for c in spec["containers"]} | {
            c["name"] for c in spec.get("initContainers", [])
        }
        assert container.group("name") in names, command
        paired += 1
    assert paired >= 5


def test_the_defaults_the_page_quotes_are_the_values_file_s() -> None:
    assert VALUES["api"]["requestTimeoutMs"] == 120000
    assert "which is 120000 by default" in FLOWED
    assert "over 60 seconds" in FLOWED
    assert VALUES["runtime"]["parallelSlots"] == 1
    assert "runtime.parallelSlots is 1 by default" in FLOWED
    assert VALUES["runtime"]["probes"]["startup"]["budgetMs"] == 600000
    assert "runtime.probes.startup.budgetMs of 600000 ms" in FLOWED
    resources = VALUES["runtime"]["resources"]
    assert (resources["requests"]["cpu"], resources["requests"]["memory"]) == (
        "1",
        "2Gi",
    )
    assert (resources["limits"]["cpu"], resources["limits"]["memory"]) == ("6", "3Gi")
    assert "1 CPU and 2Gi requested, and a 6 CPU and 3Gi limit" in FLOWED
    assert REAL_VALUES["telemetry"]["collection"]["collector"]["deploy"] is True


def test_the_forward_ports_do_not_collide_with_each_other() -> None:
    forwards = re.findall(
        r"port-forward \S+ (?P<local>\d+):(?P<remote>\d+)", " ".join(COMMANDS)
    )
    locals_ = [local for local, _ in forwards]
    assert len(locals_) == len(set(locals_)) >= 2
    for local, _ in forwards:
        assert f"http://127.0.0.1:{local}" in DOCUMENT


def test_both_verify_model_refusals_are_the_rendered_ones() -> None:
    runtime = _rendered("Deployment", "inferops-inferops-llm-runtime")
    script = "\n".join(
        str(part)
        for container in runtime["spec"]["template"]["spec"]["initContainers"]
        for part in container.get("command", [])
    )
    refusals = re.findall(r"REFUSED: [^\"\n]+", script)
    assert len(refusals) == 2
    for refusal in refusals:
        assert refusal in DOCUMENT, refusal


# --------------------------------------------------------------------------
# 5. The figures
# --------------------------------------------------------------------------


def _resolve(document: Any, pointer: str) -> Any:
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        document = (
            document[int(token)] if isinstance(document, list) else document[token]
        )
    return document


@pytest.mark.parametrize("figure", RECORD["figures"], ids=lambda f: f["figureId"])
def test_every_figure_is_read_back_from_the_record_it_came_from(
    figure: dict[str, Any],
) -> None:
    assert figure["text"] in DOCUMENT, figure["figureId"]
    source = REPO_ROOT / figure["file"]
    if figure["pointer"] is None:
        assert figure["text"] in source.read_text(encoding="utf-8"), figure["figureId"]
        return
    value = _resolve(json.loads(source.read_text(encoding="utf-8")), figure["pointer"])
    assert isinstance(value, int), figure["figureId"]
    assert f"{value:,}" in figure["text"], (figure["figureId"], value)


def test_no_grouped_number_appears_that_is_not_declared() -> None:
    """A figure typed onto the page and declared nowhere is a figure nobody checks."""
    declared = " ".join(figure["text"] for figure in RECORD["figures"])
    for match in re.finditer(r"\b\d{1,3}(?:,\d{3})+\b", PROSE):
        assert match.group(0) in declared, match.group(0)


# --------------------------------------------------------------------------
# 6. Links, drills, and the statements the page may not drop
# --------------------------------------------------------------------------

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((?P<target>[^)\s]+)\)")
LINKS = sorted({match.group("target") for match in MARKDOWN_LINK.finditer(PROSE)})


@pytest.mark.parametrize("target", LINKS)
def test_every_link_and_fragment_resolves(target: str) -> None:
    if target.startswith(("http://", "https://")):
        return
    path, _, fragment = target.partition("#")
    document = (ENVIRONMENT_DIR / path).resolve() if path else DOCUMENT_PATH
    assert document.exists(), target
    if fragment and document.suffix == ".md":
        assert fragment in runbook_anchors(document), target


@pytest.mark.parametrize("drill", RECORD["drills"], ids=lambda d: d["command"][:60])
def test_every_drill_is_a_command_on_the_page_and_in_the_record(
    drill: dict[str, Any],
) -> None:
    assert drill["command"] in COMMANDS, drill["command"]
    evidence = (REPO_ROOT / RECORD["evidenceRef"]).read_text(encoding="utf-8")
    assert drill["command"] in evidence, drill["command"]


def test_no_drill_changes_anything() -> None:
    for drill in RECORD["drills"]:
        assert not _mutates(drill["command"]), drill["command"]


REQUIRED_STATEMENTS = (
    "Every result behind this page is docker-desktop's",
    "No installed release evaluates the alerts, and nothing pages anybody",
    "No script in this repository leaves a release running",
    "A disruption shorter than that fires nothing",
    "Pod readiness is not what a caller sees",
    "Do not raise the probe budget to make a slow host look healthy",
    "Nothing detects this at run time",
    "nobody other than the author has followed any of them from here",
    "It checks strings. It does not check a cluster.",
)


@pytest.mark.parametrize("statement", REQUIRED_STATEMENTS)
def test_the_page_keeps_the_statement_it_is_not_entitled_to_drop(
    statement: str,
) -> None:
    assert statement in FLOWED, statement


def test_the_page_names_the_suite_that_checks_it() -> None:
    assert "tests/architecture/test_operator_runbook.py" in DOCUMENT
