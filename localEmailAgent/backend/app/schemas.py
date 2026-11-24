"""Data classes shared by the summarizer and the API.

ModelEmailSummary / ChunkSummaries describe what the *model* must return (its JSON schema is
passed to Ollama). EmailItem is what the *API* returns per email: sender, subject and date come
from Gmail, never from the model.
"""
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class ModelEmailSummary(BaseModel):
    email_number: int = Field(description="The number in the email's '--- Email N ---' header")
    summary: str = Field(description="One sentence saying what the email says")
    needs_action: bool = Field(description="True only if the recipient must reply or do something")
    deadline: str = Field(description="Deadline or date/time stated in the email, else empty string")


class ChunkSummaries(BaseModel):
    emails: list[ModelEmailSummary]


@dataclass
class EmailItem:
    id: str
    sender: str
    subject: str
    date: str
    summary: str
    needs_action: bool
    deadline: str | None
    priority: Literal["high", "normal"]
    summarized: bool  # False if the model returned nothing usable for this email
