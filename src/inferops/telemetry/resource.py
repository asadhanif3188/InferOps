"""What one emitting process is, stated once and attached to everything it emits.

The catalog splits these into two layers and this module keeps the split, because
the layers are not decoration: a resource attribute is attached once per process
and never varied per request, and a request attribute describes the piece of work.

:class:`ResourceAttributes` is the resource layer -- the component, its build, the
environment, the capability, the release, the pod, the model revision, the runtime
image digest, and the adapter kind this deployment was composed with.

:class:`WorkloadIdentity` is the workload this deployment serves. The catalog
classifies workload identity as a **request** attribute, and it is configuration
here for a reason worth stating plainly: **a workload identifier read out of a
caller's header would be an unbounded metric label**, and the catalog bounds it at
a deployment ceiling of twenty-five. One V1 deployment serves one workload, so the
value is constant per process, which is what makes the label bounded by
construction rather than by hoping callers behave. The integration specification
lists ``X-InferOps-Workload-ID`` among the headers an integration *should*
propagate; it also says a security-sensitive value is validated or injected by a
trusted component rather than believed because a client sent it. **This API reads
no workload header.**

**An unstated identity is empty, never invented.** A ``service.version`` of
``unknown`` sorts, groups, and reads like a release somebody shipped. The empty
string is what every metric store and query already treats as "not set", and a log
record omits the field entirely rather than writing a blank one.

**Every value is validated before it can become a label.** A label value is
written into the exposition between quotes, so a newline or a quote in one is an
injected series. The refusal happens at composition, where an operator who typed
the value is the one who reads the message.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..domain.serving.errors import InvalidAdapterConfigError
from . import names
from .registry import LABEL_VALUE, UNKNOWN

#: What this component is called wherever it emits. A singleton in the catalog:
#: one value per emitting process, and it names the component rather than the
#: deployment, so it is a constant here and not a variable an operator can set.
#: The name is the catalog's own emitter identifier for this process.
SERVICE_NAME = "inferops-api"

# -- the variables a deployment states its identity in ----------------------

#: The build of this component. Optional: a source checkout has no release.
ENV_SERVICE_VERSION = "INFEROPS_SERVICE_VERSION"

#: Which environment this deployment is. Optional, defaulting to ``dev``, which
#: is the one environment V1 has and the conservative default: a figure from a
#: laptop that defaulted to ``dev`` is never read as a figure from production.
ENV_DEPLOYMENT_ENVIRONMENT = "INFEROPS_DEPLOYMENT_ENVIRONMENT"

#: The registered platform capability this process serves.
ENV_CAPABILITY_ID = "INFEROPS_CAPABILITY_ID"

#: The release that installed this.
ENV_RELEASE_ID = "INFEROPS_RELEASE_ID"

#: The replica this process is, as Kubernetes names it. Supplied through the
#: downward API in a cluster and absent everywhere else.
ENV_POD_NAME = "INFEROPS_POD_NAME"

#: The immutable model revision behind this deployment, which a model identifier
#: alone does not pin.
ENV_MODEL_REVISION = "INFEROPS_MODEL_REVISION"

#: The runtime image, by digest rather than by a movable tag.
ENV_RUNTIME_IMAGE_DIGEST = "INFEROPS_RUNTIME_IMAGE_DIGEST"

#: The workload this deployment serves.
ENV_WORKLOAD_ID = "INFEROPS_WORKLOAD_ID"

#: The version of that workload's document.
ENV_WORKLOAD_VERSION = "INFEROPS_WORKLOAD_VERSION"

#: Who is accountable for that workload when it has to be turned off.
ENV_OWNER_ID = "INFEROPS_OWNER_ID"

#: Every variable this module reads. All of them are optional: a deployment that
#: states none of them still starts, still serves, and still emits -- with its
#: identity empty and visibly so, which is more useful than a process that
#: refuses to start because nobody set a release identifier.
TELEMETRY_ENVIRONMENT_VARIABLES: tuple[str, ...] = (
    ENV_SERVICE_VERSION,
    ENV_DEPLOYMENT_ENVIRONMENT,
    ENV_CAPABILITY_ID,
    ENV_RELEASE_ID,
    ENV_POD_NAME,
    ENV_MODEL_REVISION,
    ENV_RUNTIME_IMAGE_DIGEST,
    ENV_WORKLOAD_ID,
    ENV_WORKLOAD_VERSION,
    ENV_OWNER_ID,
)


@dataclass(frozen=True, slots=True)
class ResourceAttributes:
    """The resource layer: what this process is, for everything it emits.

    Every member is a string, and an unstated one is the empty string rather than
    ``None``, because these are published as label values and a store has no
    absent label. A log record drops the empty ones instead of writing them.
    """

    service_name: str = SERVICE_NAME
    service_version: str = UNKNOWN
    deployment_environment: str = names.ENVIRONMENT_DEV
    capability_id: str = UNKNOWN
    release_id: str = UNKNOWN
    pod_name: str = UNKNOWN
    model_revision: str = UNKNOWN
    runtime_image_digest: str = UNKNOWN
    adapter_kind: str = UNKNOWN

    def as_log_fields(self) -> dict[str, str]:
        """The resource attributes a log record carries, without the empty ones.

        ``k8s.pod.name`` is here and is not on any metric: it is unbounded, and a
        restarted pod is a new name, so a pod label grows a metric's series count
        once per restart forever.
        """
        return _present(
            {
                names.SERVICE_NAME: self.service_name,
                names.SERVICE_VERSION: self.service_version,
                names.DEPLOYMENT_ENVIRONMENT: self.deployment_environment,
                names.CAPABILITY_ID: self.capability_id,
                names.RELEASE_ID: self.release_id,
                names.POD_NAME: self.pod_name,
                names.MODEL_REVISION: self.model_revision,
                names.RUNTIME_IMAGE_DIGEST: self.runtime_image_digest,
                names.ADAPTER_KIND: self.adapter_kind,
            }
        )


@dataclass(frozen=True, slots=True)
class WorkloadIdentity:
    """The workload one deployment serves, from configuration and never a header.

    ``inferops.workload.id`` is a metric label and the other two are not. That is
    the catalog's decision and the reason is arithmetic: a workload version
    accumulates for as long as the workload exists, and an owner always varies
    with the workload it belongs to, so the second is a label that grows and the
    third is a label and a lookup wearing two names.
    """

    workload_id: str = UNKNOWN
    workload_version: str = UNKNOWN
    owner_id: str = UNKNOWN

    def as_log_fields(self) -> dict[str, str]:
        """The workload fields a log record carries, without the empty ones."""
        return _present(
            {
                names.WORKLOAD_ID: self.workload_id,
                names.WORKLOAD_VERSION: self.workload_version,
                names.OWNER_ID: self.owner_id,
            }
        )


def from_environment(
    environment: Mapping[str, str],
    *,
    adapter_kind: str = UNKNOWN,
) -> tuple[ResourceAttributes, WorkloadIdentity]:
    """Read one deployment's telemetry identity, or refuse it.

    Args:
        environment: The variables to read. A mapping rather than the process
            environment, so this is a function of its argument and a selection
            made in a test takes the same path as one made at startup.
        adapter_kind: The kind the deployment was composed with. It is passed in
            rather than read, because a second environment variable carrying that
            label would be a way to compose a real adapter and label it ``mock``
            -- which is the reason :mod:`inferops.api.selection` derives it from
            the selection in the first place.

    Raises:
        InvalidAdapterConfigError: If a stated value could not be a label value,
            or if the environment is outside the four the catalog bounds.
    """
    stated = _read(environment, ENV_DEPLOYMENT_ENVIRONMENT)
    if stated and stated not in names.ENVIRONMENTS:
        raise InvalidAdapterConfigError(
            ENV_DEPLOYMENT_ENVIRONMENT,
            f"must name one of {', '.join(names.ENVIRONMENTS)}",
        )
    resource = ResourceAttributes(
        service_name=SERVICE_NAME,
        service_version=_read(environment, ENV_SERVICE_VERSION),
        deployment_environment=stated or names.ENVIRONMENT_DEV,
        capability_id=_read(environment, ENV_CAPABILITY_ID),
        release_id=_read(environment, ENV_RELEASE_ID),
        pod_name=_read(environment, ENV_POD_NAME),
        model_revision=_read(environment, ENV_MODEL_REVISION),
        runtime_image_digest=_read(environment, ENV_RUNTIME_IMAGE_DIGEST),
        adapter_kind=adapter_kind,
    )
    workload = WorkloadIdentity(
        workload_id=_read(environment, ENV_WORKLOAD_ID),
        workload_version=_read(environment, ENV_WORKLOAD_VERSION),
        owner_id=_read(environment, ENV_OWNER_ID),
    )
    return resource, workload


def _read(environment: Mapping[str, str], name: str) -> str:
    """One optional variable, validated as a label value or refused.

    An absent or blank variable is an unstated identity and is returned empty. A
    stated one has to be usable where it is going, and where it is going is
    between quotes in a metrics exposition -- so it is checked here, naming the
    variable and never repeating the value, which is the same division of labour
    every other refusal in this distribution uses.
    """
    value = environment.get(name, "").strip()
    if not value:
        return UNKNOWN
    if LABEL_VALUE.match(value) is None:
        raise InvalidAdapterConfigError(
            name,
            "must be at most 128 characters of letters, digits, and "
            ". _ : / @ + -, starting with a letter or a digit",
        )
    return value


def _present(fields: Mapping[str, str]) -> dict[str, str]:
    return {name: value for name, value in fields.items() if value}
