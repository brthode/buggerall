import json
import logging

from config import load_config
from qase_runs.get_runs import Failure, QaseRuns


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
        # TODO: Attempt to locate a Jira bug for each failure


if __name__ == "__main__":
    main()
