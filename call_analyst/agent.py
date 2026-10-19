import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field


env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)


class CallAnalysis(BaseModel):
    reason: str = Field(
        description="The customer's main reason for calling."
    )
    appointment_booked: bool = Field(
        description="True only if both parties agreed on a visit slot."
    )
    evidence: str = Field(
        description=(
            "An exact quote from the transcript supporting the booking status. "
            "Use an empty string if no supporting quote exists."
        )
    )
    summary: str = Field(
        description="A short factual summary of the call."
    )


root_agent = LlmAgent(
    name="call_analyst",
    model=LiteLlm(
        model=os.getenv("ADK_MODEL", "openai/gpt-4.1-mini")
    ),
    description="Analyzes customer service call transcripts.",
    instruction="""
        Always provide an exact, contiguous quote when the transcript
    contains evidence about the booking status.

    For an unconfirmed appointment, quote the statement showing
    uncertainty, pending availability, rejection, or cancellation.
    A promise to check availability and call back is evidence
    that the appointment is not confirmed.

    Use an empty string only when the transcript contains
    no evidence about appointment booking.
    """,
    output_schema=CallAnalysis,
)