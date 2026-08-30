"""The workload template files, one module each, held as text.

Six modules, three per profile: the contract, the quick start, and the test
skeleton. Each carries the output path it produces inside a generated workload
and the template text that produces it.

**Why text in a module rather than files beside one.** Nothing under
``src/inferops`` reads a path. That rule is checked — no ``open``, no
``read_text``, anywhere in the distribution — and it exists so that a domain
object is constructible from a wheel with no repository around it. A template
directory would have made this package the first exception, and an exception to
a rule that is checked is a rule that stops being checked. Holding the text here
also removes the packaging question entirely: a module ships wherever the
package ships.

**The output paths are identical across profiles**, on purpose. Two generated
workloads differ in what their files say, never in what their files are called.
"""

from __future__ import annotations

from typing import Final

from . import (
    contract_test_mock_llm,
    contract_test_synchronous_llm,
    readme_mock_llm,
    readme_synchronous_llm,
    workload_mock_llm,
    workload_synchronous_llm,
)

#: Every template, keyed by a stable name that says what it is and which profile
#: it belongs to. The name is what :mod:`inferops.scaffolding.template` maps an
#: output path to, and what a refusal names when a placeholder has no value.
TEMPLATES: Final[dict[str, tuple[str, str]]] = {
    "workload.mock-llm.yaml": (
        workload_mock_llm.OUTPUT_PATH,
        workload_mock_llm.TEMPLATE,
    ),
    "workload.synchronous-llm.yaml": (
        workload_synchronous_llm.OUTPUT_PATH,
        workload_synchronous_llm.TEMPLATE,
    ),
    "README.mock-llm.md": (readme_mock_llm.OUTPUT_PATH, readme_mock_llm.TEMPLATE),
    "README.synchronous-llm.md": (
        readme_synchronous_llm.OUTPUT_PATH,
        readme_synchronous_llm.TEMPLATE,
    ),
    "test_workload_contract.mock-llm.py": (
        contract_test_mock_llm.OUTPUT_PATH,
        contract_test_mock_llm.TEMPLATE,
    ),
    "test_workload_contract.synchronous-llm.py": (
        contract_test_synchronous_llm.OUTPUT_PATH,
        contract_test_synchronous_llm.TEMPLATE,
    ),
}

__all__ = ["TEMPLATES"]
