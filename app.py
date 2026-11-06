"""Lesson 6: run a brief, evaluate cases, or approve a local publication."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from approval import approval_token, execute, proposal
from briefing import ROOT, load_cases, offline_report, prepare_packet, render_markdown, validate_report


def generate(case: dict, mode: str, contract: str, model: str | None) -> dict:
    if mode == 'offline' and contract != 'refined':
        raise ValueError('Offline mode demonstrates fixed reference behavior; compare prompts in live mode.')
    packet = prepare_packet(case)
    if mode == 'live':
        from live_agent import run_live
        report = run_live(packet, contract, model)
    else:
        report = offline_report(packet)
    checks = validate_report(report, packet)
    return {'mode': mode, 'contract': contract, 'model': (model or os.environ.get('OPENAI_MODEL')) if mode == 'live' else None,
            'case': case, 'approved_input': packet, 'report': asdict(report),
            'checks': checks, 'passed': all(checks.values())}


def save_result(envelope: dict) -> Path:
    folder = ROOT / 'outputs' / f'{envelope["mode"]}-{envelope["contract"]}'
    folder.mkdir(parents=True, exist_ok=True)
    name = envelope['case']['id']
    path = folder / f'{name}.json'
    path.write_text(json.dumps(envelope, indent=2), encoding='utf-8')
    from briefing import report_from_dict
    text = render_markdown(report_from_dict(envelope['report']), name)
    label = 'Validated draft. Local preview only; no publication was executed.\n\n'
    if not envelope['passed']:
        label = 'VALIDATION FAILED. Review the JSON checks; do not deliver this draft.\n\n'
    (folder / f'{name}.md').write_text(label + text, encoding='utf-8')
    return path


def evaluate(args) -> int:
    expectations = json.loads(args.expectations.read_text(encoding='utf-8'))
    rows = []
    for case in load_cases(args.cases):
        try:
            envelope = generate(case, args.mode, args.contract, args.model)
            expected = expectations.get(case['id'])
            observed = envelope['report']
            numeric = {f['metric']:f['value'] for f in observed['findings']}
            fixture_ok = expected is not None and observed['status'] == expected.get('status') and all(
                abs(numeric.get(metric, float('inf')) - value) < 0.000001
                for metric,value in expected.items() if metric != 'status')
            envelope['checks']['expected_fixture'] = fixture_ok
            envelope['passed'] = all(envelope['checks'].values())
            path = save_result(envelope)
            row = {'case':case['id'], 'status':observed['status'], 'passed':envelope['passed'],
                   'failed_checks':[key for key,ok in envelope['checks'].items() if not ok],
                   'result':str(path.relative_to(ROOT))}
        except Exception as exc:
            # API/configuration errors are visible failures, never silently replaced with mock output.
            row = {'case':case['id'], 'passed':False, 'error_type':type(exc).__name__}
            if isinstance(exc, (ValueError, ImportError)):
                row['error'] = str(exc)
        rows.append(row)
        print(('PASS' if row['passed'] else 'FAIL') + f' {case["id"]}: {row.get("status", row.get("error_type"))}')
    folder = ROOT / 'outputs' / f'{args.mode}-{args.contract}'
    folder.mkdir(parents=True,exist_ok=True)
    summary = {'mode':args.mode, 'contract':args.contract,
               'passed':sum(r['passed'] for r in rows),'total':len(rows),'cases':rows}
    (folder/'evaluation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(f'{summary["passed"]}/{summary["total"]} passed. Results: {folder}')
    return 0 if summary['passed'] == summary['total'] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    for name in ('run','evaluate'):
        p = commands.add_parser(name)
        p.add_argument('--mode',choices=['offline','live'],default='offline')
        p.add_argument('--contract',choices=['baseline','refined'],default='refined')
        p.add_argument('--model',default=None)
        p.add_argument('--cases',type=Path,default=ROOT/'cases.json')
        if name == 'run':
            p.add_argument('--case',default='complete')
        else:
            p.add_argument('--expectations',type=Path,default=ROOT/'expectations.json')
    p = commands.add_parser('publish',help='Preview and approve a local-only publication.')
    p.add_argument('--result',required=True,type=Path)
    p.add_argument('--approve',default=None,help='Exact SHA-256 token shown by the preview.')
    args = parser.parse_args(argv)
    try:
        if args.command == 'evaluate':
            return evaluate(args)
        if args.command == 'publish':
            envelope = json.loads(args.result.read_text(encoding='utf-8'))
            action = proposal(envelope)
            print(json.dumps(action,indent=2))
            token = approval_token(action)
            if not args.approve:
                print(f'\nPreview only. No file published.\nApproval token: {token}')
                print('Review the action above, then repeat this command with --approve TOKEN.')
                return 0
            target = execute(action,args.approve)
            print(f'Execution result: created {target}')
            return 0
        cases = {c['id']:c for c in load_cases(args.cases)}
        if args.case not in cases:
            raise ValueError(f'Unknown case. Choose from: {", ".join(cases)}')
        envelope = generate(cases[args.case],args.mode,args.contract,args.model)
        path = save_result(envelope)
        print(json.dumps(envelope['report'],indent=2))
        print(f'\nValidation: {"PASS" if envelope["passed"] else "FAIL"}\nSaved: {path}')
        if not envelope['passed']:
            print('Failed checks: '+', '.join(k for k,v in envelope['checks'].items() if not v))
        return 0 if envelope['passed'] else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Error: {exc}',file=sys.stderr)
        return 1
    except Exception as exc:
        # Do not dump SDK request objects, headers, or credentials to student logs.
        print(f'Execution failed ({type(exc).__name__}). Check SDK installation, network, model access, and API account.',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
