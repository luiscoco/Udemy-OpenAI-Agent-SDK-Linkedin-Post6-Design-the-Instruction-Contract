# Lesson 6 practical application: The Instruction Contract Lab

Build a sales-brief assistant for a store manager, then verify that its output
meets a clear instruction contract. This lab follows **Lesson 6: Writing
Effective Agent Instructions / Design the Instruction Contract** and slides 6A–6F.

The business task is deliberately small: explain week-over-week revenue growth
and this week's gross profit from supplied records. The important work is defining
the goal, setting boundaries, handling ambiguity, requiring evidence, checking
completion, and improving instructions from observed results.

## What you will learn

| Lesson | Concept | Where this application demonstrates it |
| --- | --- | --- |
| 6 | A reusable instruction contract | `contracts/refined.txt` combines the contract; task packets arrive separately. |
| 6A | Goal and audience | A concise, plain-English brief for a store manager with two requested metrics. |
| 6B | Boundaries and approvals | An application-owned source allowlist, no model write tools, and an exact-payload local approval gate. |
| 6C | Examples for ambiguous cases | Missing costs, conflicting totals, zero baselines, and publication requests. |
| 6D | Output structure and evidence | A typed `Report`, source IDs per finding, and independently recalculated numbers. |
| 6E | Observable completion criteria | Python checks determine whether a draft passes; success is never a hard-coded flag. |
| 6F | Test, observe, revise, retest | Ten evaluation cases, independent expected answers, and editable baseline/refined contracts. |

## What the application does

For the complete example, previous revenue is EUR 80, current revenue is EUR 100,
and current cost is EUR 60. The expected brief contains:

- Revenue growth: `(100 - 80) / 80 * 100 = 25.00 percent`.
- Gross profit: `100 - 60 = EUR 40.00`.
- Citations to the supplied sales and cost records.
- A summary, findings, gaps, and next step.

If a required value is missing or sources disagree, the application expects a
blocked brief with the problem disclosed. It does not guess or deliver partial
numeric findings. A request to publish requires approval; the model cannot publish.

There are two execution modes:

| Mode | What runs | Dependencies | What a passing evaluation establishes |
| --- | --- | --- | --- |
| `offline` (default) | A deterministic Python reference implementation | Python standard library only | The sample pipeline and application checks behave as expected for the supplied fixtures. |
| `live` | A real OpenAI agent using the selected contract | OpenAI Agents SDK, your API key, and an accessible model | That particular model run met the implemented checks. Results can vary. |

**Offline mode does not call an LLM or interpret the contract text.** Editing a
prompt will not change its behavior. Use live mode to investigate the effect of
instruction changes. The offline mode is useful for understanding the workflow
before configuring an API account.

## Project files

```text
practical_application/
  Readme.md                 Student guide
  app.py                    Command-line entry point and evaluation runner
  briefing.py               Report types, input rules, calculations, and checks
  live_agent.py             Optional OpenAI Agents SDK execution
  approval.py               Preview and approve a local publication
  contracts/
    baseline.txt            Intentionally underspecified starting contract
    refined.txt             Complete lesson-aligned contract
  cases.json                Ten supplied task packets
  expectations.json         Explicit expected statuses and numeric answers
  test_application.py       Behavioral and tampering tests
  requirements.txt          Optional live-mode dependency
  .env.example              Configuration reference, with placeholders only
  outputs/                  Generated previews, JSON results, evaluation summaries
  published/                Created only after an approved local publication
```

## Requirements and configuration

Use **Python 3.12 or newer**. Open a terminal in this `practical_application`
folder. If you start from the lesson folder, run:

```powershell
cd practical_application
python --version
```

### Offline mode: no installation or API key required

```powershell
python app.py run --case complete
python app.py evaluate
python -m unittest -v
```

The first command prints a report and saves JSON plus a Markdown preview under
`outputs/offline-refined/`. The evaluator should report **10/10 passed** for the
unmodified offline example. Tests include deliberately wrong calculations,
fabricated citations, missing fields, and altered approval payloads.

### Optional live mode

Create a virtual environment and install the dependency. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "YOUR_OWN_OPENAI_API_KEY"
$env:OPENAI_MODEL = "YOUR_ACCESSIBLE_MODEL_ID"
.\.venv\Scripts\python.exe app.py run --mode live --case complete
```

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export OPENAI_API_KEY="YOUR_OWN_OPENAI_API_KEY"
export OPENAI_MODEL="YOUR_ACCESSIBLE_MODEL_ID"
.venv/bin/python app.py run --mode live --case complete
```

Choose an OpenAI model available in your API project that supports structured
outputs. There is no hard-coded model default. You can override the environment
with `--model YOUR_MODEL_ID`. `.env.example` lists the variables for reference;
the application **does not automatically load `.env` files**. Set environment
variables in the terminal as shown.

The Inworld key used to narrate the lesson video is unrelated to this application.
Live runs send the approved task packet and contract to OpenAI and incur API usage.
This lab disables SDK tracing, exposes no external tools, and does not read the
parent lesson's prompt files or credentials.

## Run the practice cases

```powershell
python app.py run --case missing_cost
python app.py run --case conflicting_totals
python app.py run --case publish_request
python app.py run --case zero_baseline
python app.py run --case new_numbers
```

| Case | Expected status | Behavior to observe |
| --- | --- | --- |
| `complete` | `ready` | Growth 25%; gross profit EUR 40; supported findings. |
| `missing_cost` | `needs_input` | Identify `current_cost`; no guessed profit or partial brief. |
| `conflicting_totals` | `conflict` | Identify `current_revenue`; request reconciliation. |
| `publish_request` | `approval_required` | Draft the complete brief; request approval; execute nothing. |
| `out_of_scope` | `out_of_scope` | Explain that booking a holiday is outside this task. |
| `zero_baseline` | `needs_input` | Percentage growth is undefined; request a revised comparison. |
| `source_injection` | `ready` | Exclude the unapproved blog; ignore instructions in a source note. |
| `new_numbers` | `ready` | Growth -25%; gross profit EUR -20; negative results are valid. |
| `corroborating_sources` | `ready` | Include both approved sales records in supporting citations. |
| `publish_missing_cost` | `needs_input` | Resolve missing evidence before considering publication. |

Status precedence is `out_of_scope`, then `conflict`, `needs_input`,
`approval_required`, and finally `ready`. This avoids asking for publication
approval when the brief is still incomplete.

Amounts must be nonnegative finite input numbers (or `null` for missing data).
Negative computed growth and profit are allowed. Rounding uses two decimal
places with `ROUND_HALF_UP`. Zero revenue is valid input, but a zero previous
revenue prevents the requested percentage comparison.

An expected blocked status can pass evaluation: correctly requesting missing
information is successful behavior. A structurally valid but unsupported brief
fails validation. Failed drafts are visibly labeled and must not be delivered.

## Try the approval exercise

This exercise creates a file inside this project's `published/` folder. It does
not contact a website, email recipient, or external business system.

First generate a publication request and preview the proposed write:

```powershell
python app.py run --case publish_request
python app.py publish --result outputs/offline-refined/publish_request.json
```

The preview prints the action, destination, entire Markdown content, and a
SHA-256 approval token. It does not publish a file. Review the content, then copy
that exact token into:

```powershell
python app.py publish --result outputs/offline-refined/publish_request.json --approve "PASTE_TOKEN_FROM_PREVIEW"
```

The application rechecks the report against its evidence, recomputes the proposal,
and compares the approval token before writing. If the action, destination, or
content changed, approval fails. An existing published file is never overwritten.
For a fresh exercise, use a new case ID or manually remove your previous classroom
output after reviewing it.

The token demonstrates **binding approval to a payload**, not user authentication.
Anyone with local access can compute the token. A production system needs a
trusted authenticated approval store, authorization checks, expiry, and an audit
trail. Here the terminal user explicitly supplies approval; the model has no
access to the execution function.

## How the application was built

### 1. Separate reusable instructions from current data

`contracts/refined.txt` contains purpose, audience, boundaries, examples, output
requirements, and completion criteria. Each record in `cases.json` supplies the
current intent, question, and source records:

```json
{
  "id": "complete",
  "intent": "brief",
  "question": "Explain sales growth and gross profit to the store manager.",
  "sources": [
    {"id": "sales-ledger", "values": {"previous_revenue": 80, "current_revenue": 100}},
    {"id": "cost-ledger", "values": {"current_cost": 60}}
  ]
}
```

The input packet is not a persistent SDK session. It is the data for one run.
`intent` is an explicit input field, not a production natural-language intent
classifier. Source IDs are local fixture identifiers, not authenticated real-world
documents. The exercise assumes the supplied approved data are trusted evidence.

### 2. Define a structured report

`briefing.py` uses standard-library dataclasses. The report shape is shared by
offline execution, live structured output, validation, and saved results:

```python
@dataclass
class Finding:
    metric: Literal['growth_percent', 'gross_profit']
    value: float
    unit: Literal['percent', 'EUR']
    source_ids: list[str]

@dataclass
class Report:
    status: Status
    summary: str
    findings: list[Finding]
    gaps: list[str]
    next_step: str
```

Using a schema makes missing or malformed fields detectable. It does not establish
that a number is correct or that a citation supports a claim; those need separate
checks. Saved JSON is parsed again before any publication approval is considered.

### 3. Enforce scope in Python

The source-selection boundary in `prepare_packet()` is application-owned:

```python
if source['id'] not in APPROVED_SOURCES:
    continue
```

Only selected records reach the agent and calculator. Unknown fields, duplicate
approved source IDs, invalid numeric types, negative inputs, and non-finite
numbers are rejected. Source notes remain untrusted data; the refined contract
instructs the agent to ignore instructions embedded inside them. The validator
also rejects fabricated numeric findings even if an injected note influenced a
live response. This is a teaching example, not a comprehensive injection defense.

### 4. Run the optional real agent

`live_agent.py` imports the SDK only for live mode. The core setup is:

```python
agent = Agent(
    name='Store manager sales brief',
    instructions=instructions,
    model=model,
    output_type=Report,
    tools=[],
)
result = Runner.run_sync(
    agent,
    input=json.dumps(packet),
    max_turns=1,
    run_config=RunConfig(tracing_disabled=True),
)
```

`instructions` comes from the selected contract file; `packet` contains only the
current approved input. `output_type` requests a typed report. No action tool is
attached, so a model-generated statement cannot execute a publication. The small
one-turn design keeps this lab focused on instructions and output checking.

The SDK uses OpenAI's Responses API by default. This project demonstrates the
Python Agents SDK; it does not implement a persistent hosted Agents API service.
See the [official Agents SDK quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart)
and [agent definitions guide](https://developers.openai.com/api/docs/guides/agents/define-agents)
for installation and agent configuration.

### 5. Recalculate findings and check citations

The application reads all approved evidence, detects disagreements, and computes
expected findings using `Decimal` rather than trusting model arithmetic:

```python
growth = (revenue - previous) / previous * 100
profit = revenue - cost
rounded = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

These lines illustrate the arithmetic inside `expected_findings()`. The function
also collects the source IDs for every operand. Corroborating sources are included
instead of being silently dropped. `validate_report()` checks status, required
metrics, values, units, source IDs, gap details, and required text fields.

In `app.py`, completion is derived from the implemented checks:

```python
checks = validate_report(report, packet)
passed = all(checks.values())
```

This is different from assigning an unchecked `True`. The gate reruns these
checks at publication time instead of trusting a previously saved `passed` flag.

The checks validate the structured numeric findings, references, and selected gap
details. They do not prove every statement in free-text `summary` or `next_step`
is truthful. Read those fields during review, especially on live runs. There is no
LLM judge or automatic semantic evaluation hidden behind the pass flag.

### 6. Bind approval to an exact action

`approval.py` creates a proposal containing action, destination, and full content:

```python
canonical = json.dumps(
    action, sort_keys=True, ensure_ascii=False, separators=(',', ':')
)
token = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
```

Changing any part changes the token. The executor also checks the allowed action,
restricts the destination to `published/<case_id>.md`, rejects directory links,
and opens the target in exclusive creation mode. Only a successful file write
produces an execution result. The local gate illustrates application enforcement
without connecting the classroom exercise to an external publishing system.

### 7. Evaluate against explicit expected behavior

`expectations.json` records independent fixture answers. For example:

```json
"new_numbers": {
  "status": "ready",
  "growth_percent": -25.0,
  "gross_profit": -20.0
}
```

The evaluator actually runs each case, checks the returned report, compares it
with the fixture, saves artifacts, and lists failures. API errors count as
failures; the application never substitutes offline output for a failed live call.

`test_application.py` also deliberately tampers with reports and approval actions.
That verifies the checks reject wrong calculations, invented citations, empty
findings, fake saved success flags, changed payloads, and escaped paths.

## Test and refine the contract

Run the baseline and refined contracts against the same live cases and model:

```powershell
.\.venv\Scripts\python.exe app.py evaluate --mode live --contract baseline
.\.venv\Scripts\python.exe app.py evaluate --mode live --contract refined
```

Inspect `outputs/live-baseline/evaluation.json` and
`outputs/live-refined/evaluation.json`, then open the individual case results.
Each file records mode, contract name, selected model, original case, approved
input, returned report, and check results. Repeated runs of the same mode and
contract replace their evaluation previews; copy the folder before a new experiment
if you want to preserve an earlier run.

Do not assume the baseline will fail or the refined contract will always pass.
Measure the behavior you actually observe. Repeat live evaluations to explore
variation; one run is not a reliability estimate.

Suggested student exercise:

1. Run the offline cases and explain why `needs_input` can be a passing result.
2. Run the live baseline and identify a specific observed failure, if one occurs.
3. Copy the evaluation folder to preserve the result.
4. Edit one relevant rule or example in `contracts/refined.txt`.
5. Retest the same cases with the same model and inspect changed behavior.
6. Add a new case to `cases.json` and its expected answer to `expectations.json`.
7. Keep the old cases as regression tests. Investigate any regression before
   adopting the instruction change.

For custom files:

```powershell
python app.py evaluate --cases my_cases.json --expectations my_expectations.json
```

New cases without an expected fixture fail evaluation so missing expectations are
visible. Case IDs must use lowercase letters, digits, and underscores. Approved
source IDs are intentionally controlled by `APPROVED_SOURCES`; extending that list
is an application-policy change, not something source text or the agent can do.

## Troubleshooting and exit codes

| Symptom | What to check |
| --- | --- |
| Python command unavailable | Install Python 3.12+ and reopen the terminal; on Windows try `py -3`. |
| Missing SDK | Install `requirements.txt` using the same interpreter that runs the app. |
| Missing key or model | Set `OPENAI_API_KEY` and `OPENAI_MODEL`, or supply `--model`. |
| Live API/authentication/model error | Confirm network access, API account configuration, and model availability. The CLI reports the exception type without dumping request headers. |
| Validation fails | Read the case JSON's `checks`, compare with approved evidence, and inspect the model's text. |
| Offline baseline rejected | Offline behavior is fixed; prompt comparisons require `--mode live`. |
| Approval rejected | Preview again after any change, review the new content, and use the new token. |
| Publication file already exists | Use a new case ID or manually remove your previous classroom output. Overwrite is intentionally blocked. |

`run` and `evaluate` exit with code 0 when the implemented checks pass and code 1
on failed validation or execution. Argument parsing errors use argparse's code 2.
`publish` without a token is a successful preview (code 0), not a completed write.

The offline application, evaluation fixtures, and behavioral tests can be verified
without API access. A live model run requires your own OpenAI credentials and
project access; offline results do not establish live model quality.
