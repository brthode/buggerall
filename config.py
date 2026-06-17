import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

_HTTPS_RE = re.compile(r"^https://[^\s]+$")


@dataclass(frozen=True, slots=True)
class Config:
    jira_api_key: str
    jira_api_user: str
    jira_url: str
    qase_api_key: str


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Environment variable {name} is missing or empty")
    return value


def load_config() -> Config:
    load_dotenv()
    jira_api_key = _require("BUGGERALL_JIRA_API_KEY")
    jira_api_user = _require("BUGGERALL_JIRA_API_USER")
    jira_url = _require("BUGGERALL_JIRA_URL")
    qase_api_key = _require("BUGGERALL_QASE_API_KEY")

    if not _HTTPS_RE.match(jira_url):
        raise ValueError(
            f"BUGGERALL_JIRA_URL must be a valid HTTPS URL, got: {jira_url!r}"
        )

    return Config(
        jira_api_key=jira_api_key,
        jira_api_user=jira_api_user,
        jira_url=jira_url,
        qase_api_key=qase_api_key,
    )
