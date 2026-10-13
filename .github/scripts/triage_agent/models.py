from typing import Literal

from pydantic import BaseModel, Field


class TriageAnalysis(BaseModel):
    classification: Literal["bug", "enhancement", "question", "invalid"]
    severity: Literal["low", "medium", "high", "critical"]
    is_testable: bool = Field(
        description="True if enough XML/GPX data or steps are provided to write a pytest case"
    )
    summary: str = Field(description="A concise technical summary of the issue")
    suggested_labels: list[str]
    formatted_comment: str = Field(description="Markdown comment to post on the issue")
