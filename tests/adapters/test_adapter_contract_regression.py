"""Every adapter this repository ships is held to the one conformance suite.

The shared suite in :mod:`tests.support.serving_conformance` is written once and
inherited, and two suites inherit it today: the committed mock in
``test_mock_serving_conformance.py`` and the adapter for the selected runtime in
``test_llama_server_adapter.py``, driven over a controlled transport. A third
inherits it under the unit layer, over the domain's own in-memory double.

Those three establish that the adapters that *are* covered satisfy the contract.
None of them establishes that every adapter is covered, and that is the failure
this module exists for: an adapter added without a conformance suite passes every
check in this repository, because the check that would have caught it is the one
nobody wrote. So this module discovers the implementations rather than listing
them, and fails when a discovered one has no suite.

It also compares two vocabularies that are written down in three places — the
adapter kinds the domain accepts, the kind each shipped adapter declares, and the
kinds the API's configuration-driven selection can compose — because a kind that
exists on one side and not another is a deployment that either cannot be composed
or cannot be labelled.

Nothing here constructs an adapter, opens a socket, or reads a runtime. It reads
this repository's own modules and its own test tree. The evidence class is `mock`
and it ceilings at `C1`.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

import inferops.adapters as adapters_package
from inferops.adapters import MOCK_ADAPTER_KIND
from inferops.adapters.llama_cpp.pins import LLAMA_SERVER_ADAPTER_KIND
from inferops.api import ADAPTER_KIND_FOR
from inferops.domain.serving import ACCEPTED_ADAPTER_KINDS, ServingAdapter

pytestmark = pytest.mark.adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"

#: The name of the shared conformance suite, as a subclass names it in a base
#: list. Matched textually because the suites are discovered without importing
#: them: importing a test module to inspect it runs its module-level code, and
#: what this check needs to know is a property of the source.
CONFORMANCE_BASE = "ServingAdapterConformance"

#: The adapter kind each shipped adapter declares, read from the constant the
#: adapter itself publishes rather than restated here. The mapping is asserted
#: exhaustive against the discovered set below, so an adapter added without an
#: entry fails rather than being skipped.
DECLARED_KIND: dict[str, str] = {
    "MockServingAdapter": MOCK_ADAPTER_KIND,
    "LlamaServerAdapter": LLAMA_SERVER_ADAPTER_KIND,
}


def protocol_members() -> frozenset[str]:
    """Every member :class:`ServingAdapter` publishes.

    Read from the protocol rather than listed, so that a method added to the
    interface widens what counts as an implementation here in the same change
    that adds it.
    """
    members = getattr(ServingAdapter, "__protocol_attrs__", None)
    assert members, "the serving adapter protocol publishes no members"
    return frozenset(members)


def shipped_adapters() -> dict[str, str]:
    """Every serving-adapter implementation under ``inferops.adapters``.

    Discovered by walking the package and keeping classes defined in the module
    being walked that carry every member the protocol publishes. Structural
    rather than nominal, because the protocol is a :class:`typing.Protocol` and
    an implementation does not inherit from it.
    """
    required = protocol_members()
    found: dict[str, str] = {}
    for module_info in pkgutil.walk_packages(
        adapters_package.__path__, f"{adapters_package.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for name, obj in vars(module).items():
            if not inspect.isclass(obj) or obj.__module__ != module_info.name:
                continue
            if required <= set(dir(obj)):
                found[name] = module_info.name
    return found


SHIPPED = shipped_adapters()


def conformance_suites() -> dict[str, set[str]]:
    """Every conformance subclass in the test tree, with the names it mentions.

    The value is the set of identifiers the module's source refers to, which is
    how a suite is attributed to the adapter it covers: a suite for an adapter
    has to name that adapter's class to construct it.
    """
    suites: dict[str, set[str]] = {}
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if CONFORMANCE_BASE not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        subclasses = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(
                isinstance(base, ast.Name) and base.id == CONFORMANCE_BASE
                for base in node.bases
            )
        ]
        if not subclasses:
            continue
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        suites[path.relative_to(REPO_ROOT).as_posix()] = names
    return suites


SUITES = conformance_suites()


# --------------------------------------------------------------------------
# Every adapter is discovered, and every discovered adapter is covered
# --------------------------------------------------------------------------


def test_the_shipped_adapters_are_the_two_the_architecture_names() -> None:
    """Discovery that finds nothing would make every check below vacuous.

    The adapters package documents exactly two implementations: the committed
    mock and the adapter for the runtime ADR 0002 selected. This asserts the
    discovery above agrees, so that a later failure means "an adapter has no
    suite" rather than "the walk stopped working".
    """
    assert set(SHIPPED) == {"MockServingAdapter", "LlamaServerAdapter"}, sorted(SHIPPED)


def test_a_conformance_suite_was_discovered() -> None:
    assert SUITES, (
        "no module in the test tree subclasses the shared conformance suite, so "
        "every attribution check below would pass without proving anything"
    )


def test_the_accepted_adapter_kinds_are_not_empty() -> None:
    """A check parametrised over an empty set collects nothing and reports green.

    Every kind check below is parametrised over the domain's own accepted set. It
    is a frozenset in the distribution rather than repository data, so it will not
    empty itself by accident — and an emptied one would silently retire three
    checks rather than fail one, which is the difference worth one assertion.
    """
    assert ACCEPTED_ADAPTER_KINDS, "the domain accepts no adapter kind"


@pytest.mark.parametrize("adapter", sorted(SHIPPED), ids=sorted(SHIPPED))
def test_every_shipped_adapter_is_held_to_the_shared_conformance_suite(
    adapter: str,
) -> None:
    """An adapter with no conformance suite is an adapter nothing holds to the contract.

    The suite is inherited rather than copied precisely so that "it implements
    the contract" means the contract. That argument only reaches an adapter
    somebody remembered to write a subclass for, and this is what makes
    remembering unnecessary.
    """
    covering = [module for module, names in SUITES.items() if adapter in names]
    assert covering, (
        f"{adapter} implements the serving adapter protocol and no module in the "
        f"test tree runs the shared conformance suite against it"
    )


def test_every_shipped_adapter_declares_a_kind_this_module_knows() -> None:
    """The kind table is exhaustive, checked in both directions.

    An adapter added without an entry would otherwise be silently exempt from
    every kind check below.
    """
    assert set(DECLARED_KIND) == set(SHIPPED), {
        "shipped and unmapped": sorted(set(SHIPPED) - set(DECLARED_KIND)),
        "mapped and not shipped": sorted(set(DECLARED_KIND) - set(SHIPPED)),
    }


# --------------------------------------------------------------------------
# One vocabulary of adapter kinds, written down in three places
# --------------------------------------------------------------------------


@pytest.mark.parametrize("adapter", sorted(DECLARED_KIND), ids=sorted(DECLARED_KIND))
def test_every_shipped_adapter_declares_an_accepted_kind(adapter: str) -> None:
    """A result declaring a kind the domain does not accept refuses itself.

    :class:`~inferops.domain.serving.InferenceResult` validates ``adapter_kind``
    at construction, so an adapter declaring an unaccepted kind fails on its
    first inference rather than at import. This is the earlier failure.
    """
    assert DECLARED_KIND[adapter] in ACCEPTED_ADAPTER_KINDS, DECLARED_KIND[adapter]


def test_every_accepted_kind_is_declared_by_a_shipped_adapter() -> None:
    """The other direction: a kind nothing declares is a kind nothing can produce.

    ``mock`` and ``real`` are the two the domain accepts, and the mock and real
    boundary is written in terms of both. A kind with no implementation behind
    it is a label a deployment could be composed with and never receive.
    """
    declared = set(DECLARED_KIND.values())
    assert set(ACCEPTED_ADAPTER_KINDS) == declared, {
        "accepted and undeclared": sorted(set(ACCEPTED_ADAPTER_KINDS) - declared),
        "declared and unaccepted": sorted(declared - set(ACCEPTED_ADAPTER_KINDS)),
    }


def test_the_api_composes_exactly_the_kinds_the_domain_accepts() -> None:
    """The third place the vocabulary is written down.

    ``inferops.api.selection`` reads which adapter a deployment serves out of
    configuration and maps the selection to an adapter kind. A selection mapping
    to a kind the domain does not accept composes a deployment whose every
    response is refused by the composition point it was built at.
    """
    composable = set(ADAPTER_KIND_FOR.values())
    assert composable == set(ACCEPTED_ADAPTER_KINDS), {
        "composable and unaccepted": sorted(composable - set(ACCEPTED_ADAPTER_KINDS)),
        "accepted and not composable": sorted(set(ACCEPTED_ADAPTER_KINDS) - composable),
    }


@pytest.mark.parametrize(
    "kind", sorted(ACCEPTED_ADAPTER_KINDS), ids=sorted(ACCEPTED_ADAPTER_KINDS)
)
def test_every_accepted_kind_has_an_adapter_running_the_conformance_suite(
    kind: str,
) -> None:
    """The story's criterion, as a property rather than as two suites that exist.

    "The common adapter suite runs against mock and real-adapter test doubles"
    is true today because two subclasses were written. This asserts it stays
    true for every kind the domain accepts, including one added later.
    """
    adapters_of_kind = [
        adapter
        for adapter, adapter_kind in DECLARED_KIND.items()
        if adapter_kind == kind
    ]
    assert adapters_of_kind, kind
    covered = [
        adapter
        for adapter in adapters_of_kind
        if any(adapter in names for names in SUITES.values())
    ]
    assert covered, (
        f"no adapter declaring kind '{kind}' is run through the shared "
        f"conformance suite; the adapters declaring it are {adapters_of_kind}"
    )


def test_the_real_adapter_conformance_suite_runs_against_a_controlled_transport() -> (
    None
):
    """A real-adapter suite in the default lane is a double, and says so.

    The default lane downloads no model and touches no cluster. The real
    adapter's conformance suite therefore runs over a transport the suite
    supplies, and what it establishes is the shape of the call rather than
    anything on the other end of it. The suite carries that limitation in its own
    docstring; this fails if the module stops constructing the adapter with a
    transport it controls.
    """
    module = TESTS_ROOT / "adapters" / "test_llama_server_adapter.py"
    source = module.read_text(encoding="utf-8")
    assert "ready_transport()" in source, module.name
    assert "LlamaServerAdapter(settings(), ready_transport())" in source, (
        "the real adapter's conformance suite no longer composes the adapter "
        "over a transport the suite controls"
    )
