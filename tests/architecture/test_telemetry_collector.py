"""The collector, and the configuration it is supposed to be able to load.

`V1-S3-007` rendered a Prometheus scrape configuration and a set of recording
rules into a ConfigMap. `V1-S3-007-PR2` wrote twenty-three queries against them
and checked those with a parser written for the purpose. Nothing anywhere read
any of it, and the Sprint 3 completion review recorded that as blocking: a sprint
that requires collection is not satisfied by configuration nothing consumes.
`ADR 0004` `D7` was amended to give the collector an owner, and this module covers
what that amendment produced.

Two kinds of check, and the second is the one that matters.

**Shape.** That the collector reads the ConfigMap the chart already renders
rather than a second copy of it; that it is granted a namespace-scoped permission
and no more; that its credentials are a projected, expiring token rather than an
automounted one; that its series are explicitly ephemeral. These are read off the
render.

**Loadability.** That the configuration the chart generates is one the pinned
collector will actually accept, checked by running that collector's own
`promtool` against the committed render. This is not a scrape and it is not a
query result: it establishes that the file loads, that the rule files resolve,
and that the nine recording rules parse. The distance between that and a
collected metric is a cluster, a release, and a running process -- none of which
this module has.

The check skips, loudly, where the collector image is not available locally. A
suite that quietly stopped verifying the one thing it added would be worse than
one that never claimed to.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
RENDERED = CHART_DIR / "ci" / "rendered" / "real.expected.yaml"
VALUES = yaml.safe_load((CHART_DIR / "values.yaml").read_text(encoding="utf-8"))
REAL_VALUES = yaml.safe_load(
    (CHART_DIR / "ci" / "real-values.yaml").read_text(encoding="utf-8")
)
INVENTORY = json.loads(
    (
        REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
    ).read_text(encoding="utf-8")
)

COLLECTOR_VALUES = VALUES["telemetry"]["collection"]["collector"]
IMAGE = (
    f"{COLLECTOR_VALUES['image']['repository']}@{COLLECTOR_VALUES['image']['digest']}"
)


def documents() -> list[dict]:
    return [d for d in yaml.safe_load_all(RENDERED.read_text(encoding="utf-8")) if d]


def by_component(kind: str) -> list[dict]:
    return [
        d
        for d in documents()
        if d.get("kind") == kind
        and (d.get("metadata", {}).get("labels") or {}).get(
            "app.kubernetes.io/component"
        )
        == "telemetry-collector"
    ]


# --------------------------------------------------------------------------
# What the amendment actually produced
# --------------------------------------------------------------------------


def test_the_inventory_row_is_owned_and_still_planned() -> None:
    """Owned answers "who"; planned answers "has it run". They are different."""
    row = next(
        r for r in INVENTORY["resources"] if r["resourceId"] == "telemetry-collector"
    )
    assert row["owner"] == "helm"
    assert row["lifecycle"] == "release"
    assert row["v1Status"] == "planned", (
        "a rendered collector is not an installed one, and evidenceRef stays null "
        "until a release has actually installed it"
    )
    assert row["evidenceRef"] is None

    backend = next(
        r for r in INVENTORY["resources"] if r["resourceId"] == "telemetry-backend"
    )
    assert backend["owner"] == "undecided" and backend["v1Status"] == "deferred", (
        "dashboards and alert routing are still undecided; only the collector was "
        "resolved"
    )


def test_the_shipped_default_installs_no_collector() -> None:
    """A release that quietly started a second workload would be deciding for its
    operator."""
    assert COLLECTOR_VALUES["deploy"] is False
    assert REAL_VALUES["telemetry"]["collection"]["collector"]["deploy"] is True


def test_the_collector_reads_the_configmap_the_chart_already_renders() -> None:
    """One release, one scrape configuration.

    Copying the jobs and rules into the collector's own file would give a release
    two of them, and the one that drifted would be whichever nobody read. So the
    collector's file is plumbing -- a global block, a rule reference, a scrape
    reference -- and the content comes from `telemetry-scrape-configuration`.
    """
    collector_config = by_component("ConfigMap")
    assert len(collector_config) == 1
    body = collector_config[0]["data"]["prometheus.yaml"]

    assert "scrape_config_files:" in body
    assert "rule_files:" in body
    assert "job_name" not in body, "the collector carries its own copy of the jobs"
    assert "record:" not in body, "the collector carries its own copy of the rules"

    scrape_map = next(
        d
        for d in documents()
        if d.get("kind") == "ConfigMap"
        and d["metadata"]["name"].endswith("-telemetry-scrape")
    )
    deployment = by_component("Deployment")[0]
    mounted = {
        (v.get("configMap") or {}).get("name")
        for v in deployment["spec"]["template"]["spec"]["volumes"]
    }
    assert scrape_map["metadata"]["name"] in mounted


def test_the_collector_asks_for_its_token_rather_than_being_handed_one() -> None:
    """Every pod here sets `automountServiceAccountToken: false`, and so does this
    one.

    Prometheus needs API credentials to discover targets, which is exactly the
    case an automount exists for. It projects them instead: a token with an
    expiry, the API server's CA, and the namespace, at the path the in-cluster
    client reads. The difference is that the pod states what it is given, and the
    token rotates.
    """
    spec = by_component("Deployment")[0]["spec"]["template"]["spec"]
    assert spec["automountServiceAccountToken"] is False

    projected = next(
        v["projected"] for v in spec["volumes"] if v["name"] == "kube-api-access"
    )
    kinds = {next(iter(source)) for source in projected["sources"]}
    assert kinds == {"serviceAccountToken", "configMap", "downwardAPI"}

    token = next(
        s["serviceAccountToken"]
        for s in projected["sources"]
        if "serviceAccountToken" in s
    )
    assert token["expirationSeconds"] <= 3600 * 2, (
        "a projected token whose expiry is long enough not to matter is an "
        "automounted token with extra steps"
    )

    mount = next(
        m
        for m in by_component("Deployment")[0]["spec"]["template"]["spec"][
            "containers"
        ][0]["volumeMounts"]
        if m["name"] == "kube-api-access"
    )
    assert mount["mountPath"] == "/var/run/secrets/kubernetes.io/serviceaccount"
    assert mount["readOnly"] is True


def test_the_collectors_storage_is_ephemeral_and_bounded() -> None:
    """The limitation this design accepts, asserted so it cannot be forgotten.

    Series live in the pod. A restart loses them. That is what makes this a
    collector for the release running now rather than a store anything may depend
    on, and it is why no PersistentVolumeClaim appears here: a second durable
    thing would have to be Terraform's, and that is a larger decision than making
    the scrape configuration do something.
    """
    spec = by_component("Deployment")[0]["spec"]["template"]["spec"]
    series = next(v for v in spec["volumes"] if v["name"] == "series")
    assert "emptyDir" in series, "the collector claims durable storage"
    assert series["emptyDir"]["sizeLimit"].endswith("Mi")

    args = " ".join(spec["containers"][0]["args"])
    assert "--storage.tsdb.retention.time=" in args
    assert "--storage.tsdb.retention.size=" in args, (
        "a retention window without a size bound can fill the volume it lives in"
    )
    # `--no-<flag>` and not `--<flag>=false`. Prometheus parses its command line
    # with kingpin, where a boolean flag takes no value: `=false` is read as a
    # positional argument and the process exits with `unexpected false` before it
    # opens a port, so every probe fails and the Deployment never becomes ready.
    # The rendered manifest is well-formed YAML either way, which is why only an
    # install could tell the two apart -- V1-S3-011's first one did.
    assert "--no-web.enable-lifecycle" in args, (
        "the lifecycle endpoint reloads configuration for anyone who can reach it"
    )
    assert "--no-web.enable-admin-api" in args, (
        "the admin API deletes series for anyone who can reach it"
    )
    assert "=false" not in args, (
        "a boolean passed as '=false' is rejected by Prometheus before it starts"
    )


# --------------------------------------------------------------------------
# Whether the pinned collector will actually load what the chart writes
# --------------------------------------------------------------------------

DOCKER = shutil.which("docker")


def _image_present() -> bool:
    if DOCKER is None:
        return False
    result = subprocess.run(
        [DOCKER, "image", "inspect", IMAGE],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return result.returncode == 0


needs_collector_image = pytest.mark.skipif(
    not _image_present(),
    reason=(
        "the pinned collector image is not present locally; the configuration is "
        "not checked against the engine that has to load it. Pull it to run this: "
        f"docker pull {IMAGE}"
    ),
)


@needs_collector_image
def test_the_pinned_collector_loads_the_configuration_the_chart_writes(
    tmp_path: Path,
) -> None:
    """`promtool check config`, from the image the chart pins, on the real render.

    The Sprint 3 review noted that a previous `promtool` run was supporting
    evidence rather than a scrape result, and that `promtool` was not installed
    at all on the reviewing host. This makes it a check rather than a claim: the
    binary comes from the same digest the collector runs, and the files come from
    the committed render.

    It establishes that the configuration loads, that `scrape_config_files`
    resolves the ConfigMap's own shape, and that the recording rules parse. It
    establishes nothing whatsoever about whether a target was discovered or a
    sample was taken.
    """
    assert DOCKER is not None
    collector_dir = tmp_path / "collector"
    telemetry_dir = tmp_path / "telemetry"
    collector_dir.mkdir()
    telemetry_dir.mkdir()

    config = by_component("ConfigMap")[0]["data"]["prometheus.yaml"]
    (collector_dir / "prometheus.yaml").write_text(
        config, encoding="utf-8", newline="\n"
    )
    scrape_map = next(
        d
        for d in documents()
        if d.get("kind") == "ConfigMap"
        and d["metadata"]["name"].endswith("-telemetry-scrape")
    )
    for key, value in scrape_map["data"].items():
        (telemetry_dir / key).write_text(value, encoding="utf-8", newline="\n")

    result = subprocess.run(
        [
            DOCKER,
            "run",
            "--rm",
            "-v",
            f"{collector_dir}:/etc/inferops/collector:ro",
            "-v",
            f"{telemetry_dir}:/etc/inferops/telemetry:ro",
            "--entrypoint",
            "/bin/promtool",
            IMAGE,
            "check",
            "config",
            "/etc/inferops/collector/prometheus.yaml",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env={**__import__("os").environ, "MSYS_NO_PATHCONV": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SUCCESS" in result.stdout
    assert "1 rule files found" in result.stdout


def test_the_release_test_may_reach_everything_it_asks() -> None:
    """The gap independent review found, closed and then held closed.

    The `helm test` pod gained a question for the collector and the policy that
    lets it out did not gain the port, because the egress rule was added to the
    platform API's policy instead -- where the API has no use for it, since the
    collector scrapes the API rather than the other way round. On the accepted
    cluster nothing enforces a NetworkPolicy, so it would have stayed invisible
    until somebody ran this on a cluster that does, and then `helm test` would
    have timed out against the collector.

    So this compares the two directly: every port the test pod's script names has
    to appear in the egress of the policy that selects it.
    """
    test_pod = next(
        d
        for d in documents()
        if d.get("kind") == "Pod"
        and (d["metadata"].get("labels") or {}).get("app.kubernetes.io/component")
        == "release-test"
    )
    script = " ".join(test_pod["spec"]["containers"][0]["args"])
    asked = {int(port) for port in re.findall(r":(\d{2,5})/", script)}
    assert asked, "the release test asks nothing"

    policy = next(
        d
        for d in documents()
        if d.get("kind") == "NetworkPolicy"
        and d["metadata"]["name"].endswith("-release-test")
    )
    opened = {
        port["port"]
        for rule in policy["spec"].get("egress") or []
        for port in rule.get("ports") or []
    }
    assert asked <= opened, {
        "the test pod asks these ports": sorted(asked),
        "its policy opens these": sorted(opened),
        "unreachable": sorted(asked - opened),
    }


def test_no_workload_is_given_egress_to_the_collector() -> None:
    """The collector scrapes the workloads; they do not call it.

    An egress allowance a pod never uses is a hole with no purpose, and this
    chart says so about the runtime's egress a few lines from where the rule was
    wrongly added.
    """
    port = COLLECTOR_VALUES["port"]
    for policy in (
        d
        for d in documents()
        if d.get("kind") == "NetworkPolicy"
        and (
            d["metadata"]["name"].endswith("-api")
            or d["metadata"]["name"].endswith("-runtime")
        )
    ):
        opened = {
            entry["port"]
            for rule in policy["spec"].get("egress") or []
            for entry in rule.get("ports") or []
        }
        assert port not in opened, (
            f"{policy['metadata']['name']} may call the collector, and has no reason to"
        )
