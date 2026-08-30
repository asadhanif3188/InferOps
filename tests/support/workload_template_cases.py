"""Representative parameter sets the workload template is rendered from.

Written once and imported, so that the rendering suite and the parameter suite
argue about the same inputs. Deliberately not named ``test_*``: it is imported,
never collected.

Each case is a parameter set a second engineer could plausibly type, and between
them they cover both profiles, every accelerator shape the schema permits with a
count, the two ends of the replica range, and each data classification the
template does not force. They are inputs, not fixtures of a document: what a case
renders to is asserted by the suite, never stored beside it.
"""

from __future__ import annotations

from inferops.scaffolding import WorkloadTemplateParameters

#: A minimal real workload: every required parameter supplied, every optional one
#: left at the default the repository has already decided.
MINIMAL_REAL = WorkloadTemplateParameters(
    name="support-assistant",
    owner="team-platform-demo",
    environment="local",
    profile="synchronous-llm",
    runtime_profile="resource-conscious",
    cpu="6",
    memory="3Gi",
    tenant="demo",
    cost_center="demo-cost-center",
    data_classification="internal",
    description="Answers support questions from the product knowledge base.",
)

#: A minimal mock workload. The name suffix, the environment, and the accelerator
#: are not free here: the mock-llm profile pins all three.
MINIMAL_MOCK = WorkloadTemplateParameters(
    name="support-assistant-mock",
    owner="team-platform-demo",
    environment="ci",
    profile="mock-llm",
    runtime_profile="resource-conscious",
    cpu="250m",
    memory="128Mi",
    tenant="demo",
    cost_center="demo-cost-center",
    data_classification="public",
    description="Deterministic contract-test double. Never evidence of real serving.",
)

#: A real workload that supplies every optional parameter explicitly, including
#: an accelerator and a replica range wider than one.
FULLY_SPECIFIED_REAL = WorkloadTemplateParameters(
    name="claims-triage-assistant",
    owner="team-claims",
    environment="staging",
    profile="synchronous-llm",
    runtime_profile="throughput-oriented",
    cpu="8",
    memory="16Gi",
    tenant="claims",
    cost_center="claims-platform",
    data_classification="confidential",
    description="Summarises a claim narrative for a human reviewer.",
    version="1.2.0",
    model_ref="qwen3-1-7b-q8-0",
    accelerator_type="nvidia-gpu",
    accelerator_count=1,
    minimum_replicas=2,
    maximum_replicas=6,
)

#: A mock workload with the widest replica range and the explicit model identity,
#: to prove the optional parameters behave the same under the pinned profile.
FULLY_SPECIFIED_MOCK = WorkloadTemplateParameters(
    name="claims-triage-assistant-mock",
    owner="team-claims",
    environment="ci",
    profile="mock-llm",
    runtime_profile="balanced",
    cpu="500m",
    memory="256Mi",
    tenant="claims",
    cost_center="claims-platform",
    data_classification="public",
    description="Replays the committed response fixture for the claims contract tests.",
    version="0.2.1",
    model_ref="mock-fixed-fixture",
    minimum_replicas=0,
    maximum_replicas=1,
)

#: Every case, in a stable order.
REPRESENTATIVE_CASES: tuple[WorkloadTemplateParameters, ...] = (
    MINIMAL_REAL,
    MINIMAL_MOCK,
    FULLY_SPECIFIED_REAL,
    FULLY_SPECIFIED_MOCK,
)

REAL_CASES: tuple[WorkloadTemplateParameters, ...] = (
    MINIMAL_REAL,
    FULLY_SPECIFIED_REAL,
)

MOCK_CASES: tuple[WorkloadTemplateParameters, ...] = (
    MINIMAL_MOCK,
    FULLY_SPECIFIED_MOCK,
)


def case_id(parameters: WorkloadTemplateParameters) -> str:
    """A readable test identifier for one case."""
    return parameters.name
