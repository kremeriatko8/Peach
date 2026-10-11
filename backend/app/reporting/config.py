import os
import re
from dataclasses import dataclass

from app.reports.builder import ReportConfig


@dataclass(frozen=True)
class ReportingSettings:
    owner_sub: str
    scope: str
    bucket: str
    queue_arn: str
    recipient: str
    sender: str
    dedup_table: str
    allow_direct: bool = False

    @classmethod
    def from_env(cls, *, builder: bool = False) -> ReportingSettings:
        if os.environ.get("REPORT_TIMEZONE") != "Europe/Kyiv":
            raise ValueError("Reporting timezone must be Europe/Kyiv")
        return cls(
            (os.environ["REPORT_OWNER_SUB"] if builder else "mailer-no-database-access"),
            os.environ["REPORT_SCOPE_ID"],
            os.environ["REPORT_BUCKET"],
            (os.environ["REPORT_QUEUE_ARN"] if builder else ""),
            os.environ.get("REPORT_RECIPIENT_EMAIL", ""),
            os.environ.get("REPORT_FROM_EMAIL", ""),
            os.environ.get("REPORT_DEDUP_TABLE", ""),
            os.environ.get("REPORT_ALLOW_DIRECT", "false") == "true",
        )

    def __post_init__(self) -> None:
        ReportConfig(self.owner_sub)
        if self.owner_sub.lower() in self.scope.lower():
            raise ValueError("Report scope must not contain the Cognito owner subject")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", self.scope):
            raise ValueError("Report scope must be an opaque lowercase slug")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket):
            raise ValueError("Invalid report bucket")
        for address in (self.recipient, self.sender):
            if address and not re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", address):
                raise ValueError("Invalid configured report email")

    def key(self, week: str) -> str:
        return f"reports/{self.scope}/{week}.csv"
