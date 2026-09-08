"""The telemetry collection policy: what a rendered scrape configuration may say.

This reads rendered Kubernetes manifests, finds the telemetry scrape ConfigMap the
``inferops-llm`` chart installs, and refuses one that would collect something the
accepted telemetry catalog says may not be collected -- or that describes a mapping
the measured runtime record does not support.

**What it establishes stops at the file.** It reads a rendered manifest, not a
running collector. No collector, store, dashboard, or alerting path is selected, no
Prometheus has loaded any configuration this checks, and a check over rendered YAML
is not a check over a collection that happened. It is the same distance
:mod:`tools.workload_policy` states between a rendered pod spec and a running
workload, for the same reason.

Six rules, each named for the failure it prevents:

``target-label-the-catalog-bars-from-a-metric``
    A relabel rule writes a target label whose name is a catalog attribute the
    catalog does not permit in ``metric-label`` or ``info-label``. This is the rule
    that stops a tenant identifier, a correlation identifier, a request identifier,
    or a pod name reaching a metrics store through the collector after the emitter
    was stopped from putting it there.

``forbidden-label-is-not-dropped``
    A job does not drop every label the catalog bars. The drop list is recomputed
    from the catalog on every run, so adding an attribute there is enough.

``recorded-name-collides-with-an-emitted-metric``
    A recording rule records a name a catalog metric already publishes. Two
    definitions of one metric name is the failure that makes a query answer
    differently depending on which one won.

``native-series-was-never-observed``
    A recording rule reads a ``llamacpp:`` series that the runtime feasibility record
    does not list. A mapping table is the easiest place in a repository to publish a
    series that does not exist.

``job-has-no-absence-rule``
    A scrape job has no ``absent()`` rule naming it. A job whose discovery matched
    nothing produces no ``up`` series at all, so every query that groups by job
    returns an empty result, and an empty result looks like a healthy quiet system.

``scrape-timeout-is-not-shorter-than-its-interval``
    A timeout that can outlive its interval lets a second scrape of one target start
    before the first has finished.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

__all__ = [
    "CATALOG_PATH",
    "COLLECTION_RECORD_PATH",
    "CONFIG_MAP_COMPONENT",
    "RECORDING_RULES_KEY",
    "RULE_IDS",
    "SCRAPE_CONFIG_KEY",
    "Finding",
    "check_documents",
    "emitted_metric_names",
    "forbidden_metric_labels",
    "is_scrape_config_map",
    "observed_native_series",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: Where placement is decided. Every rule below derives from it rather than
#: restating it, so a decision taken there reaches this checker without an edit.
CATALOG_PATH: Final = REPO_ROOT / "docs/telemetry/telemetry-catalog.v1alpha1.json"

#: The collection record this checker compares a render against.
COLLECTION_RECORD_PATH: Final = (
    REPO_ROOT / "docs/telemetry/kubernetes-telemetry-collection.v1alpha1.json"
)

#: The ``app.kubernetes.io/component`` value that identifies the ConfigMap. It is
#: the ownership inventory's row id, which is how every other rendered object in
#: this chart names the row it belongs to.
CONFIG_MAP_COMPONENT: Final = "telemetry-scrape-configuration"

#: The two keys the ConfigMap carries.
SCRAPE_CONFIG_KEY: Final = "scrape-config.yaml"
RECORDING_RULES_KEY: Final = "recording-rules.yaml"

RULE_IDS: Final[tuple[str, ...]] = (
    "forbidden-label-is-not-dropped",
    "job-has-no-absence-rule",
    "native-series-was-never-observed",
    "recorded-name-collides-with-an-emitted-metric",
    "scrape-timeout-is-not-shorter-than-its-interval",
    "target-label-the-catalog-bars-from-a-metric",
)

#: A Prometheus duration, restricted to the seconds the chart renders. Anything else
#: is reported as unreadable rather than parsed with a guess.
_SECONDS = re.compile(r"^(\d+)s$")

#: A ``llamacpp:`` series name inside a recording-rule expression.
_NATIVE_SERIES = re.compile(r"llamacpp:[A-Za-z0-9_]+")

#: The job named inside an ``absent(up{job="..."})`` expression.
_ABSENT_JOB = re.compile(r'absent\(\s*up\{\s*job\s*=\s*"([^"]+)"\s*\}\s*\)')


@dataclass(frozen=True)
class Finding:
    """One refusal, naming the rule, what it was found on, and what is wrong.

    It never quotes a value read out of the manifest. A finding is written into
    logs and terminals, and a checker that echoed what it refused would be the one
    place a forbidden value got published.
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

    def __str__(self) -> str:
        return f"{self.rule}  {self.subject}  {self.field}  {self.message}"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _prometheus_form(attribute_name: str) -> str:
    """The label name a Prometheus exposition would spell this attribute with."""
    return attribute_name.replace(".", "_")


def forbidden_metric_labels() -> frozenset[str]:
    """Every label name the catalog bars from a metric, in Prometheus form.

    Derived, not listed: an attribute whose declared placements include neither
    ``metric-label`` nor ``info-label`` may not key a series, and that is the whole
    of the rule. Deriving it is what lets a placement decision taken in the catalog
    reach a collector without anybody remembering to come here.
    """
    catalog = _load(CATALOG_PATH)
    return frozenset(
        _prometheus_form(attribute["name"])
        for attribute in catalog["attributes"]
        if "metric-label" not in attribute["placements"]
        and "info-label" not in attribute["placements"]
    )


def emitted_metric_names() -> frozenset[str]:
    """Every metric name the catalog declares, emitted or not.

    Not only the emitted ones: a recording rule that took the name of a metric that
    is specified and not yet emitted would collide on the day it starts emitting,
    which is the worst day to find out.
    """
    catalog = _load(CATALOG_PATH)
    return frozenset(metric["name"] for metric in catalog["metrics"])


def observed_native_series() -> frozenset[str]:
    """Every ``llamacpp:`` series the runtime feasibility record actually observed.

    The catalog carries them because a mapping table is the easiest place in a
    repository to publish a series that does not exist, and the catalog's own suite
    already compares its list against the record that measured it.
    """
    catalog = _load(CATALOG_PATH)
    native = catalog["runtimeNativeSeries"]
    groups: Sequence[Mapping[str, Any]] = (
        native if isinstance(native, list) else [native]
    )
    return frozenset(
        entry["seriesName"] for group in groups for entry in group["series"]
    )


def is_scrape_config_map(document: object) -> bool:
    """Whether a rendered document is the telemetry scrape ConfigMap."""
    if not isinstance(document, Mapping):
        return False
    if document.get("kind") != "ConfigMap":
        return False
    metadata = document.get("metadata")
    if not isinstance(metadata, Mapping):
        return False
    labels = metadata.get("labels")
    if not isinstance(labels, Mapping):
        return False
    return labels.get("app.kubernetes.io/component") == CONFIG_MAP_COMPONENT


def _subject(document: Mapping[str, Any]) -> str:
    metadata = document.get("metadata")
    name = metadata.get("name") if isinstance(metadata, Mapping) else None
    return f"ConfigMap/{name}" if isinstance(name, str) else "ConfigMap"


def _seconds(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    match = _SECONDS.match(value)
    return int(match.group(1)) if match else None


def _target_labels(job: Mapping[str, Any]) -> Iterator[str]:
    for rule in job.get("relabel_configs") or []:
        if isinstance(rule, Mapping):
            target = rule.get("target_label")
            if isinstance(target, str):
                yield target


def _dropped_labels(job: Mapping[str, Any]) -> frozenset[str]:
    """Every label name a job's ``labeldrop`` rules match.

    The regex is read as the alternation the chart writes rather than evaluated:
    a checker that ran an arbitrary regex from a manifest against a name list would
    be deciding what is dropped by running input it is supposed to be checking.
    """
    dropped: set[str] = set()
    for rule in job.get("metric_relabel_configs") or []:
        if not isinstance(rule, Mapping) or rule.get("action") != "labeldrop":
            continue
        pattern = rule.get("regex")
        if not isinstance(pattern, str):
            continue
        dropped.update(pattern.strip("()").split("|"))
    return frozenset(dropped)


def _check_job(
    job: Mapping[str, Any],
    subject: str,
    forbidden: frozenset[str],
    absent_jobs: frozenset[str],
) -> Iterator[Finding]:
    name = job.get("job_name")
    label = name if isinstance(name, str) else "<unnamed job>"

    for target in sorted(set(_target_labels(job)) & forbidden):
        yield Finding(
            rule="target-label-the-catalog-bars-from-a-metric",
            subject=subject,
            field=f"{label}.relabel_configs",
            message=(
                f"the job writes the target label {target!r}, which the telemetry "
                "catalog does not permit in a metric label or an identity label. "
                "The emitter is refused this placement at construction; a "
                "collector that added it would put it in the store anyway"
            ),
        )

    missing = forbidden - _dropped_labels(job)
    if missing:
        yield Finding(
            rule="forbidden-label-is-not-dropped",
            subject=subject,
            field=f"{label}.metric_relabel_configs",
            message=(
                f"{len(missing)} label name(s) the catalog bars from a metric are "
                "not dropped by this job, the first alphabetically being "
                f"{min(missing)!r}. The drop list is derived from the catalog, so a "
                "new attribute there has to reach the chart's "
                "inferops-llm.forbiddenMetricLabels helper"
            ),
        )

    interval = _seconds(job.get("scrape_interval"))
    timeout = _seconds(job.get("scrape_timeout"))
    if interval is not None and timeout is not None and timeout >= interval:
        yield Finding(
            rule="scrape-timeout-is-not-shorter-than-its-interval",
            subject=subject,
            field=f"{label}.scrape_timeout",
            message=(
                "the scrape timeout is not shorter than the scrape interval. A "
                "second scrape of one target then starts before the first has "
                "finished, so a slow endpoint answers a rising number of concurrent "
                "requests and the collector becomes part of the load it measures"
            ),
        )

    if isinstance(name, str) and name not in absent_jobs:
        yield Finding(
            rule="job-has-no-absence-rule",
            subject=subject,
            field=f"{label}.job_name",
            message=(
                "no recording rule asks absent(up{job=...}) for this job. A job "
                "whose discovery matches no pod produces no up series at all, so "
                "every query that groups by job returns an empty result, and an "
                "empty result reads as a healthy quiet system"
            ),
        )


def _check_rules(
    groups: Sequence[Mapping[str, Any]],
    subject: str,
) -> Iterator[Finding]:
    declared = emitted_metric_names()
    observed = observed_native_series()

    for group in groups:
        group_name = group.get("name")
        where = group_name if isinstance(group_name, str) else "<unnamed group>"
        for rule in group.get("rules") or []:
            if not isinstance(rule, Mapping):
                continue
            record = rule.get("record")
            expression = rule.get("expr")
            if isinstance(record, str) and record in declared:
                yield Finding(
                    rule="recorded-name-collides-with-an-emitted-metric",
                    subject=subject,
                    field=f"{where}.{record}",
                    message=(
                        "this recording rule records a name the telemetry catalog "
                        "already declares as a metric. Two definitions of one name "
                        "make a query answer differently depending on which one "
                        "won; a derived series is spelled inferops: with a colon"
                    ),
                )
            if not isinstance(expression, str):
                continue
            for series in sorted(set(_NATIVE_SERIES.findall(expression)) - observed):
                yield Finding(
                    rule="native-series-was-never-observed",
                    subject=subject,
                    field=f"{where}.{record if isinstance(record, str) else '?'}",
                    message=(
                        f"the expression reads {series!r}, which the runtime "
                        "feasibility record does not list. A mapping table is the "
                        "easiest place in a repository to publish a series that "
                        "does not exist"
                    ),
                )


def _absent_jobs(groups: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    named: set[str] = set()
    for group in groups:
        for rule in group.get("rules") or []:
            if not isinstance(rule, Mapping):
                continue
            expression = rule.get("expr")
            if isinstance(expression, str):
                named.update(_ABSENT_JOB.findall(expression))
    return frozenset(named)


def _parsed(text: object) -> Any:
    import yaml

    if not isinstance(text, str):
        return None
    return yaml.safe_load(text)


def check_documents(documents: Iterable[object]) -> list[Finding]:
    """Every refusal in a rendered bundle, sorted so that output is stable.

    A bundle with no telemetry scrape ConfigMap produces no findings. That is not an
    oversight: the ConfigMap is switched off by one value, a release that renders
    none is a supported installation, and a checker that demanded one would be
    enforcing a decision the chart leaves to the operator.
    """
    findings: list[Finding] = []
    forbidden = forbidden_metric_labels()

    for document in documents:
        if not is_scrape_config_map(document):
            continue
        assert isinstance(document, Mapping)
        subject = _subject(document)
        data = document.get("data")
        if not isinstance(data, Mapping):
            continue

        rules_document = _parsed(data.get(RECORDING_RULES_KEY))
        groups: list[Mapping[str, Any]] = []
        if isinstance(rules_document, Mapping):
            raw = rules_document.get("groups")
            if isinstance(raw, list):
                groups = [g for g in raw if isinstance(g, Mapping)]

        scrape_document = _parsed(data.get(SCRAPE_CONFIG_KEY))
        if isinstance(scrape_document, Mapping):
            raw_jobs = scrape_document.get("scrape_configs")
            if isinstance(raw_jobs, list):
                absent = _absent_jobs(groups)
                for job in raw_jobs:
                    if isinstance(job, Mapping):
                        findings.extend(_check_job(job, subject, forbidden, absent))

        findings.extend(_check_rules(groups, subject))

    return sorted(findings, key=lambda f: (f.rule, f.subject, f.field, f.message))
