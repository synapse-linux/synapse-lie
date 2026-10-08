# SPDX-License-Identifier: MIT
"""HOST campaign dispatch/profile checks; no lease, remote host or model."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value

point = module('pending_steering_dispatch', Path(os.environ.get('LIE_CAMPAIGN_CANDIDATE', ROOT/'tools/strix-point-campaign.py')))
host = module('pending_dispatch_profile_fixtures', ROOT/'tests/test_strix_point_steering_quality_profile.py')
HELPER = 'strix-point-steering-quality-profile.py'


class Tests(unittest.TestCase):
    def fixture(self):
        fixture = host.Profile(); self.addCleanup(fixture.doCleanups)
        campaign, receipt = fixture.fixture()
        return fixture, campaign, receipt

    def route(self, campaign):
        with patch.object(point, 'BASE', campaign.root.parent):
            return point.Campaign.modern_steering_quality(campaign)

    def test_dispatch_selects_profile_without_generic_model_or_bench(self):
        c = SimpleNamespace(m={'bench_profile': 'modern-steering-quality'},
            modern_steering_quality=Mock(return_value='selected'), verified_model=Mock())
        self.assertEqual(point.Campaign.bench(c), 'selected')
        c.modern_steering_quality.assert_called_once_with(); c.verified_model.assert_not_called()

    def test_missing_malformed_or_drifted_hash_refuses_before_source_execution(self):
        for value in (None, True, 1, '', '0'*64):
            with self.subTest(value=value):
                _fixture, c, _receipt = self.fixture(); c.m['steering_quality_helpers'][HELPER] = value
                with self.assertRaises(ValueError): self.route(c)
                c.verified_model.assert_not_called(); c.run_container.assert_not_called()

    def test_symlink_fifo_directory_profile_refuses_without_blocking_or_model(self):
        for kind in ('symlink', 'fifo', 'directory'):
            with self.subTest(kind=kind):
                _fixture, c, _receipt = self.fixture(); path = c.root/HELPER
                if kind == 'symlink':
                    path.rename(c.root/'saved-source.py'); path.symlink_to(c.root/'saved-source.py')
                else:
                    path.unlink()
                    if kind == 'fifo': os.mkfifo(path)
                    else: path.mkdir()
                with self.assertRaises(ValueError): self.route(c)
                c.verified_model.assert_not_called(); c.run_container.assert_not_called()

    def test_real_profile_provenance_refusal_precedes_model(self):
        fixture, c, receipt = self.fixture(); receipt['capture']['pairs'] = 8
        fixture.receipt(c.root, c.m, receipt)
        with self.assertRaises(RuntimeError): self.route(c)
        c.verified_model.assert_not_called(); c.run_container.assert_not_called()

    def execute(self, fixture, campaign, **kwargs):
        # The existing fixture calls profile.run. Redirect that entry into the
        # candidate; it executes a fresh immutable admitted profile module.
        with patch.object(point, 'BASE', campaign.root.parent), \
                patch.object(host.profile, 'run', side_effect=lambda c: point.Campaign.modern_steering_quality(c)):
            return fixture.execute(campaign, **kwargs)

    def test_complete_profile_70reply_review_and_model_postflight(self):
        fixture, c, _receipt = self.fixture(); proof = self.execute(fixture, c)
        self.assertEqual((proof['state'], proof['samples']), ('PASSED', 70))
        c.verified_model.assert_called_once(); c.check_model_after.assert_called_once()
        self.assertEqual(c.r['child_exit_code'], 0)

    def test_quality_failure_stays_distinct_from_native_client_failure(self):
        fixture, c, _receipt = self.fixture()
        with self.assertRaises(RuntimeError): self.execute(fixture, c, wrong=True)
        self.assertEqual(c.r['child_exit_code'], 1)
        self.assertEqual((c.r['steering_quality_result']['state'], c.r['steering_quality_result']['samples']),
                         ('QUALITY_FAILED', 70))
        c.check_model_after.assert_called_once()

    def test_source_swap_after_hash_never_executes_unchecked_bytes(self):
        _fixture, c, _receipt = self.fixture(); real = point.importlib.util.spec_from_file_location
        def swap(name, path, **kwargs):
            if name == 'lie_steering_quality_profile':
                Path(path).write_text('raise AssertionError("unchecked-source-must-never-execute")\n')
            return real(name, path, **kwargs)
        with patch.object(point.importlib.util, 'spec_from_file_location', side_effect=swap):
            with self.assertRaisesRegex(RuntimeError, 'helper content drift'): self.route(c)
        c.verified_model.assert_not_called(); c.run_container.assert_not_called()

    @unittest.skipUnless(host.NATIVE, 'Explicit real native C client with synthetic HTTP replies')
    def test_two_actual_native_clients_through_candidate_profile(self):
        fixture, c, _receipt = self.fixture(); proof = self.execute(fixture, c, native=True)
        self.assertEqual((proof['state'], proof['samples']), ('PASSED', 70))
        c.verified_model.assert_called_once(); c.check_model_after.assert_called_once()


if __name__ == '__main__': unittest.main()
