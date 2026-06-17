"""Fetch the latest Qase run for a project and report its failures.

Run with 1Password injecting the API key:

    op run --env-file=.env -- uv run python main.py

Expects BUGGERALL_QASE_API_KEY in the environment.
"""

import os
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel
from qase.api_client_v1 import ApiClient, Configuration, ResultsApi, RunsApi

if TYPE_CHECKING:
    from qase.api_client_v1.models.run import Run

PROJECT_CODE = "PRAT"
HOST = "https://api.qase.io/v1"


class Failure(BaseModel):
    case_id: int | None
    status: str | int | None
    comment: str | None
    stacktrace: str | None
    time_spent_ms: int | None


class RunFailures(BaseModel):
    run_id: int | None
    title: str | None
    status: str | int | None
    total: int | None
    passed: int | None
    failed: int | None
    failures: list[Failure]


class QaseRuns:
    def __init__(self, api_key: str, code: str = PROJECT_CODE) -> None:
        config = Configuration(host=HOST)
        config.api_key["TokenAuth"] = api_key
        self._client = ApiClient(config)
        self._code = code

    @classmethod
    def from_env(cls, code: str = PROJECT_CODE) -> Self:
        api_key = os.environ.get("BUGGERALL_QASE_API_KEY")
        if not api_key:
            raise ValueError("BUGGERALL_QASE_API_KEY is missing or empty")
        return cls(api_key, code)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.__exit__(*exc)

    def latest_run(self) -> Run | None:
        runs = RunsApi(self._client).get_runs(self._code, limit=100).result
        entities = runs.entities if runs else None
        if not entities:
            return None
        return max(entities, key=lambda run: run.id or 0)

    def _failures(self, run_id: int) -> list[Failure]:
        results = (
            ResultsApi(self._client)
            .get_results(self._code, run=str(run_id), status="failed", limit=100)
            .result
        )
        entities = results.entities if results else None
        if not entities:
            return []
        return [
            Failure(
                case_id=result.case_id,
                status=result.status,
                comment=result.comment,
                stacktrace=result.stacktrace,
                time_spent_ms=result.time_spent_ms,
            )
            for result in entities
        ]

    def latest_run_failures(self) -> RunFailures | None:
        run = self.latest_run()
        if run is None:
            return None
        stats = run.stats
        return RunFailures(
            run_id=run.id,
            title=run.title,
            status=run.status_text or run.status,
            total=stats.total if stats else None,
            passed=stats.passed if stats else None,
            failed=stats.failed if stats else None,
            failures=self._failures(run.id or 0),
        )


def main() -> None:
    with QaseRuns.from_env() as qase:
        result = qase.latest_run_failures()
        if result is None:
            print(f"No runs found for project {PROJECT_CODE}")
            return
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
