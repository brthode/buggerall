import os
from dataclasses import dataclass
from enum import Enum
from typing import Final, Self

import requests
from pydantic import BaseModel
from requests.auth import HTTPBasicAuth

PROJECT_KEY = "QT"
API_PATH = "/rest/api/3"
TIMEOUT = 30
LABEL: Final = "buggerall"
DONE_CATEGORY: Final = "done"

# Custom field storing the originating Qase test id — used to dedup tickets
# across runs: stored on create and matched on instead of the summary.
QASE_TEST_ID_FIELD = "customfield_15307"
QASE_PROJECT = "customfield_15340"


class JiraIssue(BaseModel):
    key: str
    summary: str | None
    status: str | None
    status_category: str | None
    issue_type: str | None
    qase_test_id: str | None
    qase_project: str | None
    url: str | None


class JiraError(RuntimeError):
    """Raised when the Jira API returns a non-success response."""


class Action(Enum):
    COMMENTED = "commented"
    SKIPPED_CLOSED = "skipped_closed"
    CREATED = "created"


@dataclass(frozen=True, slots=True)
class ProcessResult:
    action: Action
    issue: JiraIssue


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

    def get_issue_type_meta(self, issue_type_name: str = "Bug") -> dict[str, object]:
        data = self._request("GET", f"/issue/createmeta/{self._project_key}/issuetypes")
        issue_types = data.get("issueTypes")
        if not isinstance(issue_types, list):
            return {}
        items: list[object] = list(issue_types)  # type: ignore[arg-type]  # narrowed list is Unknown
        for it in items:
            it_dict = _as_dict(it)
            if _opt_str(it_dict.get("name")) == issue_type_name:
                type_id = _opt_str(it_dict.get("id"))
                if type_id:
                    return self._request(
                        "GET",
                        f"/issue/createmeta/{self._project_key}/issuetypes/{type_id}",
                    )
        return {}

    def create_issue(
        self,
        summary: str,
        description: str,
        qase_test_id: str,
        qase_project: str,
        issue_type: str = "Bug",
        labels: list[str] | None = None,
    ) -> JiraIssue:
        fields: dict[str, object] = {
            "project": {"key": self._project_key},
            "summary": summary,
            "description": _to_adf(description),
            "issuetype": {"name": issue_type},
            QASE_TEST_ID_FIELD: qase_test_id,
            QASE_PROJECT: qase_project,
        }
        if labels:
            fields["labels"] = labels
        data = self._request("POST", "/issue", json={"fields": fields})
        return self.get_issue(str(data["key"]))

    def update_issue(self, key: str, fields: dict[str, object]) -> None:
        self._request("PUT", f"/issue/{key}", json={"fields": fields})

    def add_comment(self, key: str, body: str) -> None:
        self._request("POST", f"/issue/{key}/comment", json={"body": _to_adf(body)})

    def search_issues(self, jql: str, max_results: int = 50) -> list[JiraIssue]:
        data = self._request(
            "GET",
            "/search/jql",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": f"summary,status,issuetype,{QASE_TEST_ID_FIELD},{QASE_PROJECT}",
            },
        )
        issues = data.get("issues")
        if not isinstance(issues, list):
            return []
        items: list[object] = list(issues)  # type: ignore[arg-type]  # narrowed list is Unknown
        return [self._to_issue(_as_dict(issue)) for issue in items]

    def find_existing_ticket(
        self,
        qase_test_id: str,
        *,
        label: str = LABEL,
        max_results: int = 50,
    ) -> JiraIssue | None:
        jql = f'labels = "{label}" AND project = {self._project_key} ORDER BY created DESC'
        candidates = self.search_issues(jql, max_results=max_results)
        return next(
            (issue for issue in candidates if issue.qase_test_id == qase_test_id),
            None,
        )

    def process_failure(
        self,
        qase_test_id: str,
        qase_test_name: str,
        description: str,
        qase_project: str,
        *,
        label: str = LABEL,
        done_category: str = DONE_CATEGORY,
    ) -> ProcessResult:
        match = self.find_existing_ticket(qase_test_id, label=label)
        if match is None:
            issue = self.create_issue(
                qase_test_name, description, qase_test_id, qase_project, labels=[label]
            )
            return ProcessResult(Action.CREATED, issue)
        if (match.status_category or "").lower() != done_category:
            self.add_comment(
                match.key, f"Still failing in the latest run: {qase_test_name}"
            )
            return ProcessResult(Action.COMMENTED, match)
        return ProcessResult(Action.SKIPPED_CLOSED, match)

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
            qase_project=_opt_str(fields.get(QASE_PROJECT)),
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
