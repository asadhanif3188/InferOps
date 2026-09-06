"""The V1 Kubernetes workload security policy, applied to parsed manifests.

What this module is, stated before what it does, because the distance between the
two sentences is the whole point of it existing:

**It reads YAML.** It parses a bundle of Kubernetes manifests -- a committed
render, a document under `deploy/`, whatever is handed to it -- and refuses one
that has dropped a control the security baseline says every InferOps workload
carries. It is an admission controller's checklist run over a file, by a process
with no cluster, no credential, and no way to stop anything being applied. A pod
running with a property this module would refuse is a pod this module will never
see.

That is worth having anyway, and the reason is `T-18`: a control gets written
down, and being written down is mistaken for being enforced. Six pod-security
properties held over this repository's manifests by convention until a test made
them a property. The same properties now hold over a rendering path, and the
same convention applies to it -- which is to say the same absence of one.

Every rule identifier below is a control identifier in
`docs/security/security-baseline.v1alpha1.json`, and a test compares the two
sets. A rule this module invents, or a control it silently stops applying, is a
failing test rather than a divergence somebody notices later.

A finding never quotes a value read out of the manifest. The rule is borrowed
from `tools/contract_validation/errors.py` and it is borrowed for the same
reason: the field most likely to hold something sensitive is the one that was
refused for looking wrong, and a refusal is the string most likely to be pasted
into a ticket.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Final

# --------------------------------------------------------------------------
# What a manifest is held to
# --------------------------------------------------------------------------

#: Pod-level fields, as dotted paths, and the value each must carry.
#:
#: Written out rather than imported from the security suite, which writes them
#: out rather than importing them from here. Two independent copies of a small
#: set is the arrangement that makes a weakening of one of them show up as a
#: disagreement instead of propagating.
REQUIRED_POD_FIELDS: Final[dict[str, object]] = {
    "automountServiceAccountToken": False,
    "securityContext.runAsNonRoot": True,
    "securityContext.seccompProfile.type": "RuntimeDefault",
}

#: Container-level fields, as dotted paths, and the value each must carry.
REQUIRED_CONTAINER_FIELDS: Final[dict[str, object]] = {
    "securityContext.allowPrivilegeEscalation": False,
    "securityContext.readOnlyRootFilesystem": True,
}

#: Service types that publish a socket outside the cluster. `ClusterIP` and an
#: absent type (which means `ClusterIP`) are the only two accepted.
EXTERNAL_SERVICE_TYPES: Final[frozenset[str]] = frozenset(
    {"NodePort", "LoadBalancer", "ExternalName"}
)

#: Kinds that carry a pod template and are therefore workloads for this policy.
WORKLOAD_KINDS: Final[frozenset[str]] = frozenset(
    {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "ReplicaSet", "Pod"}
)

#: An image reference pinned by digest. A tag is a label somebody can move; a
#: digest is what the engine resolves.
DIGEST_PINNED: Final[re.Pattern[str]] = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")

#: Environment variable names whose value is credential-shaped by name alone.
#: The check is on the *name carrying a literal*, never on the shape of the
#: value: a rule that matched value shapes would be a rule that reads secrets.
SECRET_NAME_HINT: Final[re.Pattern[str]] = re.compile(
    r"(?:^|_)(?:SECRET|PASSWORD|PASSWD|TOKEN|CREDENTIAL|APIKEY|API_KEY|PRIVATE_KEY)"
    r"(?:_|$)",
    flags=re.IGNORECASE,
)

#: The service account name every namespace already has. A workload naming it,
#: or naming none, is a workload sharing an identity with everything else in the
#: namespace.
DEFAULT_SERVICE_ACCOUNT: Final = "default"

#: The label that says an object belongs to an installed release, and its value.
#:
#: Two of the rules below apply to a release and not to the one-shot manifests
#: under `deploy/`, which are smoke and trial apparatus: a Job that runs once by
#: hand in a smoke namespace has no service to reach and nothing to reach it, and
#: giving it a dedicated identity and a policy pair would be four objects
#: defending a Job that exits. Every other rule applies to everything.
#:
#: **The scope is read off the manifest and is not a flag.** A caller cannot ask
#: for the lighter policy: a bundle is a release when something in it carries
#: this label, which the chart writes on every object it renders and a test
#: already holds it to. A workload that wanted the lighter treatment would have
#: to leave the release it is part of.
LIFECYCLE_LABEL: Final = "inferops.io/lifecycle"
RELEASE_LIFECYCLE: Final = "release"

#: The rules that apply only inside a release. The rest apply everywhere.
RELEASE_SCOPED_RULES: Final[frozenset[str]] = frozenset(
    {
        "use-a-dedicated-service-account-per-workload",
        "network-policy-in-the-release-namespace",
    }
)

#: One parsed YAML document. Keys are strings and values are whatever the
#: document held, which is the honest type for input nothing here controls.
Manifest = dict[str, Any]

ABSENT: Final = object()


@dataclass(frozen=True)
class Finding:
    """One refusal: which rule, which object, where, and why.

    `subject` locates the object inside the bundle and `field` locates the
    problem inside the object. Both are structural, and neither carries a value
    read out of the manifest.
    """

    rule: str
    subject: str
    field: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule,
            "subject": self.subject,
            "field": self.field,
            "message": self.message,
        }

    def __str__(self) -> str:  # pragma: no cover - exercised through the CLI
        return f"{self.rule}  {self.subject}  {self.field}  {self.message}"


# --------------------------------------------------------------------------
# Reading a bundle
# --------------------------------------------------------------------------


def _dig(node: object, dotted: str) -> Any:
    """Read a dotted path, or `ABSENT`.

    An absent field and a field set to `false` are different failures, and the
    sentinel is what keeps them different. `readOnlyRootFilesystem: false` is a
    decision somebody made; its absence is one nobody did.
    """
    current: object = node
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return ABSENT
        current = current[part]
    return current


def _subject(document: Manifest) -> str:
    kind = document.get("kind", "?")
    name = _dig(document, "metadata.name")
    return f"{kind}/{name if name is not ABSENT else '?'}"


def _pod_spec(document: Manifest) -> Manifest | None:
    """The pod specification inside a workload document, whatever wraps it."""
    if document.get("kind") == "Pod":
        spec = document.get("spec")
        return spec if isinstance(spec, dict) else None
    for dotted in ("spec.template.spec", "spec.jobTemplate.spec.template.spec"):
        spec = _dig(document, dotted)
        if isinstance(spec, dict):
            return spec
    return None


def _containers(spec: Manifest) -> Iterator[tuple[str, Manifest]]:
    """Every container in a pod specification, init and ephemeral included.

    An init container is a container. It runs with the pod's privileges before
    anything else does, which makes it the one most worth checking and the one
    most often left out of a checklist written from the `containers` key.
    """
    for key in ("initContainers", "containers", "ephemeralContainers"):
        for entry in spec.get(key) or []:
            if isinstance(entry, dict):
                yield f"{key}[{entry.get('name', '?')}]", entry


def _images(node: object, trail: str = "") -> Iterator[tuple[str, str]]:
    """Every `image` value anywhere in a document, however deeply nested."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "image" and isinstance(value, str):
                yield f"{trail}.{key}".lstrip("."), value
            else:
                yield from _images(value, f"{trail}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _images(value, f"{trail}[{index}]")


def is_release_bundle(documents: Sequence[Manifest]) -> bool:
    """Whether this bundle is an installed release rather than trial apparatus.

    Read off the objects rather than taken from the caller, so that the lighter
    policy is not something an invocation can ask for.
    """
    for document in documents:
        labels = _dig(document, "metadata.labels")
        if isinstance(labels, dict) and labels.get(LIFECYCLE_LABEL) == (
            RELEASE_LIFECYCLE
        ):
            return True
    return False


def _pod_labels(document: Manifest) -> dict[str, str]:
    """The labels the pods of a workload carry, which is what a policy selects.

    A NetworkPolicy selects pods, not workloads, so a policy is matched against
    the pod template's labels rather than against the Deployment's own.
    """
    if document.get("kind") == "Pod":
        labels = _dig(document, "metadata.labels")
    else:
        labels = _dig(document, "spec.template.metadata.labels")
    return labels if isinstance(labels, dict) else {}


def _selects(selector: object, labels: dict[str, str]) -> bool:
    """Whether a `podSelector` matches a pod carrying `labels`.

    Only `matchLabels` is understood, and `matchExpressions` is deliberately
    treated as *not matching*: a policy this module cannot fully evaluate is one
    it must not report as covering anything. Reporting an unparsed selector as a
    match is how a check comes to pass on a policy it did not read.
    """
    if not isinstance(selector, dict):
        return False
    if selector.get("matchExpressions"):
        return False
    match_labels = selector.get("matchLabels")
    if match_labels is None:
        # `podSelector: {}` selects every pod in the namespace.
        return not selector
    if not isinstance(match_labels, dict) or not match_labels:
        return not match_labels
    return all(labels.get(key) == value for key, value in match_labels.items())


def _denies_everything(policy: Manifest) -> tuple[bool, bool]:
    """Whether a policy denies all ingress and whether it denies all egress.

    A policy denies a direction when it declares that direction in
    `policyTypes` and supplies no rule for it. Declaring `Ingress` alone and
    writing no rules leaves **egress unrestricted**, which is the single easiest
    mistake to make in this object and the reason both halves are computed
    separately rather than as one boolean.
    """
    spec = policy.get("spec")
    if not isinstance(spec, dict):
        return False, False
    types = spec.get("policyTypes") or []
    denies_ingress = "Ingress" in types and not spec.get("ingress")
    denies_egress = "Egress" in types and not spec.get("egress")
    return denies_ingress, denies_egress


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------


def _check_pod_security(document: Manifest, spec: Manifest) -> Iterator[Finding]:
    subject = _subject(document)
    for dotted, expected in REQUIRED_POD_FIELDS.items():
        actual = _dig(spec, dotted)
        if actual == expected:
            continue
        rule = {
            "automountServiceAccountToken": "do-not-mount-a-service-account-token",
            "securityContext.runAsNonRoot": "run-as-non-root",
            "securityContext.seccompProfile.type": "seccomp-runtime-default",
        }[dotted]
        state = "is absent" if actual is ABSENT else "is not the required value"
        yield Finding(
            rule=rule,
            subject=subject,
            field=f"spec.{dotted}",
            message=f"the pod specification's {dotted} {state}",
        )
    if _dig(spec, "securityContext.runAsUser") is ABSENT:
        yield Finding(
            rule="run-as-non-root",
            subject=subject,
            field="spec.securityContext.runAsUser",
            message=(
                "runAsNonRoot is declared without a uid, which leaves the image "
                "to choose one"
            ),
        )


def _check_container_security(document: Manifest, spec: Manifest) -> Iterator[Finding]:
    subject = _subject(document)
    for where, container in _containers(spec):
        for dotted, expected in REQUIRED_CONTAINER_FIELDS.items():
            actual = _dig(container, dotted)
            if actual == expected:
                continue
            rule = {
                "securityContext.allowPrivilegeEscalation": (
                    "forbid-privilege-escalation"
                ),
                "securityContext.readOnlyRootFilesystem": "read-only-root-filesystem",
            }[dotted]
            state = "is absent" if actual is ABSENT else "is not the required value"
            yield Finding(
                rule=rule,
                subject=subject,
                field=f"{where}.{dotted}",
                message=f"the container's {dotted} {state}",
            )

        dropped = _dig(container, "securityContext.capabilities.drop")
        if not isinstance(dropped, list) or "ALL" not in dropped:
            yield Finding(
                rule="drop-all-capabilities",
                subject=subject,
                field=f"{where}.securityContext.capabilities.drop",
                message="the container does not drop ALL Linux capabilities",
            )
        added = _dig(container, "securityContext.capabilities.add")
        if isinstance(added, list) and added:
            yield Finding(
                rule="drop-all-capabilities",
                subject=subject,
                field=f"{where}.securityContext.capabilities.add",
                message=(
                    "the container adds a capability back after dropping ALL, "
                    "which is a grant rather than a default"
                ),
            )


def _check_resources(document: Manifest, spec: Manifest) -> Iterator[Finding]:
    """Both halves, on every container, and never one of them.

    A container with no request is scheduled anywhere; a container with no limit
    is bounded by nothing, and one serving runtime with no memory limit is the
    whole node. `T-10` is the threat and this is the only control in V1 that
    does anything about it: nothing here rate-limits a caller.
    """
    subject = _subject(document)
    for where, container in _containers(spec):
        for half in ("requests", "limits"):
            block = _dig(container, f"resources.{half}")
            if not isinstance(block, dict) or not block:
                yield Finding(
                    rule="declare-explicit-resource-requests-and-limits",
                    subject=subject,
                    field=f"{where}.resources.{half}",
                    message=f"the container states no resource {half}",
                )
                continue
            for dimension in ("cpu", "memory"):
                if dimension not in block:
                    yield Finding(
                        rule="declare-explicit-resource-requests-and-limits",
                        subject=subject,
                        field=f"{where}.resources.{half}.{dimension}",
                        message=f"the container's resource {half} omit {dimension}",
                    )


def _check_service_account(document: Manifest, spec: Manifest) -> Iterator[Finding]:
    subject = _subject(document)
    name = spec.get("serviceAccountName") or spec.get("serviceAccount")
    if not name:
        yield Finding(
            rule="use-a-dedicated-service-account-per-workload",
            subject=subject,
            field="spec.serviceAccountName",
            message=(
                "the pod specification names no service account, so it runs as "
                "the namespace's default identity"
            ),
        )
    elif name == DEFAULT_SERVICE_ACCOUNT:
        yield Finding(
            rule="use-a-dedicated-service-account-per-workload",
            subject=subject,
            field="spec.serviceAccountName",
            message=(
                "the pod specification names the namespace's default service "
                "account, which is shared with everything else in it"
            ),
        )


def _check_secret_references(document: Manifest, spec: Manifest) -> Iterator[Finding]:
    """A credential-shaped name reaching a container must arrive by reference.

    The check is on the **name carrying a literal**, and never on the shape of
    the value. A rule that matched value shapes would be a rule that reads
    secrets, and its findings would be the place they got published.
    """
    subject = _subject(document)
    for where, container in _containers(spec):
        for index, entry in enumerate(container.get("env") or []):
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            if not isinstance(name, str) or not SECRET_NAME_HINT.search(name):
                continue
            if "value" in entry:
                yield Finding(
                    rule="no-secret-value-in-a-rendered-manifest",
                    subject=subject,
                    field=f"{where}.env[{index}].value",
                    message=(
                        "a credential-shaped environment name carries a literal "
                        "value; secret material is referenced through "
                        "valueFrom.secretKeyRef and never rendered"
                    ),
                )


def _check_images(document: Manifest) -> Iterator[Finding]:
    subject = _subject(document)
    for where, image in _images(document):
        if not DIGEST_PINNED.match(image):
            yield Finding(
                rule="pin-image-by-digest",
                subject=subject,
                field=where,
                message=(
                    "the image reference is not pinned by digest; a tag is a "
                    "label somebody can move"
                ),
            )


def _check_exposure(document: Manifest) -> Iterator[Finding]:
    if document.get("kind") == "Service":
        service_type = _dig(document, "spec.type")
        if isinstance(service_type, str) and service_type in EXTERNAL_SERVICE_TYPES:
            yield Finding(
                rule="least-exposure-no-manifest-publishes-a-service",
                subject=_subject(document),
                field="spec.type",
                message=(
                    "the Service publishes a socket outside the cluster; V1 "
                    "reaches a workload by an explicit port-forward"
                ),
            )
        for index, port in enumerate(_dig(document, "spec.ports") or []):
            if isinstance(port, dict) and port.get("nodePort"):
                yield Finding(
                    rule="least-exposure-no-manifest-publishes-a-service",
                    subject=_subject(document),
                    field=f"spec.ports[{index}].nodePort",
                    message="the Service pins a node port",
                )
    if document.get("kind") == "Ingress":
        yield Finding(
            rule="least-exposure-no-manifest-publishes-a-service",
            subject=_subject(document),
            field="kind",
            message=(
                "an Ingress publishes a route into the cluster; V1 installs no "
                "ingress controller and reaches a workload by port-forward"
            ),
        )


def _check_network_policy(documents: Sequence[Manifest]) -> Iterator[Finding]:
    """Every workload in the bundle is covered by a default-deny policy.

    Covered means a NetworkPolicy in the bundle selects that workload's pods and
    denies **both** directions. The direction split matters: a policy declaring
    only `Ingress` leaves egress wide open while looking, in a diff, exactly like
    one that does not.

    What this cannot check is the thing that decides whether any of it happens:
    a NetworkPolicy is applied by the cluster's network plugin, and whether the
    accepted local cluster's plugin applies one has never been tested here. This
    rule refuses a bundle whose workloads are not *described* as denied. `DR-04`
    carries the rest and `EX-05` records it.
    """
    policies = [d for d in documents if d.get("kind") == "NetworkPolicy"]
    workloads = [
        d for d in documents if d.get("kind") in WORKLOAD_KINDS and _pod_spec(d)
    ]
    for workload in workloads:
        labels = _pod_labels(workload)
        ingress = egress = False
        for policy in policies:
            if not _selects(_dig(policy, "spec.podSelector"), labels):
                continue
            denies_ingress, denies_egress = _denies_everything(policy)
            ingress = ingress or denies_ingress
            egress = egress or denies_egress
        missing = [
            direction
            for direction, covered in (("ingress", ingress), ("egress", egress))
            if not covered
        ]
        if missing:
            yield Finding(
                rule="network-policy-in-the-release-namespace",
                subject=_subject(workload),
                field="spec.template.metadata.labels",
                message=(
                    "no NetworkPolicy in this bundle selects the workload's pods "
                    f"and denies {' and '.join(missing)} by default"
                ),
            )


# --------------------------------------------------------------------------
# The policy
# --------------------------------------------------------------------------

#: Every rule identifier this module can cite. It is also the set a test
#: compares against the security baseline's controls, in both directions.
RULE_IDS: Final[tuple[str, ...]] = (
    "run-as-non-root",
    "seccomp-runtime-default",
    "do-not-mount-a-service-account-token",
    "forbid-privilege-escalation",
    "read-only-root-filesystem",
    "drop-all-capabilities",
    "declare-explicit-resource-requests-and-limits",
    "use-a-dedicated-service-account-per-workload",
    "no-secret-value-in-a-rendered-manifest",
    "pin-image-by-digest",
    "least-exposure-no-manifest-publishes-a-service",
    "network-policy-in-the-release-namespace",
)


def check_documents(documents: Iterable[object]) -> list[Finding]:
    """Apply the whole policy to one bundle of parsed manifests.

    A bundle rather than a document, because one rule needs to see the whole set:
    whether a workload is denied by default is a property of the policy objects
    installed beside it, and a Deployment read on its own can never answer it.

    Findings are sorted so that two runs over the same input produce the same
    output, which is what makes the command usable as a gate and its output
    usable in a diff.
    """
    parsed = [d for d in documents if isinstance(d, dict) and d.get("kind")]
    findings: list[Finding] = []

    for document in parsed:
        findings.extend(_check_images(document))
        findings.extend(_check_exposure(document))
        spec = _pod_spec(document)
        if spec is None:
            continue
        findings.extend(_check_pod_security(document, spec))
        findings.extend(_check_container_security(document, spec))
        findings.extend(_check_resources(document, spec))
        findings.extend(_check_service_account(document, spec))
        findings.extend(_check_secret_references(document, spec))

    findings.extend(_check_network_policy(parsed))

    if not is_release_bundle(parsed):
        findings = [f for f in findings if f.rule not in RELEASE_SCOPED_RULES]

    return sorted(findings, key=lambda f: (f.subject, f.rule, f.field, f.message))
