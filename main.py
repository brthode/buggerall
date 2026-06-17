import json
import logging

from config import load_config
from jira.client import JiraClient, JiraError
from qase_runs.get_runs import Failure, QaseRuns

_logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    load_config()
    print("Hello from python-directives!")

    with QaseRuns.from_env() as qase:
        result = qase.latest_run_failures()
        if result is None:
            print("No runs found")
            return
        failures: list[Failure] = [
            Failure(**item) for item in json.loads(result.model_dump_json())["failures"]
        ]
        print(failures)

    # TODO: Attempt to locate / create a Jira bug for each failure.
    # The API token isn't valid yet, so just confirm the client connects.
    try:
        with JiraClient.from_env() as jira:
            issues = jira.search_issues(
                f"project = {jira.project_key} ORDER BY created DESC", max_results=5
            )
            _logger.info("Jira reachable, %d recent issue(s) found", len(issues))
            for issue in issues:
                print(f"{issue.key}: {issue.summary} [{issue.status}]")
    except (JiraError, ValueError) as exc:
        _logger.warning("Jira call failed (expected until token works): %s", exc)


if __name__ == "__main__":
    main()
