import unittest
from uuid import uuid4

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from call_analyst.agent import CallAnalysis, root_agent


async def analyze_transcript(transcript: str) -> CallAnalysis:
    session_service = InMemorySessionService()
    session_id = uuid4().hex

    await session_service.create_session(
        app_name="call_analyst",
        user_id="test_user",
        session_id=session_id,
    )

    runner = Runner(
        agent=root_agent,
        app_name="call_analyst",
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"Analyze this transcript:\n{transcript}"
            )
        ],
    )

    final_response = None

    async for event in runner.run_async(
        user_id="test_user",
        session_id=session_id,
        new_message=message,
    ):
        if event.error_code:
            raise RuntimeError(f"ADK error: {event.error_code}")

        if event.is_final_response() and event.content:
            final_response = "".join(
                part.text or ""
                for part in event.content.parts or []
            )

    if not final_response:
        raise AssertionError("The agent returned no final response.")

    return CallAnalysis.model_validate_json(final_response)


class TestCallAnalyst(unittest.IsolatedAsyncioTestCase):

    async def test_confirmed_appointment(self):
        transcript = (
            "Customer: My heating system is not working. "
            "Agent: We can send a technician tomorrow at 10 AM. "
            "Customer: Yes, that works for me. "
            "Agent: Confirmed. Your appointment is tomorrow at 10 AM."
        )

        self.report_data = {
            "Transcript": transcript,
            "Expected booking status": True,
        }

        result = await analyze_transcript(transcript)

        self.report_data["Analysis"] = result.model_dump()

        self.assertTrue(result.appointment_booked)
        self.assertTrue(result.evidence.strip(), "Evidence is empty.")
        self.assertIn(result.evidence, transcript)

    async def test_callback_is_not_a_booking(self):
        transcript = (
            "Customer: My heating system is not working. "
            "Can you send someone tomorrow at 10 AM? "
            "Agent: I need to check availability and call you back. "
            "Customer: Okay, I will wait for your call."
        )

        self.report_data = {
            "Transcript": transcript,
            "Expected booking status": False,
        }

        result = await analyze_transcript(transcript)

        self.report_data["Analysis"] = result.model_dump()

        self.assertFalse(result.appointment_booked)
        self.assertTrue(result.evidence.strip(), "Evidence is empty.")
        self.assertIn(result.evidence, transcript)