"""Client for the Jira Cloud REST API v3.

Wraps create / get / update / search of issues for the QT project. Auth is
HTTP Basic with the account email (BUGGERALL_JIRA_API_USER) and an API token
(BUGGERALL_JIRA_API_KEY); the site base URL is BUGGERALL_JIRA_URL, e.g.
https://smithrx.atlassian.net

Run with 1Password injecting the credentials:

    op run --env-file=.env -- uv run python main.py
"""

import os
from typing import Self

import requests
from pydantic import BaseModel
from requests.auth import HTTPBasicAuth

PROJECT_KEY = "QT"
API_PATH = "/rest/api/3"
TIMEOUT = 30

# Jira custom field holding the originating Qase test id. Used to dedup tickets
# across runs: we store it on create and match on it instead of the summary.
QASE_TEST_ID_FIELD = "customfield_15307"


class JiraIssue(BaseModel):
    key: str
    summary: str | None
    status: str | None
    status_category: str | None
    issue_type: str | None
    qase_test_id: str | None
    url: str | None


class JiraError(RuntimeError):
    """Raised when the Jira API returns a non-success response."""


class JiraClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project_key: str = PROJECT_KEY,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = HTTPBasicAuth(email, api_token)
        self._project_key = project_key
        self._session = requests.Session()
        self._session.auth = self._auth
        self._session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )

    @property
    def project_key(self) -> str:
        return self._project_key

    @classmethod
    def from_env(cls, project_key: str = PROJECT_KEY) -> Self:
        base_url = _require("BUGGERALL_JIRA_URL")
        email = _require("BUGGERALL_JIRA_API_USER")
        api_token = _require("BUGGERALL_JIRA_API_KEY")
        return cls(base_url, email, api_token, project_key)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self._session.close()

    def _url(self, path: str) -> str:
        return f"{self._base_url}{API_PATH}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, object]:
        response = self._session.request(
            method, self._url(path), json=json, params=params, timeout=TIMEOUT
        )
        if not response.ok:
            raise JiraError(
                f"{method} {path} -> {response.status_code}: {response.text}"
            )
        if not response.content:
            return {}
        body: object = response.json()
        if isinstance(body, list):
            return {"result": body}
        return _as_dict(body)

    def get_issue(self, key: str) -> JiraIssue:
        data = self._request("GET", f"/issue/{key}")
        return self._to_issue(data)

    def create_issue(
        self,
        summary: str,
        description: str,
        qase_test_id: str,
        issue_type: str = "Bug",
        labels: list[str] | None = None,
    ) -> JiraIssue:
        fields: dict[str, object] = {
            "project": {"key": self._project_key},
            "summary": summary,
            "description": _to_adf(description),
            "issuetype": {"name": issue_type},
            QASE_TEST_ID_FIELD: qase_test_id,
        }
        if labels:
            fields["labels"] = labels
        data = self._request("POST", "/issue", json={"fields": fields})
        return self.get_issue(str(data["key"]))

    def update_issue(self, key: str, fields: dict[str, object]) -> None:
        self._request("PUT", f"/issue/{key}", json={"fields": fields})

    def add_comment(self, key: str, body: str) -> None:
        """Append a plain-text comment to an issue."""
        self._request("POST", f"/issue/{key}/comment", json={"body": _to_adf(body)})

    def search_issues(self, jql: str, max_results: int = 50) -> list[JiraIssue]:
        # The legacy /search endpoint was removed; v3 uses /search/jql, which
        # returns an "issues" array plus "isLast"/"nextPageToken" for paging.
        data = self._request(
            "GET",
            "/search/jql",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": f"summary,status,issuetype,{QASE_TEST_ID_FIELD}",
            },
        )
        issues = data.get("issues")
        if not isinstance(issues, list):
            return []
        items: list[object] = list(issues)  # type: ignore[arg-type]  # narrowed list is Unknown
        return [self._to_issue(_as_dict(issue)) for issue in items]

    def _to_issue(self, data: dict[str, object]) -> JiraIssue:
        key = str(data.get("key", ""))
        fields = _as_dict(data.get("fields"))
        status = _as_dict(fields.get("status"))
        category = _as_dict(status.get("statusCategory"))
        issue_type = _as_dict(fields.get("issuetype"))
        return JiraIssue(
            key=key,
            summary=_opt_str(fields.get("summary")),
            status=_opt_str(status.get("name")),
            status_category=_opt_str(category.get("key")),
            issue_type=_opt_str(issue_type.get("name")),
            qase_test_id=_opt_str(fields.get(QASE_TEST_ID_FIELD)),
            url=f"{self._base_url}/browse/{key}" if key else None,
        )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Environment variable {name} is missing or empty")
    return value


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items()}  # type: ignore[misc]  # narrowed dict items are Unknown


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _to_adf(text: str) -> dict[str, object]:
    """Wrap plain text in the Atlassian Document Format the v3 API requires."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }
