import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field


env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)


class CallEvaluation(BaseModel):
    booking_correct: bool = Field(
        description="Whether the booking status matches the transcript."
    )
    evidence_supports_booking: bool = Field(
        description=(
            "Whether the exact transcript quote supports the reported "
            "appointment_booked value, including false for pending "
            "or unconfirmed appointments."
        )
    )
    summary_grounded: bool = Field(
        description=(
            "Whether all factual claims in the summary "
            "are supported by the transcript."
        )
    )
    explanation: str = Field(
        description="A brief explanation identifying any specific errors."
    )


root_agent = LlmAgent(
    name="call_judge",
    model=LiteLlm(
        model=os.getenv("ADK_MODEL", "openai/gpt-4.1-mini")
    ),
    description="Evaluates call analyses against their source transcripts.",
    instruction="""
    Evaluate the supplied evidence itself, not just whether
    the booking status is correct based on the full transcript.
    
    Ask: does this quote provide information about whether
    an appointment was confirmed, left pending, rejected,
    or cancelled?
    
    A statement describing broken equipment does not support
    either booking status. The absence of a confirmation
    inside an unrelated quote is not evidence of no booking.
    
    Even when booking_correct is true,
    evidence_supports_booking must be false if the supplied
    quote is unrelated to scheduling.

    Apply these criteria independently:

    1. booking_correct
       An appointment is booked only when both parties explicitly
       agree on a visit slot.
       A requested time or a promise to check availability
       and call back is not a booking.
       A later cancellation overrides an earlier booking.
       Check whether analysis.appointment_booked matches
       the final state of the transcript.

    2. evidence_supports_booking
       This criterion means: evidence supports the REPORTED
       booking status, whether that status is true OR false.
       It does NOT mean evidence must confirm a booking.

       Evaluate analysis.evidence against
       analysis.appointment_booked:

       - If appointment_booked is true, the quote must support
         a confirmed appointment.
       - If appointment_booked is false, the quote must support
         an unconfirmed, pending, rejected, or cancelled appointment.
         A statement about checking availability and calling back
         supports false and MUST be accepted.

       The quote must be an exact, contiguous substring of
       the transcript. It may omit the speaker label and
       surrounding text.

       Reject unrelated quotes, such as statements describing
       broken equipment, even if the booking status is correct.

       Examples:
       Reported status: false
       Evidence: "I need to check availability and call you back."
       Result: true — the appointment is still pending.

       Reported status: true
       Evidence: "I need to check availability and call you back."
       Result: false — this does not confirm an appointment.

       Reported status: false
       Evidence: "My heating system is not working."
       Result: false — this says nothing about scheduling.

       Empty evidence is acceptable only when the transcript
       contains no booking-related evidence and the reported
       status is false.

    3. summary_grounded
       Every factual claim in the summary must be supported
       by the transcript.
       Mark false if it invents or contradicts facts such as
       confirmation, dates, prices, names, or promised actions.
       Different wording is acceptable.

    Explain specific failures. If all criteria pass,
    briefly explain why.

    Do not assume that the candidate analysis is correct.
    Return only JSON matching the output schema.
    """,
    output_schema=CallEvaluation,
)