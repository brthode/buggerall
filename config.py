import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

from logging_setup import get_logger

_HTTPS_RE = re.compile(r"^https://[^\s]+$")
_logger = get_logger(__name__)


_DEFAULT_MASS_FAILURE_THRESHOLD = 0.50
_DEFAULT_FLAKY_THRESHOLD = 0.20


@dataclass(frozen=True, slots=True)
class Config:
    jira_api_key: str
    jira_api_user: str
    jira_url: str
    qase_api_key: str
    mass_failure_threshold: float = _DEFAULT_MASS_FAILURE_THRESHOLD
    flaky_threshold: float = _DEFAULT_FLAKY_THRESHOLD


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

    def _optional_float(name: str, default: float) -> float:
        raw = os.environ.get(name)
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            _logger.warning(
                "Invalid value for %s=%r, using default %.2f", name, raw, default
            )
            return default

    config = Config(
        jira_api_key=jira_api_key,
        jira_api_user=jira_api_user,
        jira_url=jira_url,
        qase_api_key=qase_api_key,
        mass_failure_threshold=_optional_float(
            "BUGGERALL_MASS_FAILURE_THRESHOLD", _DEFAULT_MASS_FAILURE_THRESHOLD
        ),
        flaky_threshold=_optional_float(
            "BUGGERALL_FLAKY_THRESHOLD", _DEFAULT_FLAKY_THRESHOLD
        ),
    )
    _logger.info(
        "Config loaded: jira_url=%s jira_api_user=%s mass_failure_threshold=%.0f%% flaky_threshold=%.0f%%",
        config.jira_url,
        config.jira_api_user,
        config.mass_failure_threshold * 100,
        config.flaky_threshold * 100,
    )
    return config
