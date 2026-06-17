"""Match a candidate Jira ticket against existing QT tickets labelled "buggerall".

The flow mirrors the deduplication step in main.py: before filing a bug for a
test failure we check whether an equivalent ticket already exists. If one does,
we return it (so the caller can skip creation); otherwise we return None, the
signal that the new ticket is genuinely new and should be filed.

Run with 1Password injecting the credentials:

    op run --env-file=.env -- uv run python -m jira.match_ticket
"""

from typing import Final

from jira.client import JiraClient, JiraIssue

LABEL: Final = "buggerall"


def find_existing_ticket(
    qase_test_id: str,
    client: JiraClient,
    *,
    label: str = LABEL,
    max_results: int = 50,
) -> JiraIssue | None:
    """Return an existing QT ticket whose summary matches, else None.

    Searches the client's project for issues carrying ``label`` and compares
    each one's qase_test_id. The first exact match wins (a ticket
    title is assumed unique). None means no match — the caller should file the
    new ticket.
    """
    # JQL quotes the label so values with special characters still parse.
    jql = f'labels = "{label}" AND project = {client.project_key} ORDER BY created DESC'
    candidates = client.search_issues(jql, max_results=max_results)
    return next(
        (issue for issue in candidates if issue.qase_test_id == qase_test_id),
        # TODO later we will do a fuzzy match for description
        None,
    )


def main() -> None:
    from jira.client import JiraError
    from logging_setup import get_logger

    logger = get_logger(__name__)

    # A stand-in candidate; in the real pipeline this comes from a test failure.
    candidate_qase_test_id = "12345"

    try:
        with JiraClient.from_env() as client:
            match = find_existing_ticket(candidate_qase_test_id, client)
    except (JiraError, ValueError) as exc:
        logger.warning("Jira match failed: %s", exc)
        return

    match match:
        case None:
            logger.info(
                "No existing ticket for %r — file a new one", candidate_qase_test_id
            )
        case found:
            logger.info("Existing ticket found: %s (%s)", found.key, found.url)


if __name__ == "__main__":
    main()
