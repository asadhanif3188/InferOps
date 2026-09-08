"""The Kubernetes telemetry collection record, and the render it describes.

Four files have to agree, and the point of the suite is that no two of them are
allowed to drift:

- `docs/telemetry/kubernetes-telemetry-collection.v1alpha1.json`, the record;
- `docs/telemetry/kubernetes-telemetry-collection.md`, the document that publishes
  it in prose;
- the committed chart renders, which are what a cluster would actually be given;
- `docs/telemetry/telemetry-catalog.v1alpha1.json`, which decides where a value is
  allowed to go and is never restated here, only derived from.

The property this defends is the catalog's own, one layer further out. The catalog
stops an emitter putting a tenant identifier, a request identifier, a pod name, or a
measured duration on a metric label. A collector can put one there afterwards, from
the outside, with the emitter none the wiser -- so the same derivation is applied to
the scrape configuration, and the drop list is recomputed from the catalog on every
run rather than copied into it.

**None of this establishes that anything is collected.** No collector, store,
dashboard, or alerting path is selected, nothing scrapes either InferOps endpoint,
and this chart has never been installed. Every check here reads a file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.telemetry_collection import (
    RULE_IDS,
    SAFE_MESSAGE_CHARACTERS,
    check_documents,
    emitted_metric_names,
    forbidden_metric_labels,
    is_scrape_config_map,
    observed_native_series,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

RECORD_PATH = REPO_ROOT / "docs/telemetry/kubernetes-telemetry-collection.v1alpha1.json"
DOCUMENT_PATH = REPO_ROOT / "docs/telemetry/kubernetes-telemetry-collection.md"
CATALOG_PATH = REPO_ROOT / "docs/telemetry/telemetry-catalog.v1alpha1.json"
HELPERS_PATH = REPO_ROOT / "charts/inferops-llm/templates/_helpers.tpl"
RENDERED_DIR = REPO_ROOT / "charts/inferops-llm/ci/rendered"

RECORD: dict[str, Any] = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
DOCUMENT = DOCUMENT_PATH.read_text(encoding="utf-8")
CATALOG: dict[str, Any] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
HELPERS = HELPERS_PATH.read_text(encoding="utf-8")

PROFILES = ("mock", "real")

#: The release name and namespace the committed renders are produced with. Both are
#: part of the rendered output, so they are constants of the fixture rather than
#: choices this suite makes.
RELEASE_FULLNAME = "inferops-inferops-llm"
RELEASE_NAMESPACE = "inferops-platform"


def job_name(suffix: str) -> str:
    """A job name as the committed renders spell it."""
    return f"{RELEASE_FULLNAME}-{suffix}"


RENDERED: dict[str, list[dict[str, Any]]] = {
    profile: [
        document
        for document in yaml.safe_load_all(
            (RENDERED_DIR / f"{profile}.expected.yaml").read_text(encoding="utf-8")
        )
        if document
    ]
    for profile in PROFILES
}

ATTRIBUTE_BY_PROMETHEUS_NAME = {
    attribute["name"].replace(".", "_"): attribute
    for attribute in CATALOG["attributes"]
}
CARDINALITY_CLASS_IDS = {row["classId"] for row in CATALOG["cardinalityClasses"]}
METRIC_BY_NAME = {metric["name"]: metric for metric in CATALOG["metrics"]}


def scrape_config_map(profile: str) -> dict[str, Any]:
    """The one telemetry scrape ConfigMap in a committed render."""
    found = [d for d in RENDERED[profile] if is_scrape_config_map(d)]
    assert len(found) == 1, (
        f"the {profile} render holds {len(found)} telemetry scrape ConfigMaps, and "
        "exactly one is the whole of the design: two would be two sources of truth "
        "for one collection"
    )
    return found[0]


def scrape_jobs(profile: str) -> dict[str, dict[str, Any]]:
    data = scrape_config_map(profile)["data"]["scrape-config.yaml"]
    return {job["job_name"]: job for job in yaml.safe_load(data)["scrape_configs"]}


def recording_groups(profile: str) -> dict[str, list[dict[str, Any]]]:
    data = scrape_config_map(profile)["data"]["recording-rules.yaml"]
    return {group["name"]: group["rules"] for group in yaml.safe_load(data)["groups"]}


def target_labels(job: dict[str, Any]) -> set[str]:
    return {
        rule["target_label"]
        for rule in job.get("relabel_configs", [])
        if "target_label" in rule
    }


# --------------------------------------------------------------------------
# The suite read something
# --------------------------------------------------------------------------


def test_the_record_the_document_and_both_renders_were_found() -> None:
    """Guard against a suite that passes because every collection is empty."""
    assert RECORD_PATH.is_file()
    assert DOCUMENT_PATH.is_file()
    assert len(RECORD["jobs"]) == 2
    assert len(RECORD["targetLabels"]) >= 7
    assert len(DOCUMENT) > 4000
    for profile in PROFILES:
        assert len(RENDERED[profile]) > 5


# --------------------------------------------------------------------------
# The record does not claim a collection that does not happen
# --------------------------------------------------------------------------


def test_the_record_states_that_nothing_collects() -> None:
    """The one sentence this whole record would be dishonest without.

    Configuration for a collector and a collector are different things, and a
    document describing the first in the present tense is how the second gets
    assumed. `collected` is a boolean rather than prose so that it cannot be
    softened by editing a paragraph.
    """
    status = RECORD["collectionStatus"]
    assert status["collected"] is False
    assert status["everInstalled"] is False
    assert status["configurationRendered"] is True
    assert "not selected" in status["collector"]
    assert "nothing scrapes" in status["note"].lower()
    assert "**Nothing reads this ConfigMap, nothing scrapes either endpoint" in DOCUMENT


def test_every_reference_the_record_makes_resolves() -> None:
    """A record whose references have rotted is a record nobody can check."""
    for key, value in RECORD.items():
        if key.endswith("Ref") and isinstance(value, str):
            assert (REPO_ROOT / value).exists(), f"{key} names a path that is not there"
    for value in RECORD["renderedRefs"]:
        assert (REPO_ROOT / value).is_file()


def test_the_record_and_the_document_name_the_same_jobs_labels_and_rules() -> None:
    """Neither file may publish a name the other has never heard of."""
    for job in RECORD["jobs"]:
        assert job["jobName"] in DOCUMENT
        assert job["whyJobNameIsReleaseScoped"]
    for label in RECORD["targetLabels"]:
        assert f"`{label['labelName']}`" in DOCUMENT
    for rule in RECORD["runtimeMetricMapping"]["rules"]:
        assert rule["record"] in DOCUMENT
        for series in rule["nativeSeries"]:
            assert series in DOCUMENT
    for rule in RECORD["missingSignalVisibility"]:
        assert rule["record"] in DOCUMENT
    for limitation in RECORD["limitations"]:
        assert limitation["limitationId"]
        assert limitation["statement"].endswith(".")


# --------------------------------------------------------------------------
# The drop list is derived from the catalog, not copied from it
# --------------------------------------------------------------------------


def test_the_charts_drop_list_is_exactly_what_the_catalog_derives() -> None:
    """The chart may not decide what a metric label is allowed to be.

    A copied list is a list that is right on the day it is written. This one is
    recomputed from the catalog every run, so an attribute whose placement changes
    there fails here rather than silently reaching a store.
    """
    body = HELPERS.split('{{- define "inferops-llm.forbiddenMetricLabels" -}}')[1]
    rendered = body.split("{{- end -}}")[0].strip()
    assert set(rendered.split("|")) == forbidden_metric_labels()


def test_the_record_publishes_the_same_drop_list() -> None:
    assert set(RECORD["droppedMetricLabels"]["labels"]) == forbidden_metric_labels()


@pytest.mark.parametrize("label", sorted(forbidden_metric_labels()))
def test_the_document_publishes_every_dropped_label(label: str) -> None:
    assert label in DOCUMENT


@pytest.mark.parametrize("profile", PROFILES)
def test_every_job_drops_every_label_the_catalog_bars(profile: str) -> None:
    forbidden = forbidden_metric_labels()
    for name, job in scrape_jobs(profile).items():
        dropped: set[str] = set()
        for rule in job.get("metric_relabel_configs", []):
            if rule.get("action") == "labeldrop":
                dropped.update(rule["regex"].strip("()").split("|"))
        assert forbidden <= dropped, (
            f"{profile}/{name} does not drop {forbidden - dropped}"
        )


@pytest.mark.parametrize("profile", PROFILES)
def test_no_job_attaches_a_label_the_catalog_bars_from_a_metric(profile: str) -> None:
    """The rule this suite exists for.

    The catalog stops an emitter placing these. Nothing stopped a collector placing
    them from the outside until this did.
    """
    forbidden = forbidden_metric_labels()
    for name, job in scrape_jobs(profile).items():
        offending = target_labels(job) & forbidden
        assert not offending, f"{profile}/{name} attaches {sorted(offending)}"


# --------------------------------------------------------------------------
# The collector never restates what the emitter already publishes
# --------------------------------------------------------------------------


def test_the_api_job_attaches_no_label_the_api_already_emits() -> None:
    """`honor_labels` is false, so a duplicate target label is a silent rename.

    Prometheus keeps the target's value and renames the emitter's to `exported_*`.
    Every query written against the emitter's label then reads a label that is no
    longer there, which is a worse outcome than the missing dimension the duplicate
    was added to supply.
    """
    attribute_by_id = {row["attributeId"]: row for row in CATALOG["attributes"]}
    emitted_labels = {
        attribute_by_id[label_id]["name"].replace(".", "_")
        for metric in CATALOG["metrics"]
        if metric.get("emission") == "emitted"
        for label_id in metric["labels"]
    }
    assert emitted_labels, "the catalog declares no emitted metric label to compare"
    for profile in PROFILES:
        job = scrape_jobs(profile)[job_name("platform-api")]
        assert job["honor_labels"] is False
        collision = target_labels(job) & emitted_labels
        assert not collision, f"{profile} API job would rename {sorted(collision)}"


@pytest.mark.parametrize("profile", PROFILES)
def test_the_rendered_jobs_are_the_ones_the_record_declares(profile: str) -> None:
    declared = {
        job_name(job["jobNameSuffix"])
        for job in RECORD["jobs"]
        if profile in job["profiles"]
    }
    assert set(scrape_jobs(profile)) == declared


@pytest.mark.parametrize("profile", PROFILES)
def test_every_job_name_is_scoped_to_the_release(profile: str) -> None:
    """Prometheus refuses two scrape_configs entries sharing a job_name.

    This fragment is meant to be merged into a collector's existing
    configuration, so two releases of this chart installed beside each other --
    the case every `keep` filter here exists to distinguish -- would render two
    fragments that could not be merged at all if the names were constants.
    """
    rendered = scrape_jobs(profile)
    for name in rendered:
        assert name.startswith(f"{RELEASE_FULLNAME}-"), name
    assert len(set(rendered)) == len(rendered)


@pytest.mark.parametrize("profile", PROFILES)
def test_the_rendered_target_labels_are_the_ones_the_record_declares(
    profile: str,
) -> None:
    for job in RECORD["jobs"]:
        if profile not in job["profiles"]:
            continue
        rendered = scrape_jobs(profile)[job_name(job["jobNameSuffix"])]
        assert target_labels(rendered) == set(job["attachedTargetLabels"])


def test_nothing_the_record_says_is_not_attached_is_attached() -> None:
    for profile in PROFILES:
        for job in RECORD["jobs"]:
            if profile not in job["profiles"]:
                continue
            rendered = scrape_jobs(profile)[job_name(job["jobNameSuffix"])]
            assert not target_labels(rendered) & set(job["deliberatelyNotAttached"])


# --------------------------------------------------------------------------
# Every label declares what it costs
# --------------------------------------------------------------------------


def test_every_target_label_declares_a_cardinality_class_the_catalog_knows() -> None:
    for label in RECORD["targetLabels"]:
        assert label["cardinality"] in CARDINALITY_CLASS_IDS
        assert label["reason"]


def test_instance_is_the_only_unbounded_label_and_says_what_it_costs() -> None:
    """An unbounded label is allowed here and must be argued for, once.

    Prometheus requires a per-target identity, so this one cannot be removed. That
    is a reason to state its cost, not a reason to stop counting it -- and the
    rejected alternative is recorded so that the next reader does not have to
    rediscover why the cheap option was refused.
    """
    unbounded = [
        label for label in RECORD["targetLabels"] if label["cardinality"] == "unbounded"
    ]
    assert [label["labelName"] for label in unbounded] == ["instance"]
    assert unbounded[0]["cost"]
    assert unbounded[0]["rejectedAlternative"]


def test_a_bounded_target_label_stays_inside_its_classs_bound() -> None:
    bound_by_class = {
        row["classId"]: row["maxDistinctValues"]
        for row in CATALOG["cardinalityClasses"]
    }
    for label in RECORD["targetLabels"]:
        declared = label["maxDistinctValues"]
        if declared is None:
            assert label["cardinality"] == "unbounded"
            continue
        assert declared <= bound_by_class[label["cardinality"]]


def test_a_target_label_borrowed_from_the_catalog_keeps_the_catalogs_bound() -> None:
    """A collector may not widen an attribute's declared cardinality by relabelling."""
    for label in RECORD["targetLabels"]:
        attribute_id = label["catalogAttributeId"]
        if attribute_id is None:
            continue
        attribute = next(
            row for row in CATALOG["attributes"] if row["attributeId"] == attribute_id
        )
        assert label["labelName"] == attribute["name"].replace(".", "_")
        assert label["cardinality"] == attribute["cardinality"]
        assert label["maxDistinctValues"] == attribute["maxDistinctValues"]
        assert "metric-label" in attribute["placements"]


def test_the_series_multiplier_is_the_arithmetic_it_claims_to_be() -> None:
    """A budget nobody recomputes is a budget nobody is counting."""
    multiplier = RECORD["seriesMultiplier"]
    active = [m for m in CATALOG["metrics"] if m["v1Status"] != "deferred"]
    emitted = [m for m in CATALOG["metrics"] if m.get("emission") == "emitted"]
    assert multiplier["declaredActiveBudget"] == sum(m["maxSeries"] for m in active)
    assert multiplier["declaredEmittedBudget"] == sum(m["maxSeries"] for m in emitted)
    assert multiplier["apiJobCeilingPerTarget"] == multiplier["declaredEmittedBudget"]
    assert multiplier["apiJobCeilingTwoReplicas"] == (
        2 * multiplier["apiJobCeilingPerTarget"]
    )
    assert f"{multiplier['apiJobCeilingPerTarget']:,}" in DOCUMENT
    assert f"{multiplier['apiJobCeilingTwoReplicas']:,}" in DOCUMENT


# --------------------------------------------------------------------------
# The runtime mapping maps series that were measured
# --------------------------------------------------------------------------


def test_every_mapped_native_series_was_actually_observed() -> None:
    """A mapping table is the easiest place to publish a series that does not exist."""
    observed = observed_native_series()
    mapping = RECORD["runtimeMetricMapping"]
    for rule in mapping["rules"]:
        assert set(rule["nativeSeries"]) <= observed
    assert set(mapping["unmappedNativeSeries"]) <= observed


def test_the_mapped_and_the_unmapped_together_are_every_observed_series() -> None:
    """Neither a silent omission nor a silent addition."""
    mapping = RECORD["runtimeMetricMapping"]
    mapped = {s for rule in mapping["rules"] for s in rule["nativeSeries"]}
    assert mapped | set(mapping["unmappedNativeSeries"]) == observed_native_series()
    assert not mapped & set(mapping["unmappedNativeSeries"])


def test_every_mapping_names_a_catalog_concept_and_states_its_completeness() -> None:
    for rule in RECORD["runtimeMetricMapping"]["rules"]:
        assert rule["catalogConcept"] in METRIC_BY_NAME
        assert rule["completeness"] in ("complete", "partial")
        if rule["completeness"] == "partial":
            assert rule["note"], "a partial mapping has to say what is missing"


def test_no_recorded_name_could_collide_with_a_metric_the_catalog_declares() -> None:
    """`inferops:` with a colon, never `inferops_` with an underscore."""
    declared = emitted_metric_names()
    recorded = [rule["record"] for rule in RECORD["runtimeMetricMapping"]["rules"]]
    recorded += [rule["record"] for rule in RECORD["missingSignalVisibility"]]
    for name in recorded:
        assert name.startswith("inferops:"), name
        assert name not in declared


def test_the_rendered_recording_rules_are_the_ones_the_record_declares() -> None:
    declared = {rule["record"] for rule in RECORD["runtimeMetricMapping"]["rules"]}
    declared |= {
        rule["record"]
        for rule in RECORD["missingSignalVisibility"]
        if "real" in rule.get("profiles", ["mock", "real"])
    }
    rendered = {
        rule["record"] for rules in recording_groups("real").values() for rule in rules
    }
    assert rendered == declared


# --------------------------------------------------------------------------
# Absence is visible
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile", PROFILES)
def test_every_scrape_job_has_a_rule_that_makes_its_absence_visible(
    profile: str,
) -> None:
    """A job that matched nothing produces no `up` series to be zero.

    Every query grouping by that job then returns an empty result, and an empty
    result is indistinguishable from a healthy quiet system. `absent()` is the only
    thing that separates them.
    """
    expressions = [
        rule["expr"] for rules in recording_groups(profile).values() for rule in rules
    ]
    for name in scrape_jobs(profile):
        assert any(f'absent(up{{job="{name}"}})' in expr for expr in expressions), (
            f"{profile}/{name} has no absence rule"
        )


def test_the_absence_of_model_readiness_is_published_rather_than_averaged() -> None:
    """The rule that reads 1 today, and says so.

    `inferops_model_ready` is declared, assigned to the serving-runtime adapter, and
    not emitted. A rule that averaged it would publish an empty series, which reads
    as a healthy system rather than an absent one.
    """
    assert METRIC_BY_NAME["inferops_model_ready"]["emission"] != "emitted"
    rule = next(
        row
        for row in RECORD["missingSignalVisibility"]
        if row["record"] == "inferops:model_ready_absent:platform_api"
    )
    assert rule["expression"].startswith("absent(inferops_model_ready{")
    assert 'k8s_component="platform-api"' in rule["expression"]
    assert rule["readsToday"].startswith("1,")


def test_no_missing_signal_rule_claims_anything_evaluates_it() -> None:
    for rule in RECORD["missingSignalVisibility"]:
        if rule["record"] == "inferops:model_ready_absent:platform_api":
            continue
        assert "no collector evaluates it" in rule["readsToday"]


def test_every_unavailable_catalog_metric_is_one_the_catalog_says_is_not_emitted() -> (
    None
):
    """The record may not report a signal as missing that is in fact published."""
    for signal in RECORD["unavailableSignals"]:
        if signal["kind"] != "catalog metric":
            continue
        assert METRIC_BY_NAME[signal["signal"]]["emission"] != "emitted"
        assert signal["wouldRequire"]


# --------------------------------------------------------------------------
# The chart's derived identifiers match the code they mirror
# --------------------------------------------------------------------------


def test_the_charts_runtime_identifier_matches_the_adapters() -> None:
    """One identifier, in two files, compared rather than trusted."""
    from inferops.adapters.llama_cpp.pins import LLAMA_SERVER_RUNTIME_ID
    from inferops.adapters.mock_serving import MOCK_RUNTIME_ID

    body = HELPERS.split('{{- define "inferops-llm.runtimeId" -}}')[1]
    body = body.split("{{- end -}}")[0]
    assert LLAMA_SERVER_RUNTIME_ID in body
    assert MOCK_RUNTIME_ID in body

    real_job = scrape_jobs("real")[job_name("serving-runtime")]
    supplied = {
        rule["target_label"]: rule["replacement"]
        for rule in real_job["relabel_configs"]
        if "replacement" in rule
    }
    assert supplied["inferops_runtime_id"] == LLAMA_SERVER_RUNTIME_ID


# --------------------------------------------------------------------------
# The checker
# --------------------------------------------------------------------------


def test_the_committed_renders_satisfy_the_collection_policy() -> None:
    for profile in PROFILES:
        assert check_documents(RENDERED[profile]) == []


def test_a_config_map_that_is_not_the_scrape_configuration_is_left_alone() -> None:
    """The checker reads a bundle and answers for one object in it.

    A release that switched collection off renders no such object at all, which is a
    supported installation and reaches this same path;
    `tests/architecture/test_helm_chart.py` drives the switch itself, because that
    needs a render rather than a fixture.
    """
    assert check_documents([{"kind": "ConfigMap", "metadata": {"name": "x"}}]) == []
    assert check_documents([]) == []


def _tampered_config_map(scrape: object, rules: object) -> dict[str, Any]:
    return {
        "kind": "ConfigMap",
        "metadata": {
            "name": "hostile",
            "labels": {"app.kubernetes.io/component": "telemetry-scrape-configuration"},
        },
        "data": {"scrape-config.yaml": scrape, "recording-rules.yaml": rules},
    }


def test_a_key_that_is_not_yaml_is_refused_rather_than_skipped() -> None:
    """A configuration nothing can parse is not a configuration that passed.

    Skipping it would leave every other rule vacuously satisfied by a key nobody
    could read, and raising would break the exit status and the JSON report this
    checker promises.
    """
    findings = check_documents([_tampered_config_map("[unclosed", ": : :")])
    assert {finding.rule for finding in findings} == {
        "configuration-is-not-readable-yaml"
    }
    assert {finding.field for finding in findings} == {
        "scrape-config.yaml",
        "recording-rules.yaml",
    }


@pytest.mark.parametrize(
    "hostile",
    [
        "target label",
        "native series",
        "job name",
        "record name",
    ],
)
def test_no_finding_message_can_carry_a_value_out_of_a_manifest(hostile: str) -> None:
    """The `Finding` docstring is a property, not a promise.

    A message names a rule, a field path, and identifiers drawn from closed
    vocabularies. An unconstrained echo is how an escape sequence reaches a terminal
    or a forged line reaches a log, so every message is driven over deliberately
    hostile input and checked against the character set it declares.
    """
    poison = "\x1b[2K\rok      0 file(s)\n\u202e drop table --"
    scrape = {
        "scrape_configs": [
            {
                "job_name": f"inferops-{poison}" if hostile == "job name" else "j",
                "scrape_interval": "30s",
                "scrape_timeout": "60s",
                "relabel_configs": [
                    {
                        "target_label": (
                            poison if hostile == "target label" else "inferops_owner_id"
                        )
                    }
                ],
                "metric_relabel_configs": [
                    {"action": "labeldrop", "regex": f"({poison})"}
                ],
            }
        ]
    }
    rules = {
        "groups": [
            {
                "name": poison,
                "rules": [
                    {
                        "record": (
                            "inferops_build_info"
                            if hostile == "record name"
                            else f"inferops:{poison}"
                        ),
                        "expr": (
                            "llamacpp:never_observed_series"
                            if hostile == "native series"
                            else poison
                        ),
                    }
                ],
            }
        ]
    }
    findings = check_documents(
        [_tampered_config_map(yaml.safe_dump(scrape), yaml.safe_dump(rules))]
    )
    assert findings, "the hostile fixture produced no finding to inspect"
    for finding in findings:
        outside = set(finding.message) - SAFE_MESSAGE_CHARACTERS
        assert not outside, (
            f"{finding.rule} put {sorted(outside)!r} into a message; a finding names "
            "a rule, a field path, and closed-vocabulary identifiers, and nothing else"
        )
        assert poison not in finding.message


@pytest.mark.parametrize(
    "rule_id,mutate",
    [
        (
            "target-label-the-catalog-bars-from-a-metric",
            lambda text: text.replace(
                "target_label: k8s_component", "target_label: inferops_tenant_id", 1
            ),
        ),
        (
            "forbidden-label-is-not-dropped",
            lambda text: text.replace(
                'regex: "(http_response_status_code|', 'regex: "(inferops_owner_id|', 1
            ),
        ),
        (
            "recorded-name-collides-with-an-emitted-metric",
            lambda text: text.replace(
                "record: inferops:inference_requests_in_flight:runtime",
                "record: inferops_inference_requests_in_flight",
                1,
            ),
        ),
        (
            "native-series-was-never-observed",
            lambda text: text.replace(
                "llamacpp:requests_processing", "llamacpp:requests_invented", 1
            ),
        ),
        (
            "job-has-no-absence-rule",
            lambda text: text.replace(
                "- record: inferops:scrape_job_absent:serving_runtime\n"
                '            expr: absent(up{job="'
                + RELEASE_FULLNAME
                + '-serving-runtime"})\n',
                "",
                1,
            ),
        ),
        (
            "scrape-timeout-is-not-shorter-than-its-interval",
            lambda text: text.replace("scrape_timeout: 10s", "scrape_timeout: 30s", 1),
        ),
    ],
)
def test_each_rule_refuses_the_defect_it_is_named_for(rule_id, mutate) -> None:
    """A rule nobody has watched refuse anything is a rule nobody has tested."""
    source = (RENDERED_DIR / "real.expected.yaml").read_text(encoding="utf-8")
    tampered = mutate(source)
    assert tampered != source, "the mutation did not change the render"
    documents = [d for d in yaml.safe_load_all(tampered) if d]
    assert rule_id in {finding.rule for finding in check_documents(documents)}


def test_every_rule_the_checker_can_produce_is_declared() -> None:
    assert tuple(sorted(RULE_IDS)) == RULE_IDS
    assert len(set(RULE_IDS)) == len(RULE_IDS)


def test_the_command_line_agrees_with_the_library() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.telemetry_collection",
            "charts/inferops-llm/ci/rendered",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "satisfy the collection policy" in result.stdout


def test_the_command_line_reports_a_refusal_as_a_stable_document(tmp_path) -> None:
    source = (RENDERED_DIR / "real.expected.yaml").read_text(encoding="utf-8")
    tampered = source.replace(
        "target_label: k8s_component", "target_label: inferops_request_id", 1
    )
    manifest = tmp_path / "tampered.yaml"
    manifest.write_text(tampered, encoding="utf-8")

    runs = [
        subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.telemetry_collection",
                str(manifest),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        for _ in range(2)
    ]
    assert [run.returncode for run in runs] == [1, 1]
    assert runs[0].stdout == runs[1].stdout
    report = json.loads(runs[0].stdout)
    assert report["valid"] is False
    assert report["findings"]
