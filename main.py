import json

from config import load_config
from jira.client import JiraClient, JiraError
from logging_setup import get_logger
from qase_runs.get_runs import PROJECT_CODE, Failure, QaseRuns, RunFailures

_logger = get_logger(__name__)


def main() -> None:
    load_config()

    with QaseRuns.from_env() as qase:
        result = qase.latest_run_failures()
        if result is None:
            _logger.info("No runs found")
            return
        failures: list[Failure] = [
            Failure(**item) for item in json.loads(result.model_dump_json())["failures"]
        ]
        _logger.info("Found %d failure(s)", len(failures))

    if not failures:
        _logger.info("No failures to file")
        return

    with JiraClient.from_env() as jira:
        for failure in failures:
            if failure.case_id is None:
                _logger.warning(
                    "Skipping failure with no case_id: %s", bug_summary(failure)
                )
                continue

            qase_test_id = str(failure.case_id)
            summary = bug_summary(failure)
            description = bug_description(failure, result)
            _logger.info(
                "Processing case %s (qase project %s): %r",
                qase_test_id,
                PROJECT_CODE,
                summary,
            )

            try:
                jira.process_failure(
                    qase_test_id=qase_test_id,
                    qase_test_name=summary,
                    description=description,
                    qase_project=PROJECT_CODE,
                    qase_run_id=result.run_id or 0,
                )
            except JiraError as exc:
                _logger.error("Jira call failed for case %s: %s", qase_test_id, exc)
                continue


def bug_summary(failure: Failure) -> str:
    name = (
        failure.case_name or (failure.comment or "Test failure").strip().splitlines()[0]
    )
    return f"[Qase] {name}"[:255]


def bug_description(failure: Failure, run: RunFailures) -> str:
    lines = [
        f"Automatically filed from Qase run #{run.run_id} ({run.title}).",
        "",
        f"Case ID: {failure.case_id}",
        f"Case name: {failure.case_name}",
        f"Status: {failure.status}",
        "",
        "Comment:",
        failure.comment or "(none)",
        "",
        "Stacktrace:",
        failure.stacktrace or "(none)",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
