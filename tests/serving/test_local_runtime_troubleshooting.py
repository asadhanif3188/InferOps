"""The local runtime troubleshooting guide, held to the repository it describes.

A troubleshooting page is read by someone who has already run out of patience,
and every command on it is trusted rather than checked. That makes drift in this
particular document more expensive than drift in most: a guide naming a
subcommand that no longer exists, an exit code the tool no longer returns, or a
port the descriptor no longer pins sends the reader further from the fault.

So the page is checked against the things it quotes rather than proofread. Six
properties, each corresponding to a way this document rots:

1. **A command that does not exist.** Every ``python -m tools.<module> <sub>``
   the page prints must name a module in this repository and a subcommand that
   module's argument parser accepts.
2. **An exit code the tool does not return.** The vocabulary table is compared
   against the constants the tools define, in both directions.
3. **A number whose owner disagrees.** Ports, byte counts, budgets, the cache
   root, and the capacity floor are each compared against the record that owns
   them, never against a second copy.
4. **A link that goes nowhere.** Every relative Markdown target outside a fenced
   block resolves from this document's own directory.
5. **A credential in a command.** No fenced block may carry a token, header,
   password, or alternate-URL flag, because the tooling accepts none and a guide
   that appears to need one teaches the wrong recovery.
6. **A claim the page is not entitled to make.** It must keep saying that
   Kubernetes is out of scope and that the executed evidence is one host's.

What this suite establishes is that the document describes this repository. It
establishes nothing about whether following it fixes anything: the recoveries
that start a container or transfer bytes are authorisation-gated and were not
executed, here or anywhere in the default lane.

Every check reads files from this repository and nothing else. No network, no
cluster, no model, no container engine, no clock, no randomness.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
SERVING_DIR = DOCS_DIR / "serving"
DOCUMENT_PATH = SERVING_DIR / "local-runtime-troubleshooting.md"

PACKAGE_PATH = (
    REPO_ROOT / "deploy" / "serving" / "runtime" / "container-package.v1.json"
)
COMPOSITION_PATH = REPO_ROOT / "deploy" / "serving" / "local" / "composition.v1.json"
LIFECYCLE_PATH = (
    REPO_ROOT / "deploy" / "serving" / "lifecycle" / "model-lifecycle.v1.json"
)
CERTIFICATION_PATH = (
    REPO_ROOT / "deploy" / "serving" / "certification" / "c2-smoke.v1.json"
)
MODEL_SOURCE_PATH = SERVING_DIR / "model-source.v1.json"
PROFILE_PATH = SERVING_DIR / "runtime-profile.local.v1.json"
VALIDATION_RECORD = DOCS_DIR / "proof" / "serving" / "v1-s2-008-pr1-validation.md"

DOCUMENT = DOCUMENT_PATH.read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    """Everything outside a fenced code block, joined by newlines."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def _fenced_blocks(text: str) -> list[str]:
    """Every fenced code block's body, one string per block."""
    blocks: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
            continue
        if current is not None:
            current.append(line)
    return blocks


PROSE = _strip_fences(DOCUMENT)
BLOCKS = _fenced_blocks(DOCUMENT)
FENCED = "\n".join(BLOCKS)

#: The prose as one line, without emphasis markers. A sentence this document is
#: required to keep is a sentence, not a line: reflowing a paragraph must not
#: fail a check, and emphasising a phrase must not evade one.
FLOWED = " ".join(PROSE.replace("**", "").split())


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


PACKAGE = _load(PACKAGE_PATH)
COMPOSITION = _load(COMPOSITION_PATH)
LIFECYCLE = _load(LIFECYCLE_PATH)
CERTIFICATION = _load(CERTIFICATION_PATH)
MODEL_SOURCE = _load(MODEL_SOURCE_PATH)
PROFILE = _load(PROFILE_PATH)


def _grouped(value: int) -> str:
    """A whole number the way this repository writes one: 1,834,426,016."""
    return f"{value:,}"


# --------------------------------------------------------------------------
# The commands the page prints
# --------------------------------------------------------------------------

#: ``uv run --locked python -m tools.model_lifecycle cache --verify`` and the
#: bare ``python -m tools.x y`` form. The subcommand is the first token after
#: the module that is not a flag; a module invoked with none is captured as an
#: empty string and checked separately.
TOOL_COMMAND = re.compile(
    r"python -m tools\.(?P<module>[a-z_]+)(?P<tail>(?: +[^\s`\"']+)*)"
)

#: Flags that would mean this workflow accepts a credential or a redirect. None
#: of the tools defines one, and a sample that appeared to would teach a reader
#: to look for a secret this repository does not have.
FORBIDDEN_FLAGS = (
    "--token",
    "--password",
    "--header",
    "--auth",
    "--api-key",
    "--apikey",
    "--bearer",
    "--credential",
    "--url",
    "--cache-path",
    "--cache-dir",
    "--force",
)


def documented_tool_commands() -> set[tuple[str, str]]:
    """Every ``(module, subcommand)`` pair the document prints, fenced or not."""
    found: set[tuple[str, str]] = set()
    for match in TOOL_COMMAND.finditer(DOCUMENT):
        module = match.group("module")
        arguments = match.group("tail").split()
        subcommand = next(
            (word for word in arguments if not word.startswith("-")),
            "",
        )
        found.add((module, subcommand))
    return found


def accepted_subcommands(module: str) -> set[str]:
    """The subcommands a tool's ``__main__`` accepts, read from its source.

    Read from the argument parser rather than executed, because two of these
    modules build a parser at import time and one of them reads committed JSON
    while doing it. The two shapes this repository uses are a ``choices=(...)``
    tuple on a positional argument and a series of ``add_parser("name", ...)``
    calls on a subparser; both are collected.
    """
    source = (REPO_ROOT / "tools" / module / "__main__.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename=f"tools/{module}/__main__.py")
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attribute = node.func
        if (
            isinstance(attribute, ast.Attribute)
            and attribute.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(str(node.args[0].value))
        for keyword in node.keywords:
            if keyword.arg != "choices":
                continue
            if isinstance(keyword.value, ast.Tuple | ast.List):
                names.update(
                    str(element.value)
                    for element in keyword.value.elts
                    if isinstance(element, ast.Constant)
                )
    return names


DOCUMENTED_COMMANDS = sorted(documented_tool_commands())


@pytest.mark.parametrize(
    "command", DOCUMENTED_COMMANDS, ids=lambda pair: f"{pair[0]}:{pair[1] or '<none>'}"
)
def test_every_documented_command_names_a_module_that_exists(
    command: tuple[str, str],
) -> None:
    module, _ = command
    assert (REPO_ROOT / "tools" / module / "__main__.py").is_file(), module


@pytest.mark.parametrize(
    "command", DOCUMENTED_COMMANDS, ids=lambda pair: f"{pair[0]}:{pair[1] or '<none>'}"
)
def test_every_documented_command_names_a_subcommand_the_tool_accepts(
    command: tuple[str, str],
) -> None:
    """The check that catches a renamed subcommand, which is the usual drift."""
    module, subcommand = command
    accepted = accepted_subcommands(module)
    assert subcommand, {
        "module": module,
        "problem": "the page printed this module with no subcommand",
        "accepted": sorted(accepted),
    }
    assert subcommand in accepted, {
        "module": module,
        "documented": subcommand,
        "accepted": sorted(accepted),
    }


def test_the_page_reaches_every_tool_a_reader_may_need() -> None:
    """A guide that documents four of the six workflows sends readers elsewhere."""
    reached = {module for module, _ in DOCUMENTED_COMMANDS}
    assert {
        "model_acquisition",
        "model_lifecycle",
        "runtime_packaging",
        "local_composition",
    } <= reached, sorted(reached)


def test_every_command_sample_runs_from_the_locked_environment() -> None:
    """``--locked`` is not decoration, and a sample without it is a different run."""
    for block in BLOCKS:
        for line in block.splitlines():
            if "python -m tools." not in line and "python -c" not in line:
                continue
            if not line.lstrip().startswith("uv run"):
                continue
            assert "--locked" in line, line


@pytest.mark.parametrize("flag", FORBIDDEN_FLAGS)
def test_no_command_sample_carries_a_credential_or_a_redirect(flag: str) -> None:
    """The tooling accepts none of these, and a sample implying otherwise misleads."""
    assert flag not in FENCED, flag


def test_every_inline_python_sample_parses() -> None:
    """A one-liner that does not parse is a diagnostic nobody can run.

    The samples are extracted from their shell quoting and parsed rather than
    executed: one of them reads the process environment and one reads a
    platform-specific library, and neither belongs in a default-lane run.
    """
    samples = re.findall(r'python -c "(.*?)"', DOCUMENT, flags=re.DOTALL)
    assert samples, "the page publishes inline diagnostics; none were extracted"
    for sample in samples:
        ast.parse(sample)


# --------------------------------------------------------------------------
# The exit codes the page publishes
# --------------------------------------------------------------------------

#: Every module whose exit vocabulary the page's table describes.
EXIT_CODE_MODULES = (
    "model_acquisition",
    "model_lifecycle",
    "runtime_packaging",
    "local_composition",
    "runtime_certification",
    "serving_baseline",
    "runtime_configuration",
)


def exit_constants(module: str) -> dict[str, int]:
    entry = importlib.import_module(f"tools.{module}.__main__")
    return {
        name: value
        for name, value in vars(entry).items()
        if name.startswith("EXIT_") and isinstance(value, int)
    }


def test_the_shared_success_and_refusal_codes_are_what_the_tools_return() -> None:
    """`0` succeeded and `3` refused are the two the whole page leans on."""
    for module in EXIT_CODE_MODULES:
        constants = exit_constants(module)
        assert constants["EXIT_OK"] == 0, module
        refusal = constants.get("EXIT_REFUSED", constants.get("EXIT_INVALID"))
        if module == "model_acquisition":
            refusal = constants["EXIT_PREFLIGHT"]
        assert refusal == 3, (module, constants)


def test_the_acquisition_stage_codes_are_the_ones_the_page_splits_out() -> None:
    """The page tells a reader the stage from the number; this is that mapping."""
    constants = exit_constants("model_acquisition")
    assert constants["EXIT_PREFLIGHT"] == 3
    assert constants["EXIT_VERIFICATION"] == 4
    assert constants["EXIT_ACQUISITION"] == 5
    assert constants["EXIT_CLEANUP"] == 6


def test_the_composition_not_ready_code_is_distinct_from_refused_and_failed() -> None:
    """Exit `5` is the one a reader is most likely to misread as a failure."""
    constants = exit_constants("local_composition")
    assert constants["EXIT_NOT_READY"] == 5
    assert constants["EXIT_REFUSED"] == 3
    assert constants["EXIT_FAILED"] == 4


def test_the_baseline_criteria_code_is_the_one_the_page_publishes() -> None:
    assert exit_constants("serving_baseline")["EXIT_CRITERIA_UNMET"] == 6


@pytest.mark.parametrize("code", ("`0`", "`3`", "`4`", "`5`", "`6`", "`130`"))
def test_the_page_publishes_every_code_in_the_shared_vocabulary(code: str) -> None:
    assert code in PROSE, code


# --------------------------------------------------------------------------
# The numbers, each against the record that owns it
# --------------------------------------------------------------------------


def test_the_documented_runtime_port_is_the_one_the_package_publishes() -> None:
    published = PACKAGE["network"]["publishedPort"]
    assert f"`{published}`" in PROSE, published


def test_the_documented_api_port_is_the_one_the_composition_publishes() -> None:
    port = COMPOSITION["api"]["port"]
    assert f"`{port}`" in PROSE, port


def test_the_documented_liveness_port_agrees_with_the_lifecycle_record() -> None:
    """The page tells a reader to probe a port; it must be the probed one."""
    liveness = LIFECYCLE["probes"]["liveness"]["port"]
    assert liveness == PACKAGE["network"]["publishedPort"]


def test_the_port_probe_a_reader_runs_names_exactly_the_two_pinned_ports() -> None:
    """The check that a mention-anywhere assertion cannot make.

    The two tests above establish that each port is written down somewhere,
    which a document mentioning `8080` in four other sentences satisfies without
    the table being right. This one reads the tuple out of the diagnostic a
    reader actually pastes into a shell, and holds it to the two descriptors —
    so a port that changed in a record, or a third one invented in the guide,
    fails here rather than sending someone to look at the wrong socket.
    """
    pinned = (PACKAGE["network"]["publishedPort"], COMPOSITION["api"]["port"])
    probes = re.findall(r"for port in \(([^)]*)\)", FENCED)
    assert len(probes) == 1, probes
    probed = tuple(int(value) for value in probes[0].split(","))
    assert probed == pinned, {"probed": probed, "pinned": pinned}


def test_the_documented_byte_count_is_the_pinned_one() -> None:
    expected = MODEL_SOURCE["expectedSizeBytes"]
    assert _grouped(expected) in DOCUMENT, expected


def test_the_documented_cache_root_is_the_one_the_model_source_record_owns() -> None:
    root = MODEL_SOURCE["cache"]["path"]
    assert root in DOCUMENT, root
    assert LIFECYCLE["cache"]["rootPath"] == root


def test_the_documented_startup_budget_is_the_one_the_lifecycle_record_owns() -> None:
    budget = LIFECYCLE["startup"]["budgetMs"]
    assert _grouped(budget) in DOCUMENT, budget


def test_the_documented_drain_budget_is_the_one_the_lifecycle_record_owns() -> None:
    budget = LIFECYCLE["shutdown"]["drainTimeoutMs"]
    assert _grouped(budget) in DOCUMENT, budget


def test_the_documented_memory_envelope_is_the_profile_selection() -> None:
    resources = PROFILE["resources"]
    for value in (resources["memoryRequestMiB"], resources["memoryLimitMiB"]):
        assert f"{_grouped(value)} MiB" in DOCUMENT, value


def test_the_documented_capacity_floor_is_the_certification_prerequisite() -> None:
    """A reader sizing a host from this table must get the enforced numbers."""
    prerequisites = CERTIFICATION["prerequisites"]
    assert f"| {prerequisites['minimumLogicalCpus']} |" in PROSE
    for key in ("minimumEngineMemoryBytes", "minimumFreeDiskBytes"):
        assert _grouped(prerequisites[key]) in PROSE, key


def test_the_documented_ownership_label_is_the_package_label() -> None:
    """The reader runs this against Docker; a stale label lists nothing."""
    labels = PACKAGE["container"]["labels"]
    key = "io.inferops.package"
    assert f"{key}={labels[key]}" in DOCUMENT, labels


def test_the_readiness_statuses_are_the_ones_the_lifecycle_record_declares() -> None:
    """Not just present: attached to the right meaning.

    Independent review found the first form of this test asserting only that
    ``503`` and ``200`` each appeared somewhere in the prose. Swapping the two
    rows of the readiness table — so the page said a `200` during load meant
    `runtime-loading` and a `503` meant ready — left both tokens present and the
    test passing, while reversing the single most safety-critical fact on the
    page. Presence is not agreement, so the row each status sits in is read.
    """
    readiness = LIFECYCLE["probes"]["readiness"]
    loading = readiness["loadingStatus"]
    ready = readiness["readyStatus"]
    assert readiness["path"] in DOCUMENT

    rows = [line for line in PROSE.splitlines() if line.startswith("| `")]
    loading_row = next(
        (row for row in rows if f"`{loading}` on `{readiness['path']}`" in row), None
    )
    ready_row = next(
        (row for row in rows if f"`{ready}` on `{readiness['path']}`" in row), None
    )
    assert loading_row is not None, f"no row reads `{loading}` on `{readiness['path']}`"
    assert ready_row is not None, f"no row reads `{ready}` on `{readiness['path']}`"

    #: The loading status must be explained as loading, and must not be the row
    #: that describes a ready runtime. The ready status is the mirror.
    assert "runtime-loading" in loading_row, loading_row
    assert "runtime-loading" not in ready_row, ready_row
    assert "ready" in ready_row.lower(), ready_row


# --------------------------------------------------------------------------
# The environment variables it names
# --------------------------------------------------------------------------

DOCUMENTED_VARIABLES = sorted(set(re.findall(r"INFEROPS_[A-Z_]+", DOCUMENT)))


@pytest.mark.parametrize("name", DOCUMENTED_VARIABLES)
def test_every_environment_variable_named_is_one_the_distribution_reads(
    name: str,
) -> None:
    """A variable this repository does not read is a variable nobody should set."""
    sources = list((REPO_ROOT / "src" / "inferops").rglob("*.py"))
    sources += list((REPO_ROOT / "tools").rglob("*.py"))
    assert any(name in path.read_text(encoding="utf-8") for path in sources), name


def test_the_required_request_timeout_is_still_required() -> None:
    """The page tells a reader this one has no default. That must stay true."""
    selection = (REPO_ROOT / "src" / "inferops" / "api" / "selection.py").read_text(
        encoding="utf-8"
    )
    assert "_required_int(environment, ENV_REQUEST_TIMEOUT_MS)" in selection


#: The timeout table's rows: the variable, and the cell claiming whether it is
#: required. Read from the document so that the claim itself is the thing tested.
TIMEOUT_ROW = re.compile(
    r"^\| `(?P<name>INFEROPS_[A-Z_]+)` \| (?P<requirement>[^|]+?) \|", re.MULTILINE
)


def _variables_the_distribution_requires() -> set[str]:
    """Every variable read through the refusing accessor, from the source.

    Derived from the two modules that read the environment rather than listed
    here, because a list here would be a third copy of the answer and the whole
    point is that the document is compared with the code.
    """
    required: set[str] = set()
    for relative in (
        Path("src") / "inferops" / "api" / "selection.py",
        Path("src") / "inferops" / "adapters" / "llama_cpp" / "settings.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        constants = dict(
            re.findall(r'^(ENV_[A-Z_]+) = "(INFEROPS_[A-Z_]+)"', source, re.MULTILINE)
        )
        for constant in re.findall(
            r"_required(?:_int)?\([^,]+, (ENV_[A-Z_]+)\)", source
        ):
            if constant in constants:
                required.add(constants[constant])
    return required


def test_the_timeout_table_says_required_exactly_where_the_code_requires() -> None:
    """The check that a "mention the number" assertion cannot make.

    Independent review found this table calling 300,000 ms the *default* for
    ``INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS``, in explicit contrast to the
    request timeout beside it. The variable is in fact required with no default —
    read through the same refusing accessor — so a reader who omitted it expecting
    a five-minute fallback got a refusal instead. Nothing caught it, because every
    number on the page was individually correct.

    So the claim is compared with the code rather than the figure with a record: a
    row saying "required" must name a variable the distribution refuses to run
    without, and a row offering a default must name one it does not.
    """
    required = _variables_the_distribution_requires()
    rows = TIMEOUT_ROW.findall(PROSE)
    assert len(rows) >= 3, rows

    for name, requirement in rows:
        claims_required = "required" in requirement.lower()
        claims_default = "default" in requirement.lower() and not claims_required
        assert claims_required or claims_default, (name, requirement)
        assert claims_required == (name in required), {
            "variable": name,
            "the page says": requirement.strip(),
            "the code requires it": name in required,
        }


def test_the_startup_budget_is_read_through_the_refusing_accessor() -> None:
    """Named on its own because it is the row that was wrong.

    A general check that passes for the wrong reason is how the first version of
    this suite missed it, so the specific fact is asserted where a reader of the
    test file can see it.
    """
    assert (
        "INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS"
        in _variables_the_distribution_requires()
    )


# --------------------------------------------------------------------------
# Links, scope, and the claims it is entitled to make
# --------------------------------------------------------------------------

LINK = re.compile(r"\]\(([^)]+)\)")


def relative_targets() -> list[str]:
    return [
        target
        for target in LINK.findall(PROSE)
        if not target.startswith(("http://", "https://", "mailto:", "#"))
    ]


@pytest.mark.parametrize("target", relative_targets(), ids=lambda target: target)
def test_every_relative_link_resolves(target: str) -> None:
    path = target.split("#", 1)[0]
    if not path:
        return
    assert (SERVING_DIR / path).exists(), target


def _anchors(document: Path) -> set[str]:
    """The GitHub-style anchors a Markdown document's own headings produce."""
    anchors: set[str] = set()
    for line in _strip_fences(document.read_text(encoding="utf-8")).splitlines():
        if not line.startswith("#"):
            continue
        heading = line.lstrip("#").strip()
        slug = re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")
        anchors.add(slug)
    return anchors


FRAGMENT_TARGETS = [target for target in relative_targets() if "#" in target]


@pytest.mark.parametrize("target", FRAGMENT_TARGETS, ids=lambda target: target)
def test_every_cross_document_fragment_names_a_heading_that_exists(
    target: str,
) -> None:
    """The half of a link the existence check cannot see.

    ``test_every_relative_link_resolves`` strips the fragment before checking the
    file, so a link to a real document and a heading that was later renamed
    passes it while landing the reader at the top of a long page instead of at
    the section the sentence promised. Independent review pointed this out; the
    five fragments were correct at the time, and this is what keeps them so.
    """
    path, fragment = target.split("#", 1)
    if not path:
        return
    assert fragment in _anchors(SERVING_DIR / path), {
        "target": target,
        "headings in that document": sorted(_anchors(SERVING_DIR / path)),
    }


def test_the_page_links_to_its_own_validation_record() -> None:
    """A page claiming its commands were executed must name where."""
    assert VALIDATION_RECORD.is_file()
    assert "v1-s2-008-pr1-validation.md" in DOCUMENT


def test_the_page_keeps_kubernetes_out_of_scope() -> None:
    """The exclusion is a decision, not an omission, and it is stated as one."""
    assert "Kubernetes is deliberately out of scope." in FLOWED


def test_the_page_states_that_its_executed_evidence_is_one_hosts() -> None:
    assert "observations from one Windows host, not supported-platform minima" in FLOWED
    assert "No second host has ever run this workflow." in FLOWED


def test_the_page_forbids_pasting_content_into_a_report() -> None:
    """The one instruction on the page that is a safety rule rather than advice."""
    assert "Never paste a prompt, a completion" in FLOWED


def test_the_page_carries_no_credential_shaped_value() -> None:
    """Nothing here needs one, so anything matching is a leak rather than a sample."""
    forbidden = re.compile(
        r"(?i)\b(?:hf_[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|"
        r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*\S+)"
    )
    assert not forbidden.findall(DOCUMENT), "credential-shaped value in the guide"


def test_the_page_does_not_promise_a_shutdown_endpoint() -> None:
    """ADR 0010 declined one; a troubleshooting page is where one gets invented."""
    assert "There is no shutdown endpoint" in FLOWED
