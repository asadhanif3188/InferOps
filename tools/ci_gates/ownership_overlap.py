"""No kind of object is both rendered by the chart and declared by Terraform.

    python -m tools.ci_gates.ownership_overlap --terraform infra/terraform \\
        charts/inferops-llm/ci/rendered/real.expected.yaml

The ownership inventory gives every cluster object exactly one owner, and the
two tools that create objects are Helm and Terraform. The architecture suites
already hold each tool to its half of that inventory. This is the same boundary
as a command: it reads a render and a Terraform configuration together and
refuses the pair when they reach across it, so a gate can apply it to whatever
it was handed rather than only to what a test file loads.

Three refusals, each a way two owners arrive:

* a render carries a kind the inventory gives to Terraform or to the Kubernetes
  control plane. A Helm test hook is exempt from the second - it exists for the
  length of `helm test` and the inventory deliberately gives it no row - and not
  from the first;
* the configuration declares a kind the inventory gives to Helm or to the
  control plane, or a resource type this check cannot place at all;
* a kind appears on both sides, whoever the inventory gives it to.

**It compares kinds, not names.** The inventory assigns kinds, and a chart that
rendered a second namespace under a different name would still be a chart
creating namespaces. Terraform is read as text - its resource blocks and their
types - so no provider is resolved, no state is read, and no cluster is
contacted. Exit status is 0 when nothing overlaps and 1 when anything does.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = (
    REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
)

HOOK_ANNOTATION = "helm.sh/hook"

#: The owners that write objects into a cluster, and the one that derives them.
HELM = "helm"
TERRAFORM = "terraform"
CONTROL_PLANE = "kubernetes-control-plane"

#: A Kubernetes kind, as the inventory writes it inside a free-text `kind` field:
#: `v1/Namespace`, `apps/v1 Deployment`, `platform service (Deployment, ...)`.
KIND_WORD = re.compile(r"\b[A-Z][A-Za-z]+\b")

#: A resource block, at any indent. The first version of the equivalent pattern
#: in the Terraform suite was anchored at column 0 and could not see an indented
#: block; this one is not.
RESOURCE_BLOCK = re.compile(
    r'^[ \t]*resource[ \t]+"(?P<type>[A-Za-z0-9_]+)"[ \t]+"[A-Za-z0-9_-]+"',
    re.MULTILINE,
)

#: `kubernetes_persistent_volume_claim_v1` -> `persistent_volume_claim`.
KUBERNETES_RESOURCE_TYPE = re.compile(r"^kubernetes_(?P<kind>[a-z_]+?)(?:_v[0-9]+)?$")


def kinds_by_owner(inventory: dict[str, Any]) -> dict[str, frozenset[str]]:
    """The Kubernetes kinds each owner holds, read out of the inventory."""
    owned: dict[str, set[str]] = {}
    for row in inventory["resources"]:
        owned.setdefault(row["owner"], set()).update(KIND_WORD.findall(row["kind"]))
    return {owner: frozenset(kinds) for owner, kinds in owned.items()}


def kind_of_terraform_type(resource_type: str) -> str | None:
    """The kind a `kubernetes_*` resource type creates, or None for any other."""
    matched = KUBERNETES_RESOURCE_TYPE.match(resource_type)
    if matched is None:
        return None
    return "".join(part.capitalize() for part in matched.group("kind").split("_"))


def terraform_resource_types(directory: Path) -> list[str]:
    """Every resource type declared under a configuration directory.

    Terraform's own working state is skipped: `.terraform/` holds downloaded
    modules and providers, and a module cached there is not a declaration.
    """
    found: list[str] = []
    for path in sorted(directory.rglob("*.tf")):
        if ".terraform" in path.relative_to(directory).parts:
            continue
        found += RESOURCE_BLOCK.findall(path.read_text(encoding="utf-8"))
    return found


def rendered_documents(paths: Iterable[Path]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        documents += [d for d in yaml.safe_load_all(text) if isinstance(d, dict)]
    return documents


def _is_hook(document: dict[str, Any]) -> bool:
    metadata = document.get("metadata")
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    return isinstance(annotations, dict) and HOOK_ANNOTATION in annotations


def problems(
    documents: list[dict[str, Any]],
    resource_types: list[str],
    inventory: dict[str, Any],
) -> list[str]:
    owners = kinds_by_owner(inventory)
    helm_kinds = owners.get(HELM, frozenset())
    terraform_kinds = owners.get(TERRAFORM, frozenset())
    derived_kinds = owners.get(CONTROL_PLANE, frozenset())

    found: list[str] = []
    rendered: set[str] = set()
    for document in documents:
        kind = str(document.get("kind"))
        name = (document.get("metadata") or {}).get("name")
        rendered.add(kind)
        if kind in terraform_kinds:
            found.append(
                f"the render carries {kind}/{name}, and the inventory gives "
                f"{kind} to Terraform"
            )
        elif kind in derived_kinds and not _is_hook(document):
            found.append(
                f"the render carries {kind}/{name}, and the inventory gives "
                f"{kind} to the Kubernetes control plane"
            )

    declared: set[str] = set()
    for resource_type in resource_types:
        placed = kind_of_terraform_type(resource_type)
        if placed is None:
            found.append(
                f"Terraform declares {resource_type}, which is not a Kubernetes "
                "resource this check can place in the inventory"
            )
            continue
        kind = placed
        declared.add(kind)
        if kind in helm_kinds:
            found.append(
                f"Terraform declares {resource_type}, and the inventory gives "
                f"{kind} to Helm"
            )
        elif kind in derived_kinds:
            found.append(
                f"Terraform declares {resource_type}, and the inventory gives "
                f"{kind} to the Kubernetes control plane"
            )
        elif kind not in terraform_kinds:
            found.append(
                f"Terraform declares {resource_type}, and the inventory gives "
                f"{kind} to no owner"
            )

    for kind in sorted(rendered & declared):
        found.append(f"{kind} is both rendered by the chart and declared by Terraform")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.ci_gates.ownership_overlap",
        description=(
            "Refuse a chart render and a Terraform configuration that reach "
            "across the ownership inventory's boundary between Helm and Terraform."
        ),
    )
    parser.add_argument(
        "--terraform",
        type=Path,
        required=True,
        help="a Terraform configuration directory, read as text",
    )
    parser.add_argument("renders", nargs="+", type=Path, help="rendered manifests")
    arguments = parser.parse_args(argv)

    if not arguments.terraform.is_dir():
        print(
            f"[inferops-ownership-overlap] FAILED: {arguments.terraform} is not a "
            "directory",
            file=sys.stderr,
        )
        return 1
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    documents = rendered_documents(arguments.renders)
    resource_types = terraform_resource_types(arguments.terraform)
    if not documents or not resource_types:
        # Nothing to compare is not the same as nothing overlapping.
        print(
            f"[inferops-ownership-overlap] FAILED: read {len(documents)} rendered "
            f"object(s) and {len(resource_types)} Terraform resource(s); both "
            "sides must be non-empty for an absence of overlap to mean anything",
            file=sys.stderr,
        )
        return 1

    found = problems(documents, resource_types, inventory)
    for line in found:
        print(f"[inferops-ownership-overlap] {line}")
    if found:
        print(
            f"[inferops-ownership-overlap] FAILED: {len(found)} ownership overlap(s)",
            file=sys.stderr,
        )
        return 1
    print(
        f"[inferops-ownership-overlap] {len(documents)} rendered object(s) and "
        f"{len(resource_types)} Terraform resource(s) share no kind and cross no "
        "owner",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
