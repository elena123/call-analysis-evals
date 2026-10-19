import json
import unittest
from uuid import uuid4

from call_analyst.agent import CallAnalysis

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from call_judge.agent import CallEvaluation, root_agent
from test_call_analyst import analyze_transcript


async def evaluate_analysis(transcript, analysis) -> CallEvaluation:
    session_service = InMemorySessionService()
    session_id = uuid4().hex

    await session_service.create_session(
        app_name="call_judge",
        user_id="test_user",
        session_id=session_id,
    )

    runner = Runner(
        agent=root_agent,
        app_name="call_judge",
        session_service=session_service,
    )

    payload = {
        "transcript": transcript,
        "analysis": analysis.model_dump(),
    }

    message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(payload))],
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
        raise AssertionError("The judge returned no final response.")

    return CallEvaluation.model_validate_json(final_response)


class TestCallEvaluation(unittest.IsolatedAsyncioTestCase):

    async def test_callback_analysis_passes_evaluation(self):
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

        # анализатор
        analysis = await analyze_transcript(transcript)

        self.report_data["Analysis"] = analysis.model_dump()

        # оценител
        evaluation = await evaluate_analysis(transcript, analysis)

        self.report_data["Evaluation"] = evaluation.model_dump()

        print("\nAnalysis:")
        print(analysis.model_dump_json(indent=2))

        print("\nEvaluation:")
        print(evaluation.model_dump_json(indent=2))

        # Запазваме и независимите механични проверки.
        self.assertFalse(analysis.appointment_booked)
        self.assertTrue(analysis.evidence.strip())
        self.assertIn(analysis.evidence, transcript)

        self.assertTrue(
            evaluation.booking_correct,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.evidence_supports_booking,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.summary_grounded,
            evaluation.explanation,
        )

    async def test_judge_rejects_incorrect_analysis(self):
        transcript = (
            "Customer: My heating system is not working. "
            "Can you send someone tomorrow at 10 AM? "
            "Agent: I need to check availability and call you back. "
            "Customer: Okay, I will wait for your call."
        )

        # Нарочно грешен анализ
        incorrect_analysis = CallAnalysis(
            reason="Heating system malfunction.",
            appointment_booked=True,
            evidence="Can you send someone tomorrow at 10 AM?",
            summary=(
                "The customer booked a confirmed technician visit "
                "for tomorrow at 10 AM."
            ),
        )

        self.report_data = {
            "Transcript": transcript,
            "Analysis": incorrect_analysis.model_dump(),
            "Expected evaluation": {
                "booking_correct": False,
                "evidence_supports_booking": False,
                "summary_grounded": False,
            },
        }

        evaluation = await evaluate_analysis(
            transcript,
            incorrect_analysis,
        )

        self.report_data["Evaluation"] = evaluation.model_dump()

        print("\nEvaluation of incorrect analysis:")
        print(evaluation.model_dump_json(indent=2))

        self.assertFalse(
            evaluation.booking_correct,
            evaluation.explanation,
        )
        self.assertFalse(
            evaluation.evidence_supports_booking,
            evaluation.explanation,
        )
        self.assertFalse(
            evaluation.summary_grounded,
            evaluation.explanation,
        )

    async def test_judge_rejects_invented_price_in_summary(self):
        transcript = (
            "Customer: My heating system is not working. "
            "Can you send someone tomorrow at 10 AM? "
            "Agent: I need to check availability and call you back. "
            "Customer: Okay, I will wait for your call."
        )

        analysis = CallAnalysis(
            reason="Heating system malfunction.",
            appointment_booked=False,
            evidence="I need to check availability and call you back.",
            summary=(
                "The customer requested a heating repair visit. "
                "The agent promised to check availability and call back. "
                "No appointment was confirmed. "
                "The agent quoted a repair price of $150."
            ),
        )

        self.report_data = {
            "Transcript": transcript,
            "Analysis": analysis.model_dump(),
            "Expected evaluation": {
                "booking_correct": False,
                "evidence_supports_booking": False,
                "summary_grounded": False,
            },
        }

        evaluation = await evaluate_analysis(transcript, analysis)

        self.report_data["Evaluation"] = evaluation.model_dump()

        print("\nEvaluation of analysis with invented price:")
        print(evaluation.model_dump_json(indent=2))

        self.assertTrue(
            evaluation.booking_correct,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.evidence_supports_booking,
            evaluation.explanation,
        )
        self.assertFalse(
            evaluation.summary_grounded,
            evaluation.explanation,
        )

    async def test_judge_rejects_irrelevant_evidence(self):
        transcript = (
            "Customer: My heating system is not working. "
            "Can you send someone tomorrow at 10 AM? "
            "Agent: I need to check availability and call you back. "
            "Customer: Okay, I will wait for your call."
        )

        analysis = CallAnalysis(
            reason="Heating system malfunction.",
            appointment_booked=False,
            evidence="My heating system is not working.",
            summary=(
                "The customer requested a technician visit. "
                "The agent said they would check availability "
                "and call back. No appointment was confirmed."
            ),
        )

        self.report_data = {
            "Transcript": transcript,
            "Analysis": analysis.model_dump(),
            "Expected evaluation": {
                "booking_correct": False,
                "evidence_supports_booking": False,
                "summary_grounded": False,
            },
        }

        self.assertIn(analysis.evidence, transcript)

        evaluation = await evaluate_analysis(transcript, analysis)
        self.report_data["Evaluation"] = evaluation.model_dump()

        print("\nEvaluation of irrelevant evidence:")
        print(evaluation.model_dump_json(indent=2))

        self.assertTrue(
            evaluation.booking_correct,
            evaluation.explanation,
        )
        self.assertFalse(
            evaluation.evidence_supports_booking,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.summary_grounded,
            evaluation.explanation,
        )

    async def test_judge_accepts_cancelled_appointment(self):
        transcript = (
            "Customer: I need an annual boiler inspection. "
            "Agent: We can visit Friday at 2 PM. "
            "Customer: Yes, please book it. "
            "Agent: Your appointment is confirmed. "
            "Customer: Actually, please cancel that appointment. "
            "Agent: Your Friday appointment has been cancelled."
        )

        analysis = CallAnalysis(
            reason="Annual boiler inspection.",
            appointment_booked=False,
            evidence="Your Friday appointment has been cancelled.",
            summary=(
                "The customer initially booked a boiler inspection "
                "for Friday at 2 PM, then requested cancellation. "
                "The agent confirmed the cancellation."
            ),
        )
        self.report_data = {
            "Transcript": transcript,
            "Analysis": analysis.model_dump(),
            "Expected evaluation": {
                "booking_correct": False,
                "evidence_supports_booking": False,
                "summary_grounded": False,
            },
        }

        evaluation = await evaluate_analysis(transcript, analysis)

        self.report_data["Evaluation"] = evaluation.model_dump()

        print("\nEvaluation of cancelled appointment:")
        print(evaluation.model_dump_json(indent=2))

        self.assertTrue(
            evaluation.booking_correct,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.evidence_supports_booking,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.summary_grounded,
            evaluation.explanation,
        )

    async def test_cancelled_appointment_full_flow(self):
        transcript = (
            "Customer: I need an annual boiler inspection. "
            "Agent: We can visit Friday at 2 PM. "
            "Customer: Yes, please book it. "
            "Agent: Your appointment is confirmed. "
            "Customer: Actually, please cancel that appointment. "
            "Agent: Your Friday appointment has been cancelled."
        )

        self.report_data = {
            "Transcript": transcript,
            "Expected booking status": False,
        }

        analysis = await analyze_transcript(transcript)

        self.report_data["Analysis"] = analysis.model_dump()

        print("\nCancellation analysis:")
        print(analysis.model_dump_json(indent=2))

        self.assertFalse(
            analysis.appointment_booked,
            "The final appointment status must be cancelled.",
        )
        self.assertTrue(
            analysis.evidence.strip(),
            "Evidence must not be empty.",
        )
        self.assertIn(analysis.evidence, transcript)

        evaluation = await evaluate_analysis(transcript, analysis)

        self.report_data["Evaluation"] = evaluation.model_dump()

        print("\nCancellation evaluation:")
        print(evaluation.model_dump_json(indent=2))

        self.assertTrue(
            evaluation.booking_correct,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.evidence_supports_booking,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.summary_grounded,
            evaluation.explanation,
        )

    async def test_confirmed_appointment_full_flow(self):
        transcript = (
            "Customer: My air conditioner is not cooling. "
            "Agent: We can send a technician Monday at 3 PM. "
            "Customer: Yes, please book that time. "
            "Agent: Your technician visit is confirmed "
            "for Monday at 3 PM."
        )

        self.report_data = {
            "Transcript": transcript,
            "Expected booking status": True,
            "Expected evaluation": {
                "booking_correct": True,
                "evidence_supports_booking": True,
                "summary_grounded": True,
            },
        }

        analysis = await analyze_transcript(transcript)
        self.report_data["Analysis"] = analysis.model_dump()

        self.assertTrue(
            analysis.appointment_booked,
            "Both parties agreed and the agent confirmed the visit.",
        )
        self.assertTrue(
            analysis.evidence.strip(),
            "Evidence must not be empty.",
        )
        self.assertIn(analysis.evidence, transcript)

        evaluation = await evaluate_analysis(transcript, analysis)
        self.report_data["Evaluation"] = evaluation.model_dump()

        print("\nConfirmed appointment analysis:")
        print(analysis.model_dump_json(indent=2))

        print("\nConfirmed appointment evaluation:")
        print(evaluation.model_dump_json(indent=2))

        self.assertTrue(
            evaluation.booking_correct,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.evidence_supports_booking,
            evaluation.explanation,
        )
        self.assertTrue(
            evaluation.summary_grounded,
            evaluation.explanation,
        )

    async def test_judge_stability_on_pending_appointment(self):
        transcript = (
            "Customer: My heating system is not working. "
            "Can you send someone tomorrow at 10 AM? "
            "Agent: I need to check availability and call you back. "
            "Customer: Okay, I will wait for your call."
        )

        analysis = CallAnalysis(
            reason="Heating system malfunction.",
            appointment_booked=False,
            evidence="I need to check availability and call you back.",
            summary=(
                "The customer requested a technician visit "
                "for tomorrow at 10 AM. The agent said they "
                "would check availability and call back. "
                "No appointment was confirmed."
            ),
        )

        expected = {
            "booking_correct": True,
            "evidence_supports_booking": True,
            "summary_grounded": True,
        }

        attempts = []

        self.report_data = {
            "Transcript": transcript,
            "Analysis": analysis.model_dump(),
            "Expected evaluation": expected,
            "Attempts": attempts,
        }

        for attempt in range(1, 6):
            evaluation = await evaluate_analysis(
                transcript,
                analysis,
            )

            actual = evaluation.model_dump(
                include=set(expected)
            )

            attempts.append({
                "attempt": attempt,
                "matches_expected": actual == expected,
                "evaluation": evaluation.model_dump(),
            })

            print(
                f"\nAttempt {attempt}: "
                f"{'MATCH' if actual == expected else 'MISMATCH'}"
            )

        matches = sum(
            item["matches_expected"] for item in attempts
        )

        self.report_data["Stability summary"] = {
            "completed_attempts": len(attempts),
            "matching_attempts": matches,
            "agreement_with_expected": matches / len(attempts),
        }

        self.assertEqual(
            matches,
            5,
            f"Only {matches}/5 evaluations matched expectations. "
            "See Attempts in the report for details.",
        )