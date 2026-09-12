"""Ask a running collector whether it actually collected anything.

Every other checker in this repository reads a file. This one reads a
Prometheus, and it exists because those are different questions and only the
second one was ever in doubt.

`tools.telemetry_collection` refuses a scrape configuration the catalog does not
permit. `tools.telemetry_correlation` refuses a query whose labels, series or
joins could not work, and evaluates every accepted query against fixture stores
written by hand. Both are static, both are worth having, and neither can tell you
that a target was discovered, that a scrape returned 200, or that an expression a
fixture answered is answered by a real engine over real series. The query
record's own `verificationStatus` said as much: `collected: false`,
`everInstalled: false`, and "No Prometheus has parsed, loaded, or evaluated any
expression in this record."

So this module asks three questions of the collector the release installs, in
the order that makes a failure legible:

1. **Discovery.** Does each of the two InferOps jobs have at least one target?
   A job that matched no pod is a selector that is wrong, and every query over
   that job would return empty for a reason that has nothing to do with the
   query.
2. **Scraping.** Is every one of those targets `up`, with a scrape that actually
   completed? A discovered target that never answered produces the same empty
   result as a job that discovered nothing, which is why the rendered rules
   carry `inferops:scrape_job_absent:*` to separate them.
3. **Answerability.** Does each accepted correlation query, evaluated by that
   Prometheus, return what the query record says it returns?

What it deliberately does not do is judge a query by the *size* of its result.
A counter's value depends on how much traffic happened to have been sent, and
this workflow sends three requests for the express purpose of moving counters off
zero rather than measuring anything. So a query is answerable when the engine
parses it and returns a result without error, and the record says which queries
returned samples and which returned none -- an empty result is reported, never
silently treated as a pass or a failure, because `emptyMeans` in the query record
is what interprets it.

Nothing here retains a prompt, a completion, or any label the catalog bars. The
evidence document holds counts, names and booleans.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tools.telemetry_correlation.core import load_query_record

#: The queries this evidence covers. Read from the accepted record rather than
#: listed here, so that a query added there and not asked here is impossible.
QUERY_RECORD_KEY = "queries"

#: How long one HTTP call to the collector may take. A collector that has not
#: answered a query in this long is not a collector this workflow can use, and a
#: hang is worse than a refusal because it has no message.
REQUEST_TIMEOUT_SECONDS = 30


class VerificationFailed(RuntimeError):
    """The collector did not establish something this evidence requires."""


@dataclass(frozen=True, slots=True)
class TargetSummary:
    """One scrape job, as the collector's own API reports it."""

    job: str
    discovered: int
    up: int
    last_error: str

    @property
    def healthy(self) -> bool:
        return self.discovered > 0 and self.up == self.discovered


def _get(base_url: str, path: str, **params: str) -> dict[str, Any]:
    url = f"{base_url}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as answer:
            if answer.status != 200:
                raise VerificationFailed(f"{path} answered HTTP {answer.status}")
            document = cast(dict[str, Any], json.loads(answer.read().decode("utf-8")))
    except urllib.error.URLError as error:
        raise VerificationFailed(f"{path} could not be reached: {error}") from error
    except json.JSONDecodeError as error:
        raise VerificationFailed(f"{path} did not answer JSON") from error
    if document.get("status") != "success":
        raise VerificationFailed(
            f"{path} answered status {document.get('status')!r}: "
            f"{document.get('error', 'no error given')}"
        )
    return document


def summarise_targets(base_url: str, jobs: tuple[str, ...]) -> dict[str, TargetSummary]:
    """What the collector says about each job, right now."""
    document = _get(base_url, "/api/v1/targets", state="active")
    active = document.get("data", {}).get("activeTargets", []) or []
    summaries: dict[str, TargetSummary] = {}
    for job in jobs:
        mine = [
            target for target in active if target.get("labels", {}).get("job") == job
        ]
        up = sum(1 for target in mine if target.get("health") == "up")
        # The first error any target reported, so that a failure says why rather
        # than only that it happened.
        errors = [
            str(target.get("lastError", "")).strip()
            for target in mine
            if str(target.get("lastError", "")).strip()
        ]
        summaries[job] = TargetSummary(
            job=job,
            discovered=len(mine),
            up=up,
            last_error=errors[0] if errors else "",
        )
    return summaries


def wait_for_scrapes(
    base_url: str, jobs: tuple[str, ...], budget_seconds: int
) -> dict[str, TargetSummary]:
    """Poll until every job has at least one target and all of them are up.

    Bounded, because a collector that has not completed a first scrape inside the
    budget has not completed one: Prometheus discovers and scrapes on its own
    schedule, and asking the instant the forward opens would report a healthy
    collector as broken.
    """
    deadline = time.monotonic() + budget_seconds
    summaries: dict[str, TargetSummary] = {}
    while True:
        summaries = summarise_targets(base_url, jobs)
        if all(summary.healthy for summary in summaries.values()):
            return summaries
        if time.monotonic() >= deadline:
            detail = "; ".join(
                f"{summary.job}: {summary.up}/{summary.discovered} up"
                + (f", last error {summary.last_error!r}" if summary.last_error else "")
                for summary in summaries.values()
            )
            raise VerificationFailed(
                "the collector did not scrape every InferOps target within "
                f"{budget_seconds} s: {detail}"
            )
        time.sleep(5)


#: The answerability class that publishes no expression at all. The query record
#: defines it as "there is no series to write a query against": the signal has no
#: emitter and no collector add-on in the accepted local cluster. A query in this
#: class is not asked, and its absence from the asked set is recorded rather than
#: left to be inferred from a count that does not add up.
NO_EXPRESSION_CLASS = "no-source"


def evaluate_queries(base_url: str) -> list[dict[str, Any]]:
    """Every accepted query that has an expression, evaluated by the collector.

    The three answerability classes are kept apart, because a single pass/fail
    over all of them would be three different claims wearing one number:

    `answerable-once-collected`
        Reads series something publishes today. It should return an answer now
        that a collector exists -- but whether it returns *samples* depends on
        what traffic happened, and this workflow sends three requests on purpose.
        So the engine accepting it is asserted and the sample count is recorded.
    `not-answerable-nothing-emits`
        Has an expression and reads a catalog metric marked not emitted. It must
        still parse, and it must return nothing: a sample here would mean the
        catalog is wrong about what this release publishes.
    `no-source`
        Publishes no expression. Not asked, and recorded as not asked.
    """
    record = load_query_record()
    results: list[dict[str, Any]] = []
    for query in record[QUERY_RECORD_KEY]:
        identifier = query["queryId"]
        answerability = query.get("answerability", "")
        expression = query.get("expr", "")
        if not expression:
            if answerability != NO_EXPRESSION_CLASS:
                raise VerificationFailed(
                    f"query {identifier!r} is {answerability!r} and publishes no "
                    "expression; only 'no-source' may do that"
                )
            results.append(
                {
                    "queryId": identifier,
                    "answerability": answerability,
                    "asked": False,
                    "parsed": False,
                    "sampleCount": 0,
                    "error": "",
                }
            )
            continue
        try:
            document = _get(base_url, "/api/v1/query", query=expression)
        except VerificationFailed as error:
            results.append(
                {
                    "queryId": identifier,
                    "answerability": answerability,
                    "asked": True,
                    "parsed": False,
                    "sampleCount": 0,
                    "error": str(error),
                }
            )
            continue
        data = document.get("data", {})
        result = data.get("result", []) or []
        results.append(
            {
                "queryId": identifier,
                "answerability": answerability,
                "asked": True,
                "parsed": True,
                "resultType": data.get("resultType", ""),
                "sampleCount": len(result),
                "error": "",
            }
        )
    return results


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise VerificationFailed(f"{name} was not set by the operating script")
    return value


def build_evidence() -> dict[str, Any]:
    base_url = _required("INFEROPS_COLLECTOR_BASE_URL")
    api_job = _required("INFEROPS_API_JOB")
    runtime_job = _required("INFEROPS_RUNTIME_JOB")
    budget = int(os.environ.get("INFEROPS_SCRAPE_BUDGET_SECONDS", "120"))

    summaries = wait_for_scrapes(base_url, (api_job, runtime_job), budget)
    queries = evaluate_queries(base_url)

    unparsed = [
        entry["queryId"] for entry in queries if entry["asked"] and not entry["parsed"]
    ]
    if unparsed:
        raise VerificationFailed(
            "a real Prometheus refused an accepted correlation query: "
            + ", ".join(unparsed)
        )

    # A query the catalog says nothing emits must return nothing. A sample here
    # would not be a better result than expected -- it would mean the catalog is
    # wrong about what this release publishes, which is a defect in the record
    # every other check in this repository is measured against.
    contradicted = [
        entry["queryId"]
        for entry in queries
        if entry["answerability"] == "not-answerable-nothing-emits"
        and entry["sampleCount"] > 0
    ]
    if contradicted:
        raise VerificationFailed(
            "a query the catalog marks as reading nothing this release emits "
            "returned samples: " + ", ".join(contradicted)
        )

    build = _get(base_url, "/api/v1/status/buildinfo").get("data", {})
    return {
        "outcome": "verified",
        "environment": {
            "provider": _required("INFEROPS_TARGET_PROVIDER"),
            "clusterName": _required("INFEROPS_TARGET_CLUSTER_NAME"),
            "serverVersion": os.environ.get("INFEROPS_TARGET_SERVER_VERSION", ""),
            "namespace": _required("INFEROPS_RELEASE_NAMESPACE"),
        },
        "collector": {
            "product": "prometheus",
            "version": build.get("version", ""),
            "revision": build.get("revision", ""),
        },
        "scrape": {
            "jobs": [
                {
                    "job": summary.job,
                    "discoveredTargets": summary.discovered,
                    "targetsUp": summary.up,
                }
                for summary in summaries.values()
            ]
        },
        "queries": {
            "evaluatedBy": "prometheus",
            "total": len(queries),
            "asked": sum(1 for entry in queries if entry["asked"]),
            "notAsked": sum(1 for entry in queries if not entry["asked"]),
            "parsed": sum(1 for entry in queries if entry["parsed"]),
            "withSamples": sum(1 for entry in queries if entry["sampleCount"] > 0),
            "results": queries,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.telemetry_collection.verify",
        description=(
            "Ask a running collector whether it discovered and scraped the two "
            "InferOps jobs, and whether it can evaluate every accepted "
            "correlation query."
        ),
    )
    parser.add_argument(
        "--evidence", required=True, help="where to write the evidence document"
    )
    args = parser.parse_args(argv)

    try:
        document = build_evidence()
    except VerificationFailed as error:
        print(f"FAILED telemetry collection verification: {error}", file=sys.stderr)
        return 1

    destination = Path(args.evidence)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    for job in document["scrape"]["jobs"]:
        print(
            f"scrape        {job['job']}: {job['targetsUp']}/"
            f"{job['discoveredTargets']} target(s) up"
        )
    queries = document["queries"]
    print(
        f"queries       {queries['parsed']}/{queries['asked']} asked queries "
        f"evaluated by {document['collector']['product']} "
        f"{document['collector']['version']}; {queries['withSamples']} returned "
        f"samples; {queries['notAsked']} publish no expression"
    )
    print(f"record        {args.evidence}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through direct main tests
    raise SystemExit(main())
