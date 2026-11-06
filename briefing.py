"""Domain rules, evidence validation, and a deliberately deterministic offline demo."""
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
import json
import math
from pathlib import Path
import re
from typing import Literal

ROOT = Path(__file__).resolve().parent
APPROVED_SOURCES = frozenset({'sales-ledger', 'cost-ledger', 'sales-audit'})
FIELDS = ('previous_revenue', 'current_revenue', 'current_cost')
Status = Literal['ready', 'needs_input', 'conflict', 'approval_required', 'out_of_scope']


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


def load_cases(path: Path | None = None) -> list[dict]:
    cases = json.loads((path or ROOT / 'cases.json').read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('Cases must be a nonempty JSON array.')
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not re.fullmatch(r'[a-z0-9_]+', case.get('id', '')):
            raise ValueError('Every case needs a lowercase id containing letters, digits, or underscores.')
        if case['id'] in ids:
            raise ValueError('Case IDs must be unique.')
        ids.add(case['id'])
        prepare_packet(case)  # Validate source structure at the input boundary.
    return cases


def prepare_packet(case: dict) -> dict:
    if case.get('intent') not in {'brief', 'publish', 'unrelated'}:
        raise ValueError('intent must be brief, publish, or unrelated.')
    if not isinstance(case.get('question'), str) or not case['question'].strip():
        raise ValueError('question must be nonempty text.')
    if not isinstance(case.get('sources'), list):
        raise ValueError('sources must be an array.')
    selected, seen = [], set()
    for source in case['sources']:
        if not isinstance(source, dict) or not isinstance(source.get('id'), str):
            raise ValueError('Each source needs a string id.')
        if source['id'] not in APPROVED_SOURCES:
            continue  # An unapproved record never reaches the agent or calculator.
        if source['id'] in seen:
            raise ValueError('Source IDs must be unique within a case.')
        seen.add(source['id'])
        values = source.get('values')
        if not isinstance(values, dict) or set(values) - set(FIELDS):
            raise ValueError('Source values must contain only the documented revenue/cost fields.')
        for value in values.values():
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError('Amounts must be finite, nonnegative numbers or null.')
        note = source.get('note', '')
        if not isinstance(note, str):
            raise ValueError('Source notes must be text.')
        selected.append({'id': source['id'], 'values': values.copy(), 'note': note})
    return {'intent': case['intent'], 'question': case['question'], 'sources': selected}


def evidence(packet: dict) -> tuple[dict, dict, list[str], list[str]]:
    values, citations, missing, conflicts = {}, {}, [], []
    for field in FIELDS:
        found = [(Decimal(str(s['values'][field])), s['id']) for s in packet['sources']
                 if s['values'].get(field) is not None]
        unique = {value for value, _ in found}
        if len(unique) > 1:
            conflicts.append(field)
        elif not found:
            missing.append(field)
        else:
            values[field] = found[0][0]
            citations[field] = {source for _, source in found}
    return values, citations, missing, conflicts


def expected_status(packet: dict) -> tuple[Status, list[str]]:
    if packet['intent'] == 'unrelated':
        return 'out_of_scope', ['This request is outside the sales-brief scope.']
    values, _, missing, conflicts = evidence(packet)
    if conflicts:
        return 'conflict', [f'Conflicting approved values for {field}; reconcile the sources.' for field in conflicts]
    if missing:
        return 'needs_input', [f'Missing {field}; supply the approved value.' for field in missing]
    if values['previous_revenue'] == 0:
        return 'needs_input', ['growth_percent is undefined because previous_revenue is zero; revise the comparison.']
    if packet['intent'] == 'publish':
        return 'approval_required', ['Publication requires approval of the exact destination and content.']
    return 'ready', []


def expected_findings(packet: dict) -> list[Finding]:
    values, citations, _, _ = evidence(packet)
    revenue, previous, cost = (values[k] for k in ('current_revenue', 'previous_revenue', 'current_cost'))
    money = lambda n: float(n.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    return [
        Finding('growth_percent', money((revenue-previous)/previous*100), 'percent',
                sorted(citations['current_revenue'] | citations['previous_revenue'])),
        Finding('gross_profit', money(revenue-cost), 'EUR',
                sorted(citations['current_revenue'] | citations['current_cost'])),
    ]


def offline_report(packet: dict) -> Report:
    """Reference behavior for learning the pipeline; this does NOT execute a prompt."""
    status, gaps = expected_status(packet)
    if status in {'ready', 'approval_required'}:
        findings = expected_findings(packet)
        growth, profit = findings
        summary = (f'For the store manager: revenue growth is {growth.value:.2f}% '
                   f'and gross profit is EUR {profit.value:.2f}.')
        next_step = 'Review the brief.' if status == 'ready' else 'Review the proposed publication and approve its exact payload.'
    else:
        findings = []
        summary = 'The brief cannot be completed with the current request and approved evidence.'
        next_step = ' '.join(gaps)
    return Report(status, summary, findings, gaps, next_step)


def report_from_dict(data: dict) -> Report:
    """Reject malformed saved reports before an approval can be considered."""
    if not isinstance(data, dict) or set(data) != {'status','summary','findings','gaps','next_step'}:
        raise ValueError('Report fields do not match the required schema.')
    if data['status'] not in {'ready','needs_input','conflict','approval_required','out_of_scope'}:
        raise ValueError('Unknown report status.')
    if not all(isinstance(data[k], str) and data[k].strip() for k in ('summary','next_step')):
        raise ValueError('summary and next_step must be nonempty text.')
    if not isinstance(data['gaps'], list) or not all(isinstance(g, str) and g.strip() for g in data['gaps']):
        raise ValueError('gaps must be an array of nonempty strings.')
    if not isinstance(data['findings'], list):
        raise ValueError('findings must be an array.')
    findings = []
    for f in data['findings']:
        if not isinstance(f, dict) or set(f) != {'metric','value','unit','source_ids'}:
            raise ValueError('Finding fields do not match the schema.')
        if f['metric'] not in {'growth_percent','gross_profit'} or f['unit'] not in {'percent','EUR'}:
            raise ValueError('Unknown metric or unit.')
        if type(f['value']) not in (int, float) or not math.isfinite(f['value']):
            raise ValueError('Finding value must be a finite number.')
        if not isinstance(f['source_ids'], list) or not all(isinstance(s,str) for s in f['source_ids']):
            raise ValueError('source_ids must be a list of strings.')
        findings.append(Finding(**f))
    return Report(data['status'], data['summary'], findings, data['gaps'], data['next_step'])


def validate_report(report: Report, packet: dict) -> dict[str, bool]:
    # These are computed checks, not model-provided success flags.
    report = report_from_dict(asdict(report))
    status, expected_gaps = expected_status(packet)
    checks = {'status_matches_evidence': report.status == status,
              'gaps_disclosed': bool(report.gaps) if expected_gaps else not report.gaps,
              'summary_present': bool(report.summary.strip()),
              'next_step_present': bool(report.next_step.strip())}
    needs_findings = status in {'ready','approval_required'}
    expected = {f.metric: f for f in expected_findings(packet)} if needs_findings else {}
    actual = {f.metric: f for f in report.findings}
    checks['required_metrics'] = len(report.findings) == len(actual) and set(actual) == set(expected)
    checks['values_and_units'] = set(actual) == set(expected) and all(
        math.isclose(actual[k].value, f.value, rel_tol=0, abs_tol=0.000001) and actual[k].unit == f.unit
        for k, f in expected.items())
    checks['citations_support_values'] = set(actual) == set(expected) and all(
        set(actual[k].source_ids) == set(f.source_ids) and len(actual[k].source_ids) == len(set(actual[k].source_ids))
        for k, f in expected.items())
    _, _, missing, conflicts = evidence(packet)
    gap_text = ' '.join(report.gaps).lower()
    details = conflicts if status == 'conflict' else missing if status == 'needs_input' else []
    checks['gap_details'] = all(field in gap_text for field in details)
    if status == 'needs_input' and not missing:
        checks['gap_details'] = 'zero' in gap_text and ('previous_revenue' in gap_text or 'growth' in gap_text)
    if status == 'approval_required':
        checks['gap_details'] = 'approv' in gap_text
    return checks


def render_markdown(report: Report, case_id: str) -> str:
    lines = [f'# Sales brief: {case_id}', '', f'Status: {report.status}', '',
             '## Summary', '', report.summary, '', '## Findings', '']
    for f in report.findings:
        lines.append(f'- {f.metric}: {f.value:.2f} {f.unit}. Sources: {", ".join(f.source_ids)}.')
    if not report.findings:
        lines.append('No numeric findings are delivered until the input issue is resolved.')
    lines += ['', '## Gaps', '', *[f'- {g}' for g in report.gaps]]
    if not report.gaps:
        lines.append('None identified by the implemented checks.')
    lines += ['', '## Next step', '', report.next_step, '']
    return '\n'.join(lines)
