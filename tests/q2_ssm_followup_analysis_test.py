#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic log checks and read-only saved results; no GPU/model execution."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analysis = load('ssm_followup_analysis', 'tools/analyze-q2-ssm-followup.py')
fixture = load('ssm_original_fixture', 'tests/q2_ssm_row_group_analysis_test.py')


class FollowupAnalysisTests(unittest.TestCase):
    def setUp(self):
        seed = fixture.AnalysisTests()
        seed.setUp()
        self.events = seed.events
        self.plan = seed.plan

    def events_for(self, variant):
        events = copy.deepcopy(self.events)
        if variant in analysis.VARIANTS[2:]:
            for row in events:
                row['event'] = row['event'].replace('ssm_row_group_', 'ssm_compact_lds_')
            resources = [dict(event='ssm_compact_lds_resources', candidate=candidate,
                              shared_bytes=32768 if candidate else 49152, local_bytes=0,
                              registers=212 if candidate else 222, max_blocks_per_multiprocessor=2,
                              device_shared_bytes_per_multiprocessor=65536, measured_active_blocks=False)
                         for candidate in (False, True)]
            events = resources + events
        return events

    def test_each_candidate_preserves_coverage_and_identity(self):
        for variant in analysis.VARIANTS:
            with self.subTest(variant=variant):
                events = self.events_for(variant)
                report = analysis.analyze_events(events, self.plan, variant, 0)
                self.assertEqual(report['source_variant'], variant)
                self.assertEqual((len(report['replay']), len(report['oracle']), len(report['timings'])), (30, 60, 14))
                self.assertEqual(report['timings'][0]['event'], events[-15]['event'])
                self.assertTrue(report['numerical_pass'])
                self.assertAlmostEqual(report['summaries'][0]['candidate_time_change_percent'], -5)
                self.assertEqual(len(report['resources']), 0 if variant in analysis.VARIANTS[:2] else 2)

    def test_safe_numeric_and_operator_rejections_keep_timings(self):
        for variant in analysis.VARIANTS:
            for kind in ('replay', 'oracle'):
                with self.subTest(variant=variant, failure=kind):
                    events = self.events_for(variant)
                    row = next(e for e in events if e['event'].endswith('_' + kind))
                    if kind == 'replay':
                        row.update(changed_values=1, exact=False, candidate_sha256='b' * 64)
                    else:
                        row.update(relative_rms=0.003, **{'pass': False})
                    events[-1]['numerical_pass'] = False
                    result = analysis.analyze_events(events, self.plan, variant, 1)
                    self.assertFalse(result['numerical_pass'])
                    self.assertEqual(len(result['timings']), 14)

    def test_missing_writes_and_guards_stop_acceptance(self):
        for variant in analysis.VARIANTS:
            for key, value in (('unwritten_values', 1), ('guards_exact', False), ('unexpected_unused_values', 1)):
                events = self.events_for(variant)
                next(e for e in events if e['event'].endswith('_replay'))[key] = value
                with self.subTest(variant=variant, key=key), self.assertRaises(ValueError):
                    analysis.analyze_events(events, self.plan, variant, 1)

    def test_unsafe_exit_and_lost_numeric_exit_are_rejected(self):
        for variant in analysis.VARIANTS:
            for code in (1, 2, -9):
                with self.subTest(variant=variant, code=code), self.assertRaises(ValueError):
                    analysis.analyze_events(self.events_for(variant), self.plan, variant, code)

    def test_resource_metadata_cannot_claim_measured_occupancy(self):
        for update in ({'measured_active_blocks': True}, {'registers': -1},
                       {'max_blocks_per_multiprocessor': 0}, {'local_bytes': True},
                       {'device_shared_bytes_per_multiprocessor': 32768}):
            events = self.events_for('ssm-pingpong')
            events[0].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                analysis.analyze_events(events, self.plan, 'ssm-pingpong', 0)

    def test_missing_or_duplicated_resources_rejected(self):
        events = self.events_for('ssm-compact-lds')
        for bad in (events[1:], events[:1] + events):
            with self.assertRaises(ValueError):
                analysis.analyze_events(bad, self.plan, 'ssm-compact-lds', 0)

    def test_crossed_fixture_family_and_unknown_events_rejected(self):
        for variant in analysis.VARIANTS:
            events = self.events_for(variant)
            events.append(dict(event='unrelated_timing', us=1))
            with self.assertRaises(ValueError):
                analysis.analyze_events(events, self.plan, variant, 0)
        with self.assertRaises(ValueError):
            analysis.analyze_events(self.events, self.plan, 'ssm-pingpong', 0)

    def test_missing_duplicate_and_reordered_timings_rejected(self):
        variant = 'ssm-fixed-shape'
        events = self.events_for(variant)
        i = next(i for i, row in enumerate(events) if row['event'].endswith('_timing'))
        reordered = copy.deepcopy(events)
        reordered[i], reordered[i + 1] = reordered[i + 1], reordered[i]
        for bad in (events[:i] + events[i + 1:], events[:i] + [events[i]] + events[i:], reordered):
            with self.assertRaises(ValueError):
                analysis.analyze_events(bad, self.plan, variant, 0)

    def test_plan_cannot_change_reference_protocol(self):
        variant = 'ssm-fixed-shape'
        plan = dict(analysis.PROTOCOL, schema='synapse-lie.q2-ssm-followup-plan.v1',
                    host='q2-new-host', components=[dict(label='q2-new-component', mode=variant + '-check', variant=variant)],
                    arms=[dict(label='q2-new-model', mode='q2-counting-' + variant, variant=variant)])
        analysis.validate_scope(plan, variant)
        for key, value in (('prompt_tokens', 2042), ('chunk', 1024), ('context_capacity', 8192),
                           ('run_controls', True), ('full_curve', True), ('warmups', 0),
                           ('repetitions', 5), ('cooldown_seconds', 0), ('timed_decode_calls', 128),
                           ('mtp', True), ('component_expected_oracle_checks', 30)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                analysis.validate_scope(dict(plan, **{key: value}), variant)
        with self.assertRaises(ValueError):
            analysis.validate_scope(plan, 'ssm-fixed-bounds')

    def test_saved_model_readback_and_comparisons_stay_unchanged(self):
        # Read retained evidence only. No executable, compiler or model is run.
        saved = analysis.read(ROOT / 'config/q2-down-register-scatter-model-results.json')
        _, retained = analysis.hc.prior.shared.arm(ROOT / 'evidence/q2-down-register-scatter-model-r1',
                                                  'down-register-scatter')
        self.assertEqual(retained['measurements'], saved['model']['measurements'])
        references = {key: saved['references'][key] for key in ('fixed_q2', 'fixed_ud')}
        references['same_saved_candidate'] = saved['model']
        changes = analysis.measurement_changes(retained, references)
        for key in ('fixed_q2', 'fixed_ud'):
            self.assertEqual(changes[key], saved['candidate_median_change_percent'][key])
        self.assertTrue(all(value == 0 for value in changes['same_saved_candidate'].values()))
        self.assertLess(changes['fixed_ud']['prefill_tok_s'], 0)
        self.assertGreater(changes['fixed_ud']['decode_steps_s'], 0)

    def test_invalid_model_timing_cannot_show_a_gain(self):
        saved = analysis.read(ROOT / 'config/q2-down-register-scatter-model-results.json')
        for value in (float('nan'), float('inf'), 0, -1):
            candidate = copy.deepcopy(saved['model'])
            candidate['measurements']['prefill_tok_s']['median'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analysis.measurement_changes(candidate, {'fixed_ud': saved['references']['fixed_ud']})


if __name__ == '__main__':
    unittest.main()
