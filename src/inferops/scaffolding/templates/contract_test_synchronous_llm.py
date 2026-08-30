"""The test skeleton a generated `synchronous-llm` workload carries.

One template, held as text rather than as a file beside this module. Nothing
under ``src/inferops`` reads a path — that is an accepted architecture rule, and
it is what keeps this distribution usable from a wheel with no repository around
it — so the template travels as a module constant.

Rendered by :mod:`inferops.scaffolding.template`. Every placeholder below is a
:class:`string.Template` placeholder and must have a value in that module's
substitution mapping; a test asserts both directions, and a placeholder with no
value raises rather than surviving into generated output.
"""

from __future__ import annotations

from typing import Final

#: Where this template's output goes inside a generated workload.
OUTPUT_PATH: Final = "tests/test_workload_contract.py"

TEMPLATE: Final = '''
"""The contract this workload declares, read back and checked.

Generated from the InferOps workload template. It is a skeleton: it checks that
the document still says what this workload was generated to say, which is the
check that catches an edit nobody meant to make. Add the assertions that are
specific to what this workload does.

It reads one file in this directory's parent and nothing else. No network, no
cluster, no model, no clock, no randomness. **Nothing here starts a runtime or
loads a model**, so a green run says the document is intact and says nothing
about serving.

**What it does not do.** Parsing establishes that the document is well formed and
that its values satisfy their published formats. It does not apply the semantic
rules — the replica range, the compatibility matrix, the pasted-credential
heuristic — and it does not apply the JSON Schema. Those are the validator's, and
the command for it is in this workload's README. Run both.

Requires `pyyaml` and an importable `inferops` distribution.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from inferops.domain.workload import Profile, WorkloadContract, parse_workload_contract

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "workload.yaml"


def load_contract() -> WorkloadContract:
    document = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return parse_workload_contract(document)


def test_the_contract_parses_into_a_domain_object() -> None:
    assert load_contract() is not None


def test_the_workload_still_declares_the_identity_it_was_generated_with() -> None:
    contract = load_contract()
    assert str(contract.metadata.name) == "${name}"
    assert str(contract.metadata.owner) == "${owner}"
    assert str(contract.metadata.version) == "${version}"
    assert str(contract.metadata.description) == ${description_python}


def test_the_workload_still_declares_the_serving_shape_it_was_generated_with() -> None:
    contract = load_contract()
    assert contract.spec.profile is Profile.SYNCHRONOUS_LLM
    assert contract.spec.environment.value == "${environment}"
    assert contract.spec.model.serving_capability.value == "${serving_capability}"
    assert str(contract.spec.model.model_ref) == "${model_ref}"
    assert contract.spec.model.runtime_profile.value == "${runtime_profile}"


def test_the_workload_still_declares_the_resources_it_was_generated_with() -> None:
    contract = load_contract()
    assert str(contract.spec.resources.cpu) == "${cpu}"
    assert str(contract.spec.resources.memory) == "${memory}"
    assert contract.spec.resources.accelerator.type.value == "${accelerator_type}"
    assert contract.spec.resources.accelerator.count == ${accelerator_count}
    assert contract.spec.scaling.minimum_replicas == ${minimum_replicas}
    assert contract.spec.scaling.maximum_replicas == ${maximum_replicas}


def test_the_workload_is_still_attributed() -> None:
    contract = load_contract()
    assert str(contract.spec.attribution.tenant) == "${tenant}"
    assert str(contract.spec.attribution.cost_center) == "${cost_center}"


def test_the_bytes_this_workload_serves_are_still_the_pinned_ones() -> None:
    """A revision names what was published; a hash names what arrived.

    Both are asserted because either alone would let a different file through:
    an upstream revision can be repointed, and a hash on its own does not say
    where the bytes came from.
    """
    contract = load_contract()
    profile = contract.spec.synchronous_llm
    assert profile is not None
    assert str(profile.runtime.image_reference) == "${runtime_image_reference}"
    assert str(profile.model_artifact.repository) == "${model_repository}"
    assert str(profile.model_artifact.revision) == "${model_revision}"
    assert str(profile.model_artifact.file) == "${model_file}"
    assert profile.model_artifact.size_bytes == ${model_size_bytes}
    assert str(profile.model_artifact.sha256) == "${model_sha256}"


def test_this_workload_does_not_present_itself_as_a_mock() -> None:
    contract = load_contract()
    assert not contract.is_mock
    assert contract.spec.mock_llm is None


def test_this_workload_cites_only_evidence_it_has_produced() -> None:
    """A generated workload has executed nothing, so it cites nothing.

    Delete this test when this workload has a record of its own and
    ``evidence.proofRefs`` names it. Until then, a citation here would be
    another workload's result borrowed for this one.
    """
    contract = load_contract()
    assert not contract.spec.evidence.proof_refs
'''
