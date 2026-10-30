# Call Analysis Evals
Automated Evaluation of LLM Call Analysis.

A Python prototype for testing LLM-generated analyses of customer
service call transcripts.

It combines deterministic assertions with a separate LLM judge.
The judge is also tested against manually constructed correct
and incorrect analyses.

## How it works

1. `call_analyst` extracts the call reason, final booking status,
   supporting evidence, and a summary.
2. Python checks the response schema, expected booking status,
   and whether the evidence exists verbatim in the transcript.
3. `call_judge` evaluates booking correctness, evidence relevance,
   and summary grounding.
4. A test runner generates HTML and JSON reports.

Both agents use Google ADK with OpenAI through LiteLLM.
The default model is `openai/gpt-4.1-mini`.

## Setup

Use Python 3.10 or later. The project has been run with Python 3.13.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=your_api_key
ADK_MODEL=openai/gpt-4.1-mini
```

## Run tests and reports

```bash
python run_tests.py
```

Reports are written to:

- `reports/report.html`
- `reports/report.json`

On macOS:

```bash
open reports/report.html
```

Each run replaces the previous reports.

To run tests without generating reports:

```bash
python -m unittest discover -s tests -v
```

To run only the judge stability check:

```bash
python -m unittest discover -s tests -p "test_call_evaluation.py" -k stability -v
```

Tests make real, billable OpenAI API calls.

## Meaning of the fields

`appointment_booked` describes the final state of the call:

- `true`: an appointment remains confirmed.
- `false`: no appointment was confirmed, or it was later cancelled.

The judge evaluates the candidate analysis:

| Field | Meaning of `true` |
|---|---|
| `booking_correct` | The reported booking status matches the transcript |
| `evidence_supports_booking` | The quote supports the reported status, including an unconfirmed or cancelled appointment |
| `summary_grounded` | All factual claims in the summary are supported by the transcript |

A negative test passes when the judge correctly rejects
an intentionally incorrect analysis.

## Test coverage

The suite covers:

- Confirmed appointments.
- Availability checks and promises to call back.
- Cancellation after an initial confirmation.
- Incorrect booking claims.
- Invented prices in summaries.
- Real transcript quotes that do not support the booking status.
- Repeated evaluation of one fixed transcript and analysis.

Full-flow tests cover confirmed, pending, and cancelled appointments.

## Judge validation and repeatability

During development, the judge incorrectly rejected a valid
substring quote and confused evidence for an unconfirmed
appointment with evidence for a confirmed booking.

These cases informed prompt clarification and regression tests.

One fixed pending-appointment example was evaluated five times
in separate sessions. All five evaluations matched the expected
three boolean judgments in the observed run.

This is a small repeatability check, not a general accuracy estimate.

## Report statuses

- `PASS`: all assertions passed.
- `FAIL`: an assertion did not match expectations.
- `ERROR`: execution raised an exception, such as an API connection error.
- `SKIP`: the test was skipped.

Detailed reports include available transcripts, analyses,
evaluations, expectations, and failure information.

## Limitations

- Uses a small set of synthetic English transcripts.
- Does not process audio or assess transcription quality.
- Both agents use the same underlying model and may share errors.
- Judge outputs can vary across runs.
- Several examples were used during prompt development;
  they are regression cases, not an independent benchmark.
- The current judge does not separately score the extracted call reason.
- Summary grounding checks factual support, not completeness.
- Boolean booking status does not distinguish pending,
  cancelled, and never-booked appointments.

## Possible next steps

- Expand independently labelled examples.
- Add paraphrases, noisy transcripts, and rescheduling cases.
- Test prompt injection embedded in transcripts.
- Measure judge agreement across more cases and repetitions.
- Compare a different judge model.
- Record model and prompt versions with each report.