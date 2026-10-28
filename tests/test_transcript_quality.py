import unittest

from test_call_analyst import analyze_transcript


class TestTranscriptQuality(unittest.IsolatedAsyncioTestCase):

    async def test_missing_cancellation_changes_booking_status(self):
        reference = (
            "Customer: I need an annual boiler inspection. "
            "Agent: We can visit Friday at 2 PM. "
            "Customer: Yes, please book it. "
            "Agent: Your appointment is confirmed. "
            "Customer: Actually, please cancel that appointment. "
            "Agent: Your Friday appointment has been cancelled."
        )

        candidate = (
            "Customer: I need an annual boiler inspection. "
            "Agent: We can visit Friday at 2 PM. "
            "Customer: Yes, please book it. "
            "Agent: Your appointment is confirmed."
        )

        self.report_data = {
            "Scenario": "Cancellation omitted from transcript",
            "Reference transcript": reference,
            "Candidate transcript": candidate,
            "Expected booking status from reference": False,
            "Expected booking status from candidate": True,
        }

        reference_analysis = await analyze_transcript(reference)
        self.report_data["Reference analysis"] = (
            reference_analysis.model_dump()
        )

        candidate_analysis = await analyze_transcript(candidate)
        self.report_data["Candidate analysis"] = (
            candidate_analysis.model_dump()
        )

        business_result_changed = (
            reference_analysis.appointment_booked
            != candidate_analysis.appointment_booked
        )

        self.report_data["Business impact"] = {
            "booking_status_changed": business_result_changed,
            "candidate_matches_reference_truth": (
                candidate_analysis.appointment_booked is False
            ),
            "explanation": (
                "The candidate omits the cancellation. "
                "A confirmed booking inferred from that text "
                "does not match the final state of the full call."
            ),
        }

        self.assertFalse(
            reference_analysis.appointment_booked,
            "The complete call ends with a cancellation.",
        )
        self.assertTrue(
            candidate_analysis.appointment_booked,
            "The shortened transcript ends with confirmation.",
        )

        self.assertTrue(
            business_result_changed,
            "Omitting the cancellation should change the booking result.",
        )