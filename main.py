import logging

from config import load_config
from qase_runs.get_runs import QaseRuns


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
        print(result.model_dump_json(indent=2))

        # Typed access to individual failures, e.g. the first failure's comment:
        if result.failures:
            first = result.failures[0]
            print(f"\nFirst failure (case {first.case_id}): {first.comment}")


if __name__ == "__main__":
    main()
