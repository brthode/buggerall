"""Process a test failure into the right Jira action.

This ties together the dedup check (match_ticket.py) and the Jira REST client
(client.py) to decide what a single failing test should do to the QT project:

- A matching ticket that is still **open** — comment that it is failing again.
- A matching ticket that is **not open** (done/closed) — do nothing; a closed
  ticket is a deliberate state we don't reopen here.
- **No** matching ticket — file a fresh bug.

Run with 1Password injecting the credentials:

    op run --env-file=.env -- uv run python -m jira.process_ticket
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final, assert_never

from jira.client import JiraClient, JiraIssue
from jira.match_ticket import LABEL, find_existing_ticket

# Status category Jira assigns to closed/resolved issues, regardless of the
# project's custom status names. Anything else counts as "open".
DONE_CATEGORY: Final = "done"


class Action(Enum):
    """What was done with a test failure."""

    COMMENTED = "commented"
    SKIPPED_CLOSED = "skipped_closed"
    CREATED = "created"


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Outcome of processing one failing test."""

    action: Action
    issue: JiraIssue


class TicketProcessor:
    """Routes a failing test to a comment, a no-op, or a new ticket."""

    def __init__(
        self,
        client: JiraClient,
        *,
        label: str = LABEL,
        done_category: str = DONE_CATEGORY,
    ) -> None:
        self._client = client
        self._label = label
        self._done_category = done_category

    def process(
        self, qase_test_id: str, qase_test_name: str, description: str
    ) -> ProcessResult:
        """Comment on, skip, or create a ticket for a failing test.

        ``qase_test_id`` is matched against existing labelled tickets;
        ``qase_test_name`` becomes the summary and ``description`` the body of a
        brand-new ticket when one has to be filed.
        """
        match = find_existing_ticket(qase_test_id, self._client, label=self._label)
        if match is None:
            issue = self._create(qase_test_id, qase_test_name, description)
            return ProcessResult(Action.CREATED, issue)
        if self._is_open(match):
            self._client.add_comment(match.key, _still_failing_comment(qase_test_name))
            return ProcessResult(Action.COMMENTED, match)
        return ProcessResult(Action.SKIPPED_CLOSED, match)

    def _is_open(self, issue: JiraIssue) -> bool:
        return (issue.status_category or "").lower() != self._done_category

    def _create(
        self, qase_test_id: str, qase_test_name: str, description: str
    ) -> JiraIssue:
        # Carry the dedup label so future runs can match this ticket.
        return self._client.create_issue(
            qase_test_name, description, qase_test_id, labels=[self._label]
        )


def _still_failing_comment(qase_test_name: str) -> str:
    return f"This test is still failing in the latest run: {qase_test_name}"


def main() -> None:
    from jira.client import JiraError
    from logging_setup import get_logger

    logger = get_logger(__name__)

    # Stand-in failure; in the real pipeline this comes from a test result.
    qase_test_id = "12345"
    qase_test_name = "Example failing test"
    description = "Automated bug filed by buggerall for a failing test."

    try:
        with JiraClient.from_env() as client:
            result = TicketProcessor(client).process(
                qase_test_id, qase_test_name, description
            )
    except (JiraError, ValueError) as exc:
        logger.warning("Processing Jira ticket failed: %s", exc)
        return

    issue = result.issue
    match result.action:
        case Action.COMMENTED:
            logger.info("Commented on open ticket %s (%s)", issue.key, issue.url)
        case Action.SKIPPED_CLOSED:
            logger.info(
                "Ticket %s is closed (%s) — left untouched", issue.key, issue.status
            )
        case Action.CREATED:
            logger.info("Filed new ticket %s (%s)", issue.key, issue.url)
        case _ as unreachable:
            assert_never(unreachable)


if __name__ == "__main__":
    main()
