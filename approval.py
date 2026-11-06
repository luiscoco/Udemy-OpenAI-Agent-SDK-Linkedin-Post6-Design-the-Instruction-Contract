"""Local-only publishing exercise: validate, preview, bind approval, then execute."""
import hashlib
import hmac
import json
from pathlib import Path
import re

from briefing import ROOT, prepare_packet, report_from_dict, render_markdown, validate_report


def proposal(envelope: dict) -> dict:
    case_id = envelope['case']['id']
    if not isinstance(case_id, str) or not re.fullmatch(r'[a-z0-9_]+', case_id):
        raise ValueError('Invalid case id.')
    packet = prepare_packet(envelope['case'])
    report = report_from_dict(envelope['report'])
    checks = validate_report(report, packet)  # Ignore stored success flags; recheck now.
    if not all(checks.values()) or report.status not in {'ready','approval_required'}:
        raise ValueError('Only a validated, complete brief can be proposed for publication.')
    return {'action': 'publish_local_brief', 'target': f'published/{case_id}.md',
            'content': render_markdown(report, case_id)}


def approval_token(action: dict) -> str:
    canonical = json.dumps(action, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def execute(action: dict, approved_token: str | None, root: Path = ROOT) -> Path:
    if not approved_token or not hmac.compare_digest(approval_token(action), approved_token):
        raise ValueError('Approval missing or does not match the exact action, destination, and content.')
    if action.get('action') != 'publish_local_brief':
        raise ValueError('The action is not permitted.')
    if not re.fullmatch(r'published/[a-z0-9_]+\.md', action.get('target','')):
        raise ValueError('The destination is not permitted.')
    allowed = (root / 'published').resolve()
    target = (root / action['target']).resolve()
    if target.parent != allowed or not target.is_relative_to(root.resolve()):
        raise ValueError('Publication must remain inside the local published folder.')
    # Refuse directory links too; this is a local classroom gate, not a multiuser service.
    if (root / 'published').is_symlink() or (root / 'published').is_junction():
        raise ValueError('The published folder must be an ordinary local directory.')
    allowed.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8', newline='\n') as f:
        f.write(action['content'])  # Never overwrite a previously published brief.
    return target

