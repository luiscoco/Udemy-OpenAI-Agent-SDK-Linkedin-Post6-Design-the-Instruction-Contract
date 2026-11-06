"""Behavioral checks with independent expected answers and tampered outputs."""
import copy
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import unittest
import uuid

from approval import approval_token, execute, proposal
from app import generate
from briefing import ROOT, load_cases, offline_report, prepare_packet, report_from_dict, validate_report


@contextmanager
def test_folder():
    # Normal inherited permissions also work inside Windows managed workspaces.
    path = ROOT / f'.test_{uuid.uuid4().hex}'
    path.mkdir()
    try:
        yield path
    finally:
        resolved = path.resolve()
        if resolved.parent != ROOT.resolve() or not resolved.name.startswith('.test_'):
            raise RuntimeError('Test cleanup escaped the project folder.')
        shutil.rmtree(resolved)


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c['id']:c for c in load_cases()}

    def packet(self, case='complete'):
        return prepare_packet(self.cases[case])

    def test_known_math_and_units(self):
        report = offline_report(self.packet())
        self.assertEqual(report.status,'ready')
        self.assertEqual([(f.metric,f.value,f.unit) for f in report.findings],
                         [('growth_percent',25.0,'percent'),('gross_profit',40.0,'EUR')])

    def test_loss_and_decline_are_valid(self):
        findings = offline_report(self.packet('new_numbers')).findings
        self.assertEqual([f.value for f in findings],[-25.0,-20.0])

    def test_missing_and_conflicting_inputs_stop_completion(self):
        for case,status,field in [('missing_cost','needs_input','current_cost'),
                                  ('conflicting_totals','conflict','current_revenue')]:
            report = offline_report(self.packet(case))
            self.assertEqual(report.status,status)
            self.assertFalse(report.findings)
            self.assertIn(field,' '.join(report.gaps))

    def test_zero_baseline_is_not_zero_percent(self):
        report = offline_report(self.packet('zero_baseline'))
        self.assertEqual(report.status,'needs_input')
        self.assertFalse(report.findings)
        self.assertIn('zero',' '.join(report.gaps))

    def test_policy_statuses_and_precedence(self):
        self.assertEqual(offline_report(self.packet('publish_request')).status,'approval_required')
        self.assertEqual(offline_report(self.packet('publish_missing_cost')).status,'needs_input')
        self.assertEqual(offline_report(self.packet('out_of_scope')).status,'out_of_scope')

    def test_unapproved_sources_are_removed(self):
        packet = self.packet('source_injection')
        self.assertEqual({s['id'] for s in packet['sources']},{'sales-ledger','cost-ledger'})
        self.assertEqual([f.value for f in offline_report(packet).findings],[25.0,40.0])

    def test_wrong_calculation_fails_even_with_valid_shape(self):
        packet = self.packet()
        report = offline_report(packet)
        report.findings[1].value = 999.0
        self.assertFalse(validate_report(report,packet)['values_and_units'])

    def test_fabricated_or_incomplete_citations_fail(self):
        packet = self.packet()
        report = offline_report(packet)
        report.findings[0].source_ids = ['invented-source']
        self.assertFalse(validate_report(report,packet)['citations_support_values'])
        packet = self.packet('corroborating_sources')
        report = offline_report(packet)
        self.assertEqual(report.findings[0].source_ids,['sales-audit','sales-ledger'])
        report.findings[0].source_ids.remove('sales-audit')
        self.assertFalse(validate_report(report,packet)['citations_support_values'])

    def test_fake_success_and_empty_findings_fail(self):
        packet = self.packet('missing_cost')
        report = offline_report(packet)
        report.status = 'ready'
        self.assertFalse(validate_report(report,packet)['status_matches_evidence'])
        report = offline_report(self.packet())
        report.findings.clear()
        self.assertFalse(validate_report(report,self.packet())['required_metrics'])

    def test_missing_schema_field_is_rejected(self):
        data = asdict(offline_report(self.packet()))
        del data['gaps']
        with self.assertRaises(ValueError):
            report_from_dict(data)

    def test_approval_binds_action_target_and_content(self):
        envelope = generate(self.cases['publish_request'],'offline','refined',None)
        action = proposal(envelope)
        token = approval_token(action)
        with test_folder() as directory:
            root = Path(directory)
            for field,value in [('action','email'),('target','published/another.md'),('content','Changed body')]:
                changed = {**action,field:value}
                with self.assertRaises(ValueError):
                    execute(changed,token,root)
            with self.assertRaises(ValueError):
                execute(action,None,root)
            self.assertFalse((root/'published').exists())
            target = execute(action,token,root)
            self.assertEqual(target.read_text(encoding='utf-8'),action['content'])
            with self.assertRaises(FileExistsError):
                execute(action,token,root)

    def test_gate_rechecks_evidence_instead_of_saved_pass_flag(self):
        envelope = generate(self.cases['complete'],'offline','refined',None)
        envelope['report']['findings'][0]['value'] = 0
        envelope['passed'] = True
        with self.assertRaises(ValueError):
            proposal(envelope)

    def test_path_escape_blocked_even_with_matching_hash(self):
        action = {'action':'publish_local_brief','target':'../escape.md','content':'Hello'}
        with test_folder() as directory:
            with self.assertRaises(ValueError):
                execute(action,approval_token(action),Path(directory))

    def test_malformed_inputs_rejected(self):
        for bad in [True,-1,float('nan'),float('inf'),'100']:
            case = copy.deepcopy(self.cases['complete'])
            case['sources'][0]['values']['current_revenue'] = bad
            with self.assertRaises(ValueError):
                prepare_packet(case)

    def test_all_case_fixtures(self):
        expected = json.loads((ROOT/'expectations.json').read_text(encoding='utf-8'))
        for name,case in self.cases.items():
            with self.subTest(case=name):
                envelope = generate(case,'offline','refined',None)
                self.assertTrue(envelope['passed'])
                self.assertEqual(envelope['report']['status'],expected[name]['status'])
                metrics = {f['metric']:f['value'] for f in envelope['report']['findings']}
                for metric,value in expected[name].items():
                    if metric != 'status':
                        self.assertEqual(metrics[metric],value)


if __name__ == '__main__':
    unittest.main()
