#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Refuse unsafe experiment/archive combinations before any staging or SSH."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

path = Path(__file__).resolve().parents[1] / 'tools/q2-remote.py'
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location('q2_remote', path)
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)


class RemoteGuardTests(unittest.TestCase):
    def test_ssm_channel_bounds_matching_modes_only(self):
        variant = 'ssm-channel-bounds'
        for mode in ('cpu', 'q2-profile', 'q2-bench', 'q2-curve'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Q2 SSM follow-up requires its component or matched historical counting provider')
        component = [variant + '-check', 'q2-fixture', '--source-variant', variant]
        self.refuse([variant + '-check', 'q2-fixture'], 'Q2 SSM follow-up requires')
        self.refuse(component + ['--rebuild-mmq'], 'Q2 SSM follow-up component builds')
        model = ['q2-counting-' + variant, 'q2-fixture', '--source-variant', variant]
        self.refuse(model, 'Historical counting requires a full MMQ rebuild')
        for argv in (component, model + ['--rebuild-mmq']):
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_ssm_channel_registry_preserves_historical_registry(self):
        historical = json.loads((remote.ROOT / remote.SSM_FOLLOWUP_MANIFEST).read_text())
        current = json.loads((remote.ROOT / remote.SSM_CHANNEL_MANIFEST).read_text())
        self.assertNotIn('ssm-channel-bounds', historical['variants'])
        self.assertEqual(set(current['variants']), {'ssm-channel-bounds'})
        self.assertEqual(current['variants']['ssm-channel-bounds']['event_prefix'], 'ssm_row_group')

    def test_half_fixed_width_manifest_binding(self):
        self.assertEqual(remote.HALF_FIXED_WIDTH_MANIFEST,
                         'config/q2-half-fixed-width-source.json')
        self.assertTrue((remote.ROOT / remote.HALF_FIXED_WIDTH_MANIFEST).is_file())

    def test_half_fixed_width_new_component_or_matched_counting_only(self):
        variant = 'half-fixed-width'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 half fixed width requires its component or matched historical counting provider')
        self.refuse([remote.HALF_FIXED_WIDTH_MODE, 'q2-fixture'], 'Q2 half fixed width requires')
        base = [remote.HALF_FIXED_WIDTH_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 half fixed width component builds')
        for mode in (remote.HALF_FIXED_WIDTH_MODE, 'q2-counting-half-fixed-width'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_half_consumer_eight_manifest_binding(self):
        self.assertEqual(remote.HALF_CONSUMER_EIGHT_MANIFEST,
                         'config/q2-half-consumer-eight-source.json')
        self.assertTrue((remote.ROOT / remote.HALF_CONSUMER_EIGHT_MANIFEST).is_file())

    def test_half_consumer_eight_new_component_or_matched_counting_only(self):
        variant = 'half-consumer-eight'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 half consumer eight requires its component or matched historical counting provider')
        self.refuse([remote.HALF_CONSUMER_EIGHT_MODE, 'q2-fixture'], 'Q2 half consumer eight requires')
        base = [remote.HALF_CONSUMER_EIGHT_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 half consumer eight component builds')
        for mode in (remote.HALF_CONSUMER_EIGHT_MODE, 'q2-counting-half-consumer-eight'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_ssm_row_group_manifest_binding(self):
        self.assertEqual(remote.SSM_ROW_GROUP_MANIFEST,
                         'config/q2-ssm-row-group-compose-source.json')
        self.assertTrue((remote.ROOT / remote.SSM_ROW_GROUP_MANIFEST).is_file())

    def test_ssm_row_group_new_component_or_matched_counting_only(self):
        variant = 'ssm-row-group'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 SSM row group requires its component or matched historical counting provider')
        self.refuse([remote.SSM_ROW_GROUP_MODE, 'q2-fixture'], 'Q2 SSM row group requires')
        base = [remote.SSM_ROW_GROUP_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 SSM row group component builds')
        for mode in (remote.SSM_ROW_GROUP_MODE, 'q2-counting-ssm-row-group'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_down_register_scatter_manifest_binding(self):
        self.assertEqual(remote.DOWN_REGISTER_SCATTER_MANIFEST,
                         'config/q2-down-register-scatter-pair-source.json')
        self.assertTrue((remote.ROOT / remote.DOWN_REGISTER_SCATTER_MANIFEST).is_file())

    def test_down_register_scatter_new_component_or_matched_counting_only(self):
        variant = 'down-register-scatter'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 down register scatter requires its component or matched historical counting provider')
        self.refuse([remote.DOWN_REGISTER_SCATTER_MODE, 'q2-fixture'], 'Q2 down register scatter requires')
        base = [remote.DOWN_REGISTER_SCATTER_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 down register scatter component builds')
        for mode in (remote.DOWN_REGISTER_SCATTER_MODE, 'q2-counting-down-register-scatter'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_down_half_vector_manifest_binding(self):
        self.assertEqual(remote.DOWN_HALF_VECTOR_MANIFEST,
                         'config/q2-down-half-vector-source.json')
        self.assertTrue((remote.ROOT / remote.DOWN_HALF_VECTOR_MANIFEST).is_file())

    def test_down_half_vector_new_component_or_matched_counting_only(self):
        variant = 'down-half-vector'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 down half vector requires its component or matched historical counting provider')
        self.refuse([remote.DOWN_HALF_VECTOR_MODE, 'q2-fixture'], 'Q2 down half vector requires')
        base = [remote.DOWN_HALF_VECTOR_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 down half vector component builds')
        for mode in (remote.DOWN_HALF_VECTOR_MODE, 'q2-counting-down-half-vector'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_down_half_pair_manifest_binding(self):
        self.assertEqual(remote.DOWN_HALF_PAIR_MANIFEST,
                         'config/q2-down-half-pair-source.json')
        self.assertTrue((remote.ROOT / remote.DOWN_HALF_PAIR_MANIFEST).is_file())

    def test_down_half_pair_new_component_or_matched_counting_only(self):
        variant = 'down-half-pair'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 down half pair requires its component or matched historical counting provider')
        self.refuse([remote.DOWN_HALF_PAIR_MODE, 'q2-fixture'], 'Q2 down half pair requires')
        base = [remote.DOWN_HALF_PAIR_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 down half pair component builds')
        for mode in (remote.DOWN_HALF_PAIR_MODE, 'q2-counting-down-half-pair'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_down_half_storage_manifest_binding(self):
        self.assertEqual(remote.DOWN_HALF_STORAGE_MANIFEST,
                         'config/q2-down-half-storage-source.json')
        self.assertTrue((remote.ROOT / remote.DOWN_HALF_STORAGE_MANIFEST).is_file())

    def test_down_half_storage_new_component_or_matched_counting_only(self):
        variant = 'down-half-storage'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 down half storage requires its component or matched historical counting provider')
        self.refuse([remote.DOWN_HALF_STORAGE_MODE, 'q2-fixture'], 'Q2 down half storage requires')
        base = [remote.DOWN_HALF_STORAGE_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 down half storage component builds')
        for mode in (remote.DOWN_HALF_STORAGE_MODE, 'q2-counting-down-half-storage'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_down_live_stage_manifest_binding(self):
        self.assertEqual(remote.DOWN_LIVE_STAGE_MANIFEST,
                         'config/q2-down-live-stage-source.json')
        self.assertTrue((remote.ROOT / remote.DOWN_LIVE_STAGE_MANIFEST).is_file())

    def test_down_live_stage_new_component_or_matched_counting_only(self):
        variant = 'down-live-stage'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 down live stage requires its component or matched historical counting provider')
        self.refuse([remote.DOWN_LIVE_STAGE_MODE, 'q2-fixture'], 'Q2 down live stage requires')
        base = [remote.DOWN_LIVE_STAGE_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 down live stage component builds')
        for mode in (remote.DOWN_LIVE_STAGE_MODE, 'q2-counting-down-live-stage'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_down_output_reuse_manifest_binding(self):
        self.assertEqual(remote.DOWN_OUTPUT_REUSE_MANIFEST,
                         'config/q2-down-output-reuse-source.json')
        self.assertTrue((remote.ROOT / remote.DOWN_OUTPUT_REUSE_MANIFEST).is_file())

    def test_down_output_reuse_new_component_or_matched_counting_only(self):
        variant = 'down-output-reuse'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 down output reuse requires its component or matched historical counting provider')
        self.refuse([remote.DOWN_OUTPUT_REUSE_MODE, 'q2-fixture'], 'Q2 down output reuse requires')
        base = [remote.DOWN_OUTPUT_REUSE_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 down output reuse component builds')
        for mode in (remote.DOWN_OUTPUT_REUSE_MODE, 'q2-counting-down-output-reuse'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_wide_pair_manifest_binding(self):
        self.assertEqual(remote.IQ2_WIDE_PAIR_MANIFEST,
                         'config/q2-iq2-wide-pair-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_WIDE_PAIR_MANIFEST).is_file())

    def test_iq2_wide_pair_new_component_or_matched_counting_only(self):
        variant = 'iq2-wide-pair'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 wide pair requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_WIDE_PAIR_MODE, 'q2-fixture'], 'IQ2 wide pair requires')
        base = [remote.IQ2_WIDE_PAIR_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 wide pair component builds')
        for mode in (remote.IQ2_WIDE_PAIR_MODE, 'q2-counting-iq2-wide-pair'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_lane_commit_manifest_binding(self):
        self.assertEqual(remote.IQ2_LANE_COMMIT_MANIFEST,
                         'config/q2-iq2-lane-commit-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_LANE_COMMIT_MANIFEST).is_file())

    def test_iq2_lane_commit_new_component_or_matched_counting_only(self):
        variant = 'iq2-lane-commit'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 lane commit requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_LANE_COMMIT_MODE, 'q2-fixture'], 'IQ2 lane commit requires')
        base = [remote.IQ2_LANE_COMMIT_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 lane commit component builds')
        for mode in (remote.IQ2_LANE_COMMIT_MODE, 'q2-counting-iq2-lane-commit'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_short_tiles_manifest_binding(self):
        self.assertEqual(remote.IQ2_SHORT_TILES_MANIFEST,
                         'config/q2-iq2-short-tiles-source-v2.json')
        self.assertTrue((remote.ROOT / remote.IQ2_SHORT_TILES_MANIFEST).is_file())

    def test_iq2_short_tiles_new_component_or_matched_counting_only(self):
        variant = 'iq2-short-tiles'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-iq2-raw-prefetch', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 short tiles requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_SHORT_TILES_MODE, 'q2-fixture'], 'IQ2 short tiles requires')
        base = [remote.IQ2_SHORT_TILES_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 short tiles component builds')
        for mode in (remote.IQ2_SHORT_TILES_MODE, 'q2-counting-iq2-short-tiles'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_live_compose_manifest_binding(self):
        self.assertEqual(remote.IQ2_LIVE_COMPOSE_MANIFEST,
                         'config/q2-iq2-live-compose-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_LIVE_COMPOSE_MANIFEST).is_file())

    def test_iq2_live_compose_matched_new_counting_only(self):
        variant = 'iq2-live-compose'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'scaled-tiles-check', 'q2-counting-scaled-selective',
                     'q2-counting-iq2-raw-prefetch'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 live composition requires its matched historical counting provider')
        argv = ['q2-counting-iq2-live-compose', 'q2-fixture', '--source-variant', variant]
        self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
        argv += ['--rebuild-mmq']
        self.refuse(argv + ['--detach'], 'Persistent launch is limited')
        self.refuse(argv + ['--native-curve'], 'Native curve requires')
        with patch.object(sys, 'argv', [str(path), *argv]), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_iq2_raw_selective_manifest_binding(self):
        self.assertEqual(remote.IQ2_RAW_SELECTIVE_MANIFEST,
                         'config/q2-iq2-raw-selective-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_RAW_SELECTIVE_MANIFEST).is_file())

    def test_iq2_raw_selective_matched_new_counting_only(self):
        variant = 'iq2-raw-selective'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'scaled-tiles-check', 'q2-counting-scaled-selective',
                     'q2-counting-iq2-raw-prefetch'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 raw selective composition requires its matched historical counting provider')
        argv = ['q2-counting-iq2-raw-selective', 'q2-fixture', '--source-variant', variant]
        self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
        argv += ['--rebuild-mmq']
        self.refuse(argv + ['--detach'], 'Persistent launch is limited')
        self.refuse(argv + ['--native-curve'], 'Native curve requires')
        with patch.object(sys, 'argv', [str(path), *argv]), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_q8_mirror_manifest_binding(self):
        self.assertEqual(remote.Q8_MIRROR_MANIFEST,
                         'config/q2-q8-mirror-source.json')
        self.assertTrue((remote.ROOT / remote.Q8_MIRROR_MANIFEST).is_file())

    def test_q8_mirror_new_component_or_matched_counting_only(self):
        variant = 'q8-mirror'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q8 mirror requires its component or matched historical counting provider')
        self.refuse([remote.Q8_MIRROR_MODE, 'q2-fixture'], 'Q8 mirror requires')
        base = [remote.Q8_MIRROR_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q8 mirror component builds')
        for mode in (remote.Q8_MIRROR_MODE, 'q2-counting-q8-mirror'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_scaled_wave_pack_manifest_binding(self):
        self.assertEqual(remote.SCALED_WAVE_PACK_MANIFEST,
                         'config/q2-scaled-wave-pack-source.json')
        self.assertTrue((remote.ROOT / remote.SCALED_WAVE_PACK_MANIFEST).is_file())

    def test_scaled_wave_pack_new_component_or_matched_counting_only(self):
        variant = 'scaled-wave-pack'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Scaled wave pack requires its component or matched historical counting provider')
        self.refuse([remote.SCALED_WAVE_PACK_MODE, 'q2-fixture'], 'Scaled wave pack requires')
        base = [remote.SCALED_WAVE_PACK_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Scaled wave pack component builds')
        for mode in (remote.SCALED_WAVE_PACK_MODE, 'q2-counting-scaled-wave-pack'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_scaled_expert_order_manifest_binding(self):
        self.assertEqual(remote.SCALED_EXPERT_ORDER_MANIFEST,
                         'config/q2-scaled-expert-order-source.json')
        self.assertTrue((remote.ROOT / remote.SCALED_EXPERT_ORDER_MANIFEST).is_file())

    def test_scaled_expert_order_new_component_or_matched_counting_only(self):
        variant = 'scaled-expert-order'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Scaled expert order requires its component or matched historical counting provider')
        self.refuse([remote.SCALED_EXPERT_ORDER_MODE, 'q2-fixture'], 'Scaled expert order requires')
        base = [remote.SCALED_EXPERT_ORDER_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Scaled expert order component builds')
        for mode in (remote.SCALED_EXPERT_ORDER_MODE, 'q2-counting-scaled-expert-order'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_compact_expert_chain_manifest_binding(self):
        self.assertEqual(remote.COMPACT_EXPERT_CHAIN_MANIFEST,
                         'config/q2-compact-expert-chain-source.json')
        self.assertTrue((remote.ROOT / remote.COMPACT_EXPERT_CHAIN_MANIFEST).is_file())

    def test_compact_expert_chain_new_component_or_matched_counting_only(self):
        variant = 'compact-expert-chain'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Compact expert chain requires its component or matched historical counting provider')
        self.refuse([remote.COMPACT_EXPERT_CHAIN_MODE, 'q2-fixture'], 'Compact expert chain requires')
        base = [remote.COMPACT_EXPERT_CHAIN_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Compact expert chain component builds')
        for mode in (remote.COMPACT_EXPERT_CHAIN_MODE, 'q2-counting-compact-expert-chain'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_producer_q8_manifest_binding(self):
        self.assertEqual(remote.PRODUCER_Q8_MANIFEST,
                         'config/q2-producer-q8-source-v2.json')
        self.assertTrue((remote.ROOT / remote.PRODUCER_Q8_MANIFEST).is_file())

    def test_producer_q8_new_component_or_matched_counting_only(self):
        variant = 'producer-q8'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Producer Q8 requires its component or matched historical counting provider')
        self.refuse([remote.PRODUCER_Q8_MODE, 'q2-fixture'], 'Producer Q8 requires')
        base = [remote.PRODUCER_Q8_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Producer Q8 component builds')
        for mode in (remote.PRODUCER_Q8_MODE, 'q2-counting-producer-q8'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_shared_q8_pair_manifest_binding(self):
        self.assertEqual(remote.SHARED_Q8_PAIR_MANIFEST,
                         'config/q2-shared-q8-pair-source.json')
        self.assertTrue((remote.ROOT / remote.SHARED_Q8_PAIR_MANIFEST).is_file())

    def test_shared_q8_pair_new_component_or_matched_counting_only(self):
        variant = 'shared-q8-pair'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Shared Q8 pair requires its component or matched historical counting provider')
        self.refuse([remote.SHARED_Q8_PAIR_MODE, 'q2-fixture'], 'Shared Q8 pair requires')
        base = [remote.SHARED_Q8_PAIR_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Shared Q8 pair component builds')
        for mode in (remote.SHARED_Q8_PAIR_MODE, 'q2-counting-shared-q8-pair'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_q8_aligned_pair_manifest_binding(self):
        self.assertEqual(remote.Q8_ALIGNED_PAIR_MANIFEST,
                         'config/q2-q8-aligned-pair-source.json')
        self.assertTrue((remote.ROOT / remote.Q8_ALIGNED_PAIR_MANIFEST).is_file())

    def test_q8_aligned_pair_new_component_or_matched_counting_only(self):
        variant = 'q8-aligned-pair'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q8 aligned pair requires its component or matched historical counting provider')
        self.refuse([remote.Q8_ALIGNED_PAIR_MODE, 'q2-fixture'], 'Q8 aligned pair requires')
        base = [remote.Q8_ALIGNED_PAIR_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q8 aligned pair component builds')
        for mode in (remote.Q8_ALIGNED_PAIR_MODE, 'q2-counting-q8-aligned-pair'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_q8_k16_phases_manifest_binding(self):
        self.assertEqual(remote.Q8_K16_PHASES_MANIFEST,
                         'config/q2-q8-k16-phases-source.json')
        self.assertTrue((remote.ROOT / remote.Q8_K16_PHASES_MANIFEST).is_file())

    def test_q8_k16_phases_new_component_or_matched_counting_only(self):
        variant = 'q8-k16-phases'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q8 K16 phases requires its component or matched historical counting provider')
        self.refuse([remote.Q8_K16_PHASES_MODE, 'q2-fixture'], 'Q8 K16 phases requires')
        base = [remote.Q8_K16_PHASES_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q8 K16 phases component builds')
        for mode in (remote.Q8_K16_PHASES_MODE, 'q2-counting-q8-k16-phases'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_down_raw_prefetch_manifest_binding(self):
        self.assertEqual(remote.DOWN_RAW_PREFETCH_MANIFEST,
                         'config/q2-down-raw-prefetch-source.json')
        self.assertTrue((remote.ROOT / remote.DOWN_RAW_PREFETCH_MANIFEST).is_file())

    def test_down_raw_prefetch_new_component_or_matched_counting_only(self):
        variant = 'down-raw-prefetch'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q2 down raw prefetch requires its component or matched historical counting provider')
        self.refuse([remote.DOWN_RAW_PREFETCH_MODE, 'q2-fixture'], 'Q2 down raw prefetch requires')
        base = [remote.DOWN_RAW_PREFETCH_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q2 down raw prefetch component builds')
        for mode in (remote.DOWN_RAW_PREFETCH_MODE, 'q2-counting-down-raw-prefetch'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_fused_grid_manifest_binding(self):
        self.assertEqual(remote.IQ2_FUSED_GRID_MANIFEST,
                         'config/q2-iq2-fused-grid-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_FUSED_GRID_MANIFEST).is_file())

    def test_iq2_fused_grid_new_component_or_matched_counting_only(self):
        variant = 'iq2-fused-grid'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 fused grid requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_FUSED_GRID_MODE, 'q2-fixture'], 'IQ2 fused grid requires')
        base = [remote.IQ2_FUSED_GRID_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 fused grid component builds')
        for mode in (remote.IQ2_FUSED_GRID_MODE, 'q2-counting-iq2-fused-grid'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_slice_commit_manifest_binding(self):
        self.assertEqual(remote.IQ2_SLICE_COMMIT_MANIFEST,
                         'config/q2-iq2-slice-commit-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_SLICE_COMMIT_MANIFEST).is_file())

    def test_iq2_slice_commit_new_component_or_matched_counting_only(self):
        variant = 'iq2-slice-commit'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred', 'q2-counting-iq2-pair-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 slice commit requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_SLICE_COMMIT_MODE, 'q2-fixture'], 'IQ2 slice commit requires')
        base = [remote.IQ2_SLICE_COMMIT_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 slice commit component builds')
        for mode in (remote.IQ2_SLICE_COMMIT_MODE, 'q2-counting-iq2-slice-commit'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_pair_commit_manifest_binding(self):
        self.assertEqual(remote.IQ2_SLICE_COMMIT_MANIFEST,
                         'config/q2-iq2-slice-commit-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_SLICE_COMMIT_MANIFEST).is_file())

    def test_iq2_pair_commit_new_component_or_matched_counting_only(self):
        variant = 'iq2-pair-commit'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred', 'q2-counting-iq2-slice-commit'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 slice commit requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_SLICE_COMMIT_MODE, 'q2-fixture'], 'IQ2 slice commit requires')
        base = [remote.IQ2_SLICE_COMMIT_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 slice commit component builds')
        for mode in (remote.IQ2_SLICE_COMMIT_MODE, 'q2-counting-iq2-pair-commit'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_sign_mask_manifest_binding(self):
        self.assertEqual(remote.IQ2_SIGN_MASK_MANIFEST,
                         'config/q2-iq2-sign-mask-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_SIGN_MASK_MANIFEST).is_file())

    def test_iq2_sign_mask_new_component_or_matched_counting_only(self):
        variant = 'iq2-sign-mask'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 sign mask requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_SIGN_MASK_MODE, 'q2-fixture'], 'IQ2 sign mask requires')
        base = [remote.IQ2_SIGN_MASK_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 sign mask component builds')
        for mode in (remote.IQ2_SIGN_MASK_MODE, 'q2-counting-iq2-sign-mask'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_raw_prefetch_manifest_binding(self):
        self.assertEqual(remote.IQ2_RAW_PREFETCH_MANIFEST,
                         'config/q2-iq2-raw-prefetch-source.json')
        self.assertTrue((remote.ROOT / remote.IQ2_RAW_PREFETCH_MANIFEST).is_file())

    def test_iq2_raw_prefetch_new_component_or_matched_counting_only(self):
        variant = 'iq2-raw-prefetch'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 raw prefetch requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_RAW_PREFETCH_MODE, 'q2-fixture'], 'IQ2 raw prefetch requires')
        base = [remote.IQ2_RAW_PREFETCH_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 raw prefetch component builds')
        for mode in (remote.IQ2_RAW_PREFETCH_MODE, 'q2-counting-iq2-raw-prefetch'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_ssm_row128_new_component_or_matched_counting_only(self):
        variant = 'ssm-row128'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'SSM row128 requires its component or matched historical counting provider')
        self.refuse([remote.SSM_ROW128_MODE, 'q2-fixture'], 'SSM row128 requires')
        base = [remote.SSM_ROW128_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'SSM row128 component builds')
        for mode in (remote.SSM_ROW128_MODE, 'q2-counting-ssm-row128'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_q8_halfpair_new_component_or_matched_counting_only(self):
        variant = 'q8-halfpair'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q8 halfpair requires its component or matched historical counting provider')
        self.refuse([remote.Q8_HALFPAIR_MODE, 'q2-fixture'], 'Q8 halfpair requires')
        base = [remote.Q8_HALFPAIR_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'Q8 halfpair component builds')
        for mode in (remote.Q8_HALFPAIR_MODE, 'q2-counting-q8-halfpair'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_halfbyte_new_component_or_matched_counting_only(self):
        variant = 'iq2-halfbyte-perm'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 halfbyte requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_HALFBYTE_MODE, 'q2-fixture'], 'IQ2 halfbyte requires')
        base = [remote.IQ2_HALFBYTE_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 halfbyte component builds')
        for mode in (remote.IQ2_HALFBYTE_MODE, 'q2-counting-iq2-halfbyte'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_iq2_halfstage_new_component_or_matched_counting_only(self):
        variant = 'iq2-halfstage'
        for mode in ('cpu', 'operators', 'q2-profile', 'q2-bench', 'q2-curve',
                     'q2-counting-hc-moe-deferred', 'q8-grouped-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'IQ2 halfstage requires its component or matched historical counting provider')
        self.refuse([remote.IQ2_HALFSTAGE_MODE, 'q2-fixture'], 'IQ2 halfstage requires')
        base = [remote.IQ2_HALFSTAGE_MODE, 'q2-fixture', '--source-variant', variant]
        self.refuse(base + ['--rebuild-mmq'], 'IQ2 halfstage component builds')
        for mode in (remote.IQ2_HALFSTAGE_MODE, 'q2-counting-iq2-halfstage'):
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
                argv += ['--rebuild-mmq']
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            self.refuse(argv + ['--native-curve'], 'Native curve requires')
            self.refuse(argv + ['--point-only'], 'Focused point requires')
            self.refuse(argv + ['--replay-from', 'q2-norm-fixed-model-before-r1'],
                        'Binary replay requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_q8_grouped_is_new_component_or_matched_counting_only(self):
        variant='q8-grouped-store'
        for mode in ('cpu','operators','q2-profile','q2-bench','q2-curve','q2-counting-hc-moe-deferred'):
            self.refuse([mode,'q2-fixture','--source-variant',variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Q8 grouped requires its component or matched historical counting provider')
        self.refuse([remote.Q8_GROUPED_MODE,'q2-fixture'], 'Q8 grouped requires')
        argv=[remote.Q8_GROUPED_MODE,'q2-fixture','--source-variant',variant]
        self.refuse(argv+['--rebuild-mmq'],'Q8 grouped component builds')
        for mode in (remote.Q8_GROUPED_MODE,'q2-counting-q8-grouped'):
            argv=[mode,'q2-fixture','--source-variant',variant]
            if mode.startswith('q2-counting'):
                self.refuse(argv,'Historical counting requires a full MMQ rebuild')
                argv+=['--rebuild-mmq']
            with patch.object(sys,'argv',[str(path),*argv]), \
                 patch.object(Path,'mkdir',side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess,'run',side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError,'staging reached'):
                    remote.main()
                run.assert_not_called()

    def test_fixed_moe_profile_reuses_only_saved_candidate(self):
        argv = [remote.FIXED_PROFILE_MODE, 'q2-fixture', '--source-variant', 'hc-moe-deferred']
        for extra in (['--rebuild-mmq'], ['--native-curve'], ['--point-only'], ['--detach'],
                      ['--replay-from', 'q2-norm-fixed-model-before-r1']):
            self.refuse(argv + extra, 'Fixed MoE profile requires the saved candidate binary only')
        self.refuse([remote.FIXED_PROFILE_MODE, 'q2-fixture'],
                    'Fixed MoE profile requires the saved candidate binary only')
        with patch.object(sys, 'argv', [str(path), *argv]), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_current_best_profile_reuses_only_saved_candidate(self):
        argv = [remote.CURRENT_PROFILE_MODE, 'q2-fixture', '--source-variant', 'half-consumer-eight']
        for extra in (['--rebuild-mmq'], ['--native-curve'], ['--point-only'], ['--detach'],
                      ['--replay-from', 'q2-norm-fixed-model-before-r1']):
            self.refuse(argv + extra, 'Current best profile requires the saved candidate binary only')
        self.refuse([remote.CURRENT_PROFILE_MODE, 'q2-fixture'],
                    'Current best profile requires the saved candidate binary only')
        with patch.object(sys, 'argv', [str(path), *argv]), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_selective_scaled_fixed_counting_scope(self):
        variant = 'scaled-selective'
        for mode in ('cpu', 'q2-bench', 'q2-profile', 'q2-curve', 'scaled-tiles-check',
                     'q8-grouped-check', 'q2-counting-hc-moe-deferred'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'Selective scaled tiles require their matched historical counting provider')
        argv = ['q2-counting-scaled-selective', 'q2-fixture', '--source-variant', variant]
        self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
        self.refuse(argv + ['--rebuild-mmq', '--detach'], 'Persistent launch is limited')
        self.refuse(argv + ['--rebuild-mmq', '--native-curve'], 'Native curve requires')
        self.refuse(argv + ['--replay-from', 'q2-norm-fixed-model-before-r1'], 'Binary replay requires')
        self.refuse(['q2-counting-scaled-selective', 'q2-fixture', '--rebuild-mmq'],
                    'Historical counting requires its matched provider')
        with patch.object(sys, 'argv', [str(path), *argv, '--rebuild-mmq']), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_moe_deferred_fixed_counting_scope(self):
        variant = 'hc-moe-deferred'
        for mode in ('cpu', 'q2-bench', 'q2-profile', 'q2-curve', 'hc-bk256-bench',
                     'hc-deferred-bench', 'q2-counting-hc-bk256-bounded'):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Historical counting requires its matched provider' if mode in remote.COUNTING_SOURCES
                        else 'MoE deferred norm requires its matched historical counting provider')
        argv = ['q2-counting-hc-moe-deferred', 'q2-fixture', '--source-variant', variant]
        self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
        self.refuse(argv + ['--rebuild-mmq', '--detach'], 'Persistent launch is limited')
        self.refuse(argv + ['--rebuild-mmq', '--native-curve'], 'Native curve requires')
        self.refuse(argv + ['--replay-from', 'q2-norm-fixed-model-before-r1'], 'Binary replay requires')
        self.refuse(['q2-counting-hc-moe-deferred', 'q2-fixture', '--rebuild-mmq'],
                    'Historical counting requires its matched provider')
        with patch.object(sys, 'argv', [str(path), *argv, '--rebuild-mmq']), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_focused_norm_point_scope_and_driver(self):
        for mode in ('cpu', 'q2-counting-iq2', 'q2-curve-scale', 'q2-curve-routes'):
            self.refuse([mode, 'q2-fixture', '--native-curve', '--point-only'],
                        'Focused point requires')
        self.refuse(['q2-point-norm', 'q2-fixture', '--native-curve'],
                    'Paired norm model requires the focused native point')
        self.refuse(['q2-curve-iq2', 'q2-fixture', '--point-only'],
                    'Focused point requires')
        for mode, variant in [('q2-point-norm', 'point-norm-q2'),
                              ('q2-curve-iq2', 'curve-iq2-q2'), ('ud-curve', 'curve-ud')]:
            argv = [mode, 'q2-fixture', '--source-variant', variant,
                    '--native-curve', '--point-only']
            self.refuse(argv, 'Canonical curve requires a full MMQ rebuild')
            with patch.object(sys, 'argv', [str(path), *argv, '--rebuild-mmq']), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()
        from q2_native_curve import client_argv, check_backend
        argv = client_argv(Path('/owned/bench'), Path('/owned/out'), Path('/owned/graphs'),
                           'norm', point_only=True)
        opts = dict(zip(argv[1::2], argv[2::2]))
        self.assertEqual([opts[k] for k in ('--depths','--pp','--tg','--warmups','--repetitions')],
                         ['0','2048','128','1','3'])
        self.assertEqual(opts['--context-capacity'], '133760')
        info = dict(schema='synapse-lie.llm.v1', ready=True,
            backend=dict(synthetic=False, mtp=False, vision=False, prefix_state=True,
                         model='bench', context_tokens=133760, build_id='q2-canonical-point-norm-ragged',
                         source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e'),
            cache=dict(budget_bytes=16384*1024*1024), scheduler=dict(queued=0, active=0, max_active=1))
        check_backend(info, 'norm')
        for variant in ('ordered','row','scale','ud'):
            with self.assertRaises(ValueError): check_backend(info, variant)

    def test_scaled_row_component_scope(self):
        for variant in remote.ROW_VARIANTS:
            for mode in ('cpu', 'q2-curve', 'q2-bench', 'q2-profile', 'operators'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'Scaled row reuse requires its isolated component mode and source')
            argv = ['scaled-row-check', 'q2-fixture', '--source-variant', variant]
            self.refuse(argv + ['--rebuild-mmq'], 'no MMQ selection')
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()
        self.refuse(['scaled-row-check', 'q2-fixture'], 'Scaled row reuse requires')

    def test_native_curve_host_uses_only_the_frozen_cpu_client(self):
        for extra in (['--source-variant', 'curve-iq2-q2'], ['--rebuild-mmq']):
            self.refuse(['native-curve-cpu', 'q2-fixture', *extra],
                        'Native curve host conformance requires its fixed client and no GPU build')
        self.refuse(['native-curve-cpu', 'q2-fixture', '--native-curve'],
                    'Native curve requires an uninstrumented')
        self.refuse(['native-curve-cpu', 'q2-fixture', '--detach'], 'Persistent launch is limited')
        with patch.object(sys, 'argv', [str(path), 'native-curve-cpu', 'q2-fixture']), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_native_curve_rejects_fallback_and_wrong_provider(self):
        self.refuse(['q2-curve-scale', 'q2-fixture', '--source-variant', 'curve-scale-q2',
                     '--rebuild-mmq'], 'requires the native C canonical benchmark')
        for mode in ('cpu', 'q2-counting-iq2', 'q2-curve-routes', 'q2-curve-iq2-mixed'):
            self.refuse([mode, 'q2-fixture', '--native-curve'], 'Native curve requires')
        for mode, variant in [('q2-curve-iq2', 'curve-iq2-q2'),
                              ('q2-curve-scale', 'curve-scale-q2'),
                              ('q2-curve-row', 'curve-row-q2'), ('ud-curve', 'curve-ud')]:
            argv = [mode, 'q2-fixture', '--source-variant', variant, '--native-curve']
            self.refuse(argv, 'Canonical curve requires a full MMQ rebuild')
            self.refuse(argv + ['--rebuild-mmq', '--detach'], 'Persistent launch is limited')
            with patch.object(sys, 'argv', [str(path), *argv, '--rebuild-mmq']), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                run.assert_not_called()
        self.refuse(['q2-curve-scale', 'q2-fixture', '--source-variant', 'curve-iq2-q2',
                     '--native-curve', '--rebuild-mmq'], 'Canonical curve requires its matched')

    def test_scaled_row_curve_identity_and_native_only(self):
        self.refuse(['q2-curve-row', 'q2-fixture', '--source-variant', 'curve-row-q2',
                     '--rebuild-mmq'], 'requires the native C canonical benchmark')
        self.refuse(['q2-curve-row', 'q2-fixture', '--source-variant', 'curve-scale-q2',
                     '--native-curve', '--rebuild-mmq'], 'Canonical curve requires its matched')
        from q2_native_curve import check_backend
        info = dict(schema='synapse-lie.llm.v1', ready=True,
            backend=dict(synthetic=False, mtp=False, vision=False, prefix_state=True,
                         model='bench', context_tokens=133760,
                         build_id='q2-canonical-curve-scaled-row-reuse',
                         source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e'),
            cache=dict(budget_bytes=16384*1024*1024), scheduler=dict(queued=0, active=0, max_active=1))
        check_backend(info, 'row')
        for variant in ('ordered', 'scale', 'ud'):
            with self.assertRaises(ValueError): check_backend(info, variant)

    def test_native_curve_source_is_complete_and_frozen(self):
        from q2_native_curve import verify_source, MANIFEST, sha
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'config').mkdir()
            source = root/'source'
            files = {}
            for name in ('tools/native/http_curve.c', 'tools/native/gufo_workload.c',
                         'tests/test_http_curve_native.c'):
                p = source/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fixture')
                files[name] = sha(p)
            receipt = dict(schema='synapse-lie.q2-native-bench-source.v1', source='source', files=files)
            (root/MANIFEST).write_text(json.dumps(receipt))
            self.assertEqual(verify_source(root)[0], source)
            extra = source/'unexpected.c'
            extra.write_text('extra')
            with self.assertRaisesRegex(ValueError, 'inventory changed'):
                verify_source(root)
            extra.unlink()
            (source/'tools/native/http_curve.c').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'inventory changed'):
                verify_source(root)

    def test_native_curve_admission_and_exact_cli(self):
        from q2_native_curve import check_backend, client_argv
        info = dict(schema='synapse-lie.llm.v1', ready=True,
            backend=dict(synthetic=False, mtp=False, vision=False, prefix_state=True,
                         model='bench', context_tokens=133760, build_id='q2-canonical-curve-iq2-scale-reuse',
                         source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e'),
            cache=dict(budget_bytes=16384*1024*1024), scheduler=dict(queued=0, active=0, max_active=1))
        check_backend(info, 'scale')
        for group, field, value in [('backend','synthetic',True), ('backend','mtp',True),
                                    ('backend','context_tokens',4096), ('cache','budget_bytes',0),
                                    ('scheduler','active',1), ('scheduler','max_active',2)]:
            changed = json.loads(json.dumps(info)); changed[group][field] = value
            with self.assertRaises(ValueError): check_backend(changed, 'scale')
        with self.assertRaises(ValueError): check_backend(info, 'ordered')
        argv = client_argv(Path('/owned/synapse-lie-bench'), Path('/owned/out.jsonl'),
                           Path('/owned/graphs'), 'scale')
        self.assertEqual(argv[0], '/owned/synapse-lie-bench')
        options = dict(zip(argv[1::2], argv[2::2]))
        self.assertEqual(options['--suite'], 'http-curve')
        self.assertEqual(options['--depths'], '0,4096,8192,12288,16384,32768,65536,131072')
        self.assertEqual([options[k] for k in ('--pp','--tg','--task','--warmups','--repetitions')],
                         ['2048','128','prose','1','1'])
        self.assertFalse(any('python' in a.lower() for a in argv))

    def test_historical_counting_scope(self):
        for mode, variant in remote.COUNTING_SOURCES.items():
            base = [mode, 'q2-fixture', '--source-variant', variant]
            self.refuse(base, 'Historical counting requires a full MMQ rebuild')
            self.refuse(base + ['--rebuild-mmq', '--detach'], 'Persistent launch is limited')
            for wrong in set(remote.COUNTING_SOURCES.values()) - {variant}:
                self.refuse([mode, 'q2-fixture', '--source-variant', wrong, '--rebuild-mmq'],
                            'requires the existing library component only' if wrong in remote.NORM_SHAPE_VARIANTS
                            else 'Shared Q8 producer requires its isolated component mode and source' if wrong == remote.Q8_PRODUCER_VARIANT
                            else 'Historical counting requires its matched provider')
            with patch.object(sys, 'argv', [str(path), *base, '--rebuild-mmq']), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()

    def test_hc_bk256_isolated_scope(self):
        for variant in remote.HC_BK_VARIANTS:
            for mode in ('cpu', 'operators', 'q2-bench', 'ud-counting-legacy'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'Historical counting requires its matched provider'
                            if mode in remote.COUNTING_SOURCES
                            else 'HC BK256 requires its component or matched counting mode')
            argv = [remote.HC_BK_MODE, 'q2-fixture', '--source-variant', variant]
            self.refuse(argv+['--rebuild-mmq'], 'HC BK256 component builds kernels directly')
            self.refuse(argv+['--detach'], 'Persistent launch is limited')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')):
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
        self.refuse([remote.HC_BK_MODE, 'q2-fixture'],
                    'HC BK256 requires its component or matched counting mode')

    def test_binary_replay_scope(self):
        controls = [('q2-counting-iq2-mixed', 'curve-iq2-mixed-q2', 'q2-norm-fixed-model-before-r1'),
                    ('ud-counting-legacy', 'qualified', 'q2-norm-fixed-model-ud-r1')]
        for mode, variant, label in controls:
            argv = [mode, 'q2-fixture', '--source-variant', variant, '--replay-from', label]
            for extra in (['--rebuild-mmq'], ['--native-curve'], ['--detach'], ['--point-only']):
                self.refuse(argv+extra, 'Binary replay requires')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')):
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
        self.refuse(['q2-counting-shared-q8', 'q2-fixture', '--source-variant', 'shared-q8-producer',
                     '--replay-from', 'q2-norm-fixed-model-before-r1'], 'Binary replay requires')

    def test_reaudit_composition_scope(self):
        for variant in remote.REAUDIT_SOURCES.values():
            for mode in ('cpu', 'shared-q8-producer-check', 'q2-curve', 'operators', 'q2-bench'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'Historical counting requires its matched provider')
        for mode, variant in remote.REAUDIT_SOURCES.items():
            argv = [mode, 'q2-fixture', '--source-variant', variant]
            self.refuse(argv, 'Historical counting requires a full MMQ rebuild')
            self.refuse(argv+['--rebuild-mmq', '--native-curve'], 'Native curve requires')
            self.refuse(argv+['--rebuild-mmq', '--point-only'], 'Focused point requires')
            self.refuse(argv+['--rebuild-mmq', '--detach'], 'Persistent launch is limited')
            self.refuse(argv+['--replay-from', 'q2-norm-fixed-model-before-r1'], 'Binary replay requires')

    def test_historical_counting_harness_is_frozen(self):
        root = path.parents[1]
        manifest = json.loads((root/'config/q2-counting-harness.json').read_text())
        self.assertEqual(manifest['source'], 'experiments/counting-baseline/q2_model.cpp')
        self.assertEqual(manifest['sha256'],
                         '681f00a308135c2a241e480bde23d071cf1ec4fa05002456fcb2623eabfb5d52')
        self.assertEqual(hashlib.sha256((root/manifest['source']).read_bytes()).hexdigest(),
                         manifest['sha256'])
        self.assertEqual(hashlib.sha256((root/'tests/q2_profile_markers.hip').read_bytes()).hexdigest(),
                         manifest['markers_sha256'])

    def test_iq2_mixed_component_scope(self):
        for mode in remote.MIXED_TILE_MODES:
            self.refuse([mode, 'q2-fixture'], 'IQ2 mixed tiles requires')
            argv = [mode, 'q2-fixture', '--source-variant', 'iq2-mixed']
            self.refuse(argv + ['--rebuild-mmq'], 'no MMQ selection')
            self.refuse(argv + ['--detach'], 'Persistent launch is limited')
            with patch.object(sys, 'argv', [str(path), *argv]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()
        for mode in ('cpu', 'q2-curve', 'q2-bench', 'operators', 'iq2-live-epilogue-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'iq2-mixed'],
                        'IQ2 mixed tiles requires')

    def test_iq2_epilogue_component_scope(self):
        for variant in remote.EPILOGUE_VARIANTS:
            for mode in ('cpu', 'q2-curve', 'q2-bench', 'q2-profile', 'operators', 'iq2-wmma-signs-check'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'IQ2 live epilogue requires its isolated component mode and source')
            base = ['iq2-live-epilogue-check', 'q2-fixture', '--source-variant', variant]
            self.refuse(base + ['--rebuild-mmq'], 'no MMQ selection')
            self.refuse(base + ['--detach'], 'Persistent launch is limited')
            with patch.object(sys, 'argv', [str(path), *base]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()
        for variant in ('qualified', *remote.WMMA_SIGN_VARIANTS):
            self.refuse(['iq2-live-epilogue-check', 'q2-fixture', '--source-variant', variant],
                        'IQ2 live epilogue requires its isolated component mode and source')

    def test_iq2_wmma_component_scope(self):
        for variant in remote.WMMA_SIGN_VARIANTS:
            for mode in ('cpu', 'q2-curve', 'q2-bench', 'q2-profile', 'operators'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'IQ2 WMMA signs requires its isolated component mode and source')
            base = ['iq2-wmma-signs-check', 'q2-fixture', '--source-variant', variant]
            self.refuse(base + ['--rebuild-mmq'], 'no MMQ selection')
            self.refuse(base + ['--detach'], 'Persistent launch is limited')
            with patch.object(sys, 'argv', [str(path), *base]), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()
        self.refuse(['iq2-wmma-signs-check', 'q2-fixture'],
                    'IQ2 WMMA signs requires its isolated component mode and source')

    def test_ple_cache_first_host_scope(self):
        for extra in (['--source-variant', 'curve-q2'], ['--rebuild-mmq']):
            self.refuse(['ple-cache-first-cpu', 'q2-fixture', *extra],
                        'PLE cache-first host checks require their fixed source and no GPU build')
        argv = [str(path), 'ple-cache-first-cpu', 'q2-fixture']
        with patch.object(sys, 'argv', argv), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_iq2_signs_scope(self):
        for variant in remote.SIGN_VARIANTS:
            for mode in ('cpu', 'q2-curve', 'q2-bench', 'q2-profile', 'operators'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'IQ2 signs source requires its isolated component mode')
            self.refuse(['iq2-signs-check','q2-fixture','--source-variant',variant],
                        'IQ2 signs requires a full MMQ rebuild')
            self.refuse(['iq2-signs-check','q2-fixture','--source-variant',variant,
                         '--rebuild-mmq','--detach'],
                        'Persistent launch is limited to Terminal-Bench task runs')
            argv=[str(path),'iq2-signs-check','q2-fixture','--source-variant',variant,
                  '--rebuild-mmq']
            with patch.object(sys,'argv',argv), \
                 patch.object(Path,'mkdir',side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess,'run',side_effect=AssertionError('No process')) as run:
                with self.assertRaisesRegex(RuntimeError,'staging reached'):
                    remote.main()
                mkdir.assert_called_once();run.assert_not_called()
        self.refuse(['iq2-signs-check','q2-fixture','--source-variant','curve-q2'],
                    'IQ2 signs source requires its isolated component mode')

    def test_canonical_curve_scope(self):
        for mode, variant in [('q2-curve', 'qualified'), ('ud-curve', 'curve-q2'),
                              ('q2-curve', 'curve-ud'), ('q2-bench', 'curve-q2'),
                              ('q2-curve-ple','curve-q2'), ('ud-curve','curve-ple-ud'),
                              ('q2-curve-ple','curve-ple-ud'),
                              ('q2-curve-iq2','curve-q2'), ('q2-curve','curve-iq2-q2'),
                              ('q2-curve-iq2','curve-ud'), ('q2-bench','curve-iq2-q2'),
                              ('q2-curve-ple','curve-iq2-q2'),
                              ('q2-curve-ple-cache-first','curve-iq2-q2'),
                              ('q2-curve-iq2','curve-ple-cache-first-q2'),
                              ('q2-curve-ple','curve-ple-cache-first-q2'),
                              ('ud-curve','curve-ple-cache-first-q2'),
                              ('q2-bench','curve-ple-cache-first-q2'),
                              ('q2-curve-routes','curve-iq2-q2'),
                              ('q2-curve-iq2','curve-routes-q2'),
                              ('ud-curve','curve-routes-q2'),
                              ('q2-curve-ple','curve-routes-q2')]:
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Canonical curve requires its matched Q2 or UD composition')
        for mode, variant in [('q2-curve', 'curve-q2'), ('ud-curve', 'curve-ud'),
                              ('q2-curve-ple','curve-ple-q2'), ('ud-curve-ple','curve-ple-ud'),
                              ('q2-curve-iq2','curve-iq2-q2'),
                              ('q2-curve-ple-cache-first','curve-ple-cache-first-q2'),
                              ('q2-curve-routes','curve-routes-q2')]:
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Canonical curve requires a full MMQ rebuild')
            self.refuse([mode, 'q2-fixture', '--source-variant', variant,
                         '--rebuild-mmq', '--detach'],
                        'Persistent launch is limited to Terminal-Bench task runs')

    def test_iq2_curve_valid_selection_reaches_staging(self):
        argv=[str(path),'q2-curve-iq2','q2-fixture','--source-variant','curve-iq2-q2',
              '--rebuild-mmq']
        with patch.object(sys,'argv',argv), \
             patch.object(Path,'mkdir',side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess,'run',side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError,'staging reached'):
                remote.main()
            mkdir.assert_called_once();run.assert_not_called()

    def test_mixed_model_scope(self):
        mode, variant = 'q2-curve-iq2-mixed', 'curve-iq2-mixed-q2'
        base = [mode, 'q2-fixture', '--source-variant', variant]
        self.refuse(base, 'Canonical curve requires a full MMQ rebuild')
        self.refuse(base + ['--rebuild-mmq', '--detach'], 'Persistent launch is limited')
        for wrong in ('curve-q2', 'curve-iq2-q2', 'curve-ud'):
            self.refuse([mode, 'q2-fixture', '--source-variant', wrong, '--rebuild-mmq'],
                        'Canonical curve requires its matched Q2 or UD composition')
        for wrong in ('q2-curve-iq2', 'ud-curve', 'q2-bench'):
            self.refuse([wrong, 'q2-fixture', '--source-variant', variant, '--rebuild-mmq'],
                        'Canonical curve requires its matched Q2 or UD composition')
        with patch.object(sys, 'argv', [str(path), *base, '--rebuild-mmq']), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_route_profile_valid_selection_reaches_staging(self):
        argv=[str(path),'q2-curve-routes','q2-fixture','--source-variant','curve-routes-q2',
              '--rebuild-mmq']
        with patch.object(sys,'argv',argv), \
             patch.object(Path,'mkdir',side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess,'run',side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError,'staging reached'):
                remote.main()
            mkdir.assert_called_once();run.assert_not_called()

    def test_ple_curve_valid_selection_reaches_staging(self):
        argv=[str(path),'q2-curve-ple-cache-first','q2-fixture',
              '--source-variant','curve-ple-cache-first-q2','--rebuild-mmq']
        with patch.object(sys,'argv',argv), \
             patch.object(Path,'mkdir',side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess,'run',side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError,'staging reached'):
                remote.main()
            mkdir.assert_called_once();run.assert_not_called()

    def test_collection_bounds_and_paths(self):
        def archive(mode, size=1, name='results/output.f32', kind=tarfile.REGTYPE):
            receipt = tarfile.TarInfo('results/result.json')
            data = json.dumps({'mode': mode}).encode()
            receipt.size = len(data)
            member = tarfile.TarInfo(name)
            member.size, member.type = size, kind
            result = Mock()
            result.getmembers.return_value = [receipt, member]
            result.extractfile.return_value = io.BytesIO(data)
            return result
        self.assertEqual(remote.collection_receipt(archive('q2-ple-first-access', 320000000))['mode'],
                         'q2-ple-first-access')
        self.assertEqual(remote.collection_receipt(archive('iq2-live-epilogue-check', 320000000))['mode'],
                         'iq2-live-epilogue-check')
        self.assertEqual(remote.collection_receipt(archive('q2-terminal-full', 1024**3))['mode'],
                         'q2-terminal-full')
        self.assertEqual(remote.collection_receipt(archive('hc-norm-ragged-bench', 1106304168))['mode'],
                         'hc-norm-ragged-bench')
        for mode, size in [('q2-ple-lookahead', 129000000), ('q2-ple-first-access', 385000000),
                           ('iq2-live-epilogue-check', 384000000), ('iq2-wmma-signs-check', 129000000)]:
            with self.assertRaisesRegex(ValueError, 'Oversized collection'):
                remote.collection_receipt(archive(mode, size))
        for mode, size in [('hc-norm-ragged-bench', 1120000000), ('q2-terminal-full', 2 * 1024**3),
                           ('q2-terminal-smoke', 129000000), ('cpu', 129000000)]:
            with self.assertRaisesRegex(ValueError, 'Oversized collection'):
                remote.collection_receipt(archive(mode, size))
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('source/file', tarfile.REGTYPE), ('results/link', tarfile.SYMTYPE),
                           ('results/result.json', tarfile.REGTYPE)]:
            value = archive('q2-ple-first-access', name=name, kind=kind)
            with self.assertRaisesRegex(ValueError, 'Unsafe collection'):
                remote.collection_receipt(value)
            value.extractfile.assert_not_called()

    def test_streamed_artifact_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'telemetry.jsonl'
            payload = b'bounded observation\n' * 100000
            path.write_bytes(payload)
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('No whole-file read')):
                self.assertEqual(remote.file_sha256(path), hashlib.sha256(payload).hexdigest())

    def test_existing_collection_cannot_launch_model(self):
        self.refuse(['q2-ple-first-access', 'q2-fixture', '--existing-collection'],
                    'Existing collection requires collect mode')

    def refuse(self, argv, reason):
        with patch.object(sys, 'argv', [str(path), *argv]), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run, \
             patch.object(Path, 'mkdir', side_effect=AssertionError('No staging may start')) as mkdir, \
             contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as result:
                remote.main()
            self.assertEqual(result.exception.code, 2)
            self.assertIn(reason, error.getvalue())
            run.assert_not_called()
            mkdir.assert_not_called()

    def test_terminal_tasks_require_persistent_supervision(self):
        for mode in ('q2-terminal-smoke', 'q2-terminal-full'):
            self.refuse([mode, 'q2-fixture'], 'require the persistent supervisor')
        self.refuse(['cpu', 'q2-fixture', '--detach'], 'limited to Terminal-Bench task runs')

    def test_terminal_variants_are_frozen(self):
        for mode in ('terminal-cpu', 'q2-terminal-build', 'q2-terminal-probe'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'shared-overlap'],
                        'three frozen Q2 variants')
            self.refuse([mode, 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')

    def test_ple_source_is_fixed(self):
        for mode in ('ple-cpu', 'q2-ple', 'ud-ple', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-moe-fused'],
                        'fixed instrumented Q2/UD source')
            self.refuse([mode, 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')

    def test_changed_executor_header_cannot_reuse_mmq(self):
        for variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
            self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', variant],
                        'explicitly rebuild MMQ')

    def test_deferred_norm_requires_component_scope(self):
        for variant in ('qualified', 'hc-up-chains', 'hc-sequence'):
            self.refuse(['hc-deferred-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the isolated hc-deferred-norm source')
        for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'ud-bench2k'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-deferred-norm'],
                        'not wired for model measurements')
        self.refuse(['hc-deferred-bench', 'q2-fixture', '--source-variant',
                     'hc-deferred-norm', '--rebuild-mmq'], 'requires bench2k')

    def test_sequence_requires_preserved_control_source(self):
        for variant in ('qualified', 'hc-up-chains', 'hc-norm-half'):
            self.refuse(['hc-sequence-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the isolated hc-sequence source')
        self.refuse(['hc-sequence-bench', 'q2-fixture', '--source-variant',
                     'hc-sequence', '--rebuild-mmq'], 'requires bench2k')

    def test_norm_requires_paired_output_source(self):
        for mode in ('hc-norm-operators', 'hc-norm-bench'):
            for variant in ('qualified', 'hc-moe-fused', 'packed'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'require the isolated hc-norm-half source')

    def test_iq2_entry_requires_correct_source(self):
        self.refuse(['iq2-pair-operators', 'q2-fixture'], 'require the isolated IQ2 source')
        self.refuse(['routed-operators', 'q2-fixture'], 'require the isolated stack source')

    def test_scaled_input_source_guard(self):
        for variant in ('qualified', 'hc-up-chains', 'shared-overlap'):
            self.refuse(['scaled-input-check', 'q2-fixture', '--source-variant', variant],
                        'Scaled checks require the isolated scaled-input source')

    def test_scaled_tiles_component_only(self):
        for variant in ('qualified', 'hc-up-chains', 'scaled-input'):
            self.refuse(['scaled-tiles-check', 'q2-fixture', '--source-variant', variant],
                        'Scaled tile checks require the isolated scaled-tiles source')
        for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'scaled-input-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'scaled-tiles'],
                        'component-only; no model dispatch')
        self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                     '--source-variant', 'scaled-tiles'],
                    'requires one of its three frozen Q2 variants')

    def test_narrow_vector_component_only(self):
        for variant in ('qualified', 'hc-up-chains', 'scaled-input'):
            self.refuse(['narrow-vector-check', 'q2-fixture', '--source-variant', variant],
                        'Narrow checks require the isolated narrow-vector source')
        for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'scaled-input-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'narrow-vector'],
                        'component-only; no model dispatch')
        self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                     '--source-variant', 'narrow-vector'],
                    'requires one of its three frozen Q2 variants')

    def test_scaled_library_source_boundaries(self):
        self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', 'scaled-library'],
                    'requires a full MMQ rebuild')
        self.refuse(['q2-profile', 'q2-fixture', '--source-variant', 'scaled-library',
                     '--rebuild-mmq'], 'requires bench2k')
        for mode in ('q2-bench', 'ud-bench2k', 'q2-ple-lookahead',
                     'hc-library-bench', 'operators', 'cpu', 'scaled-input-check'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'scaled-library'],
                        'requires its explicit component, bench2k or profile experiment')
        self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                     '--source-variant', 'scaled-library'],
                    'requires one of its three frozen Q2 variants')

    def test_ragged_paired_norm_scope(self):
        for variant in ('qualified', 'library-norm-cycle', 'hc-library-ragged'):
            self.refuse(['hc-norm-ragged-bench', 'q2-fixture', '--source-variant', variant],
                        'requires its isolated component mode and source')
        for mode in ('cpu', 'q2-bench2k', 'q2-curve-iq2', 'hc-library-norm-bench'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-norm-ragged'],
                        'requires its isolated component mode and source')
        self.refuse(['hc-norm-ragged-bench', 'q2-fixture', '--source-variant',
                     'hc-norm-ragged', '--rebuild-mmq'], 'builds its kernels directly')
        self.refuse(['hc-norm-ragged-bench', 'q2-fixture', '--source-variant',
                     'hc-norm-ragged', '--detach'], 'Persistent launch is limited')
        argv = [str(path), 'hc-norm-ragged-bench', 'q2-fixture',
                '--source-variant', 'hc-norm-ragged']
        with patch.object(sys, 'argv', argv), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_fixed_norm_shape_component_scope(self):
        for variant in ('norm-shape-reference', 'norm-fixed-shape'):
            for mode in ('cpu', 'q2-bench2k', 'q2-counting-iq2-mixed',
                         'q2-curve-iq2-mixed', 'hc-norm-ragged-bench'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'requires the existing library component only')
            self.refuse(['hc-library-norm-bench', 'q2-fixture',
                         '--source-variant', variant, '--rebuild-mmq'],
                        'builds its kernels directly')
            self.refuse(['hc-library-norm-bench', 'q2-fixture',
                         '--source-variant', variant, '--detach'],
                        'Persistent launch is limited')
            argv = [str(path), 'hc-library-norm-bench', 'q2-fixture',
                    '--source-variant', variant]
            with patch.object(sys, 'argv', argv), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()

    def test_shared_q8_producer_scope(self):
        for mode in ('cpu', 'q2-counting-iq2-mixed', 'q2-counting-norm-fixed',
                     'q2-curve-iq2-mixed', 'hc-library-norm-bench'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'shared-q8-producer'],
                        'Shared Q8 producer requires its isolated component')
        self.refuse(['shared-q8-producer-check', 'q2-fixture'],
                    'Shared Q8 producer requires its isolated component')
        self.refuse(['shared-q8-producer-check', 'q2-fixture', '--source-variant',
                     'shared-q8-producer', '--rebuild-mmq'], 'builds kernels directly')
        self.refuse(['shared-q8-producer-check', 'q2-fixture', '--source-variant',
                     'shared-q8-producer', '--detach'], 'Persistent launch is limited')
        argv = [str(path), 'shared-q8-producer-check', 'q2-fixture',
                '--source-variant', 'shared-q8-producer']
        with patch.object(sys, 'argv', argv), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_saved_q8_oracle_scope(self):
        mode = 'shared-q8-oracle-replay'
        self.refuse([mode, 'q2-fixture'], 'requires its saved-array provider')
        self.refuse([mode, 'q2-fixture', '--source-variant', 'reaudit-q8-row'],
                    'Historical counting requires its matched provider')
        args = [mode, 'q2-fixture', '--source-variant', 'shared-q8-producer']
        self.refuse(args + ['--rebuild-mmq'], 'builds kernels directly')
        self.refuse(args + ['--detach'], 'Persistent launch is limited')
        self.refuse(args + ['--native-curve'], 'Native curve requires')
        self.refuse(args + ['--point-only'], 'Focused point requires')
        with patch.object(sys, 'argv', [str(path), *args]), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')), \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            run.assert_not_called()

    def test_saved_q8_source_member_size_is_bounded(self):
        limits = remote.source_data_limits('shared-q8-oracle-replay')
        self.assertEqual(limits, {'oracle-replay-data/shared-q8-n2048-p0-mixed-reference.bin': 20971520})
        for mode in ('cpu', 'shared-q8-producer-check', 'q2-counting-shared-q8'):
            self.assertEqual(remote.source_data_limits(mode), {})
        for name in ('source/weights.bin', 'oracle-replay-data/../weights.bin',
                     'oracle-replay-data/shared-q8-n2048-p0-q8-reference.bin'):
            self.assertEqual(limits.get(name,16000000),16000000)

    def test_fixed_norm_shape_model_scope(self):
        self.refuse(['q2-counting-norm-fixed', 'q2-fixture', '--source-variant',
                     'norm-shape-reference', '--rebuild-mmq'],
                    'requires the existing library component only')
        for variant in ('qualified', 'curve-iq2-mixed-q2', 'library-norm-cycle'):
            self.refuse(['q2-counting-norm-fixed', 'q2-fixture', '--source-variant',
                         variant, '--rebuild-mmq'], 'Historical counting requires its matched provider')
        self.refuse(['q2-counting-norm-fixed', 'q2-fixture', '--source-variant',
                     'norm-fixed-shape'], 'Historical counting requires a full MMQ rebuild')
        for flag, reason in (('--native-curve', 'Native curve requires'),
                             ('--point-only', 'Focused point requires'),
                             ('--detach', 'Persistent launch is limited')):
            self.refuse(['q2-counting-norm-fixed', 'q2-fixture', '--source-variant',
                         'norm-fixed-shape', '--rebuild-mmq', flag], reason)
        argv = [str(path), 'q2-counting-norm-fixed', 'q2-fixture',
                '--source-variant', 'norm-fixed-shape', '--rebuild-mmq']
        with patch.object(sys, 'argv', argv), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_library_norm_cycle_scope(self):
        for variant in ('qualified', 'scaled-library', 'hc-sequence'):
            self.refuse(['hc-library-norm-bench', 'q2-fixture', '--source-variant', variant],
                        'requires its preserved-control source')
        for mode in ('ud-bench2k', 'q2-profile', 'hc-sequence-bench', 'hc-pp-bench', 'cpu'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'library-norm-cycle'],
                        'requires its explicit component or bench2k experiment')
        self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', 'library-norm-cycle'],
                    'requires a full MMQ rebuild')
        self.refuse(['hc-library-norm-bench', 'q2-fixture', '--source-variant',
                     'library-norm-cycle', '--rebuild-mmq'], 'requires bench2k')
        # An allowed invocation must reach staging, without creating files or SSH.
        for mode in ('hc-library-norm-bench', 'q2-bench2k'):
            argv = [str(path), mode, 'q2-fixture', '--source-variant', 'library-norm-cycle']
            if mode == 'q2-bench2k':
                argv.append('--rebuild-mmq')
            with patch.object(sys, 'argv', argv), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()

    def test_hc_decode_reduction_scope(self):
        for variant in ('qualified', 'library-norm-bound', 'library-norm-cycle'):
            self.refuse(['hc-decode-reduce-bench', 'q2-fixture', '--source-variant', variant],
                        'HC decode reduction requires its preserved-control source')
        for mode in ('q2-bench2k', 'ud-bench2k', 'q2-profile', 'cpu', 'hc-bench'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-decode-reduce'],
                        'HC decode reduction is component-only')
        self.refuse(['hc-decode-reduce-bench', 'q2-fixture', '--source-variant',
                     'hc-decode-reduce', '--rebuild-mmq'], 'requires bench2k')
        argv = [str(path), 'hc-decode-reduce-bench', 'q2-fixture',
                '--source-variant', 'hc-decode-reduce']
        with patch.object(sys, 'argv', argv), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_ragged_library_scope(self):
        for variant in ('qualified', 'library-norm-bound', 'hc-decode-reduce'):
            self.refuse(['hc-library-ragged-bench', 'q2-fixture', '--source-variant', variant],
                        'Ragged HC library requires its isolated source')
        for mode in ('cpu', 'ud-original-baseline', 'q2-decode-baseline', 'q2-bench2k', 'q2-profile', 'hc-library-norm-bench'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-library-ragged'],
                        'Ragged HC library requires its component or original Q2 baseline experiment')
        self.refuse(['hc-library-ragged-bench', 'q2-fixture', '--source-variant',
                     'hc-library-ragged', '--rebuild-mmq'], 'requires bench2k')
        self.refuse(['hc-library-ragged-bench', 'q2-fixture', '--source-variant',
                     'hc-library-ragged', '--detach'], 'Persistent launch is limited')
        argv = [str(path), 'hc-library-ragged-bench', 'q2-fixture',
                '--source-variant', 'hc-library-ragged']
        with patch.object(sys, 'argv', argv), \
             patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
             patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
            with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                remote.main()
            mkdir.assert_called_once()
            run.assert_not_called()

    def test_decode_baseline_scope(self):
        for mode, variant in (('q2-decode-baseline', 'library-norm-bound'),
                              ('ud-decode-baseline', 'qualified')):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'requires a full MMQ rebuild')
            for wrong in ('scaled-library', 'library-norm-cycle',
                          'qualified' if variant != 'qualified' else 'library-norm-bound'):
                self.refuse([mode, 'q2-fixture', '--source-variant', wrong,
                             '--rebuild-mmq'], 'requires its fixed Q2 or pristine UD source')
            argv = [str(path), mode, 'q2-fixture', '--source-variant', variant,
                    '--rebuild-mmq']
            with patch.object(sys, 'argv', argv), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()
        for mode in ('cpu', 'q2-bench2k', 'q2-profile', 'operators'):
            self.refuse([mode, 'q2-fixture', '--source-variant', 'library-norm-bound'],
                        'requires the Q2 decode baseline experiment')

    def test_original_baseline_scope(self):
        for mode, variant in (('q2-original-baseline', 'library-norm-bound'),
                              ('q2-original-baseline', 'hc-library-ragged'),
                              ('ud-original-baseline', 'qualified')):
            self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                        'Original baseline requires a full MMQ rebuild')
            for wrong in ('scaled-library', 'library-norm-cycle',
                          'qualified' if variant != 'qualified' else 'library-norm-bound'):
                self.refuse([mode, 'q2-fixture', '--source-variant', wrong,
                             '--rebuild-mmq'], 'Original baseline requires its fixed Q2 or pristine UD source')
            self.refuse([mode, 'q2-fixture', '--source-variant', 'hc-decode-reduce',
                         '--rebuild-mmq'], 'HC decode reduction is component-only')
            self.refuse([mode, 'q2-fixture', '--source-variant', variant,
                         '--rebuild-mmq', '--detach'], 'Persistent launch is limited')
            argv = [str(path), mode, 'q2-fixture', '--source-variant', variant,
                    '--rebuild-mmq']
            with patch.object(sys, 'argv', argv), \
                 patch.object(Path, 'mkdir', side_effect=RuntimeError('staging reached')) as mkdir, \
                 patch.object(remote.subprocess, 'run', side_effect=AssertionError('No process may start')) as run:
                with self.assertRaisesRegex(RuntimeError, 'staging reached'):
                    remote.main()
                mkdir.assert_called_once()
                run.assert_not_called()

    def test_combined_source_boundaries(self):
        for variant in ('combined-retained', 'combined-scaled'):
            self.refuse(['q2-bench2k', 'q2-fixture', '--source-variant', variant],
                        'requires a full MMQ rebuild')
            for mode in ('q2-bench', 'ud-bench2k', 'q2-profile', 'q2-ple', 'operators', 'cpu'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'requires its explicit Q2 model or conversion checks')
            self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                         '--source-variant', variant],
                        'requires one of its three frozen Q2 variants')

    def test_phased_hc_component_only(self):
        for variant in ('hc-down-phased', 'hc-down-phased-free', 'hc-row160-wide', 'hc-row160-loads'):
            for mode in ('q2-bench', 'q2-bench2k', 'q2-profile', 'operators', 'hc-input-bench'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'Phased HC source is component-only; no model dispatch')
            self.refuse(['q2-terminal-full', 'q2-fixture', '--detach',
                         '--source-variant', variant],
                        'requires one of its three frozen Q2 variants')

    def test_shared_fork_source_guard(self):
        for variant in ('qualified', 'hc-up-chains', 'down-scatter'):
            self.refuse(['shared-fork-check', 'q2-fixture', '--source-variant', variant],
                        'require the isolated shared-overlap source')

    def test_packed_bench_requires_measured_source(self):
        for variant in ('qualified', 'packed', 'hc-norm-half'):
            self.refuse(['packed-bench', 'q2-fixture', '--source-variant', variant],
                        'Packed benchmark requires')

    def test_packed_entry_requires_correct_source(self):
        self.refuse(['packed-operators', 'q2-fixture'], 'require the isolated packed source')

    def test_packed_tiles_bench_requires_retained_source(self):
        for mode in ('packed-tiles-bench', 'packed-tiles16-bench'):
            for variant in ('qualified', 'packed', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-down-wide'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'requires retained hc-up-chains source')
            self.refuse([mode, 'q2-fixture', '--source-variant',
                         'hc-up-chains', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_input_requires_isolated_source(self):
        for variant in ('qualified', 'affine-palette', 'hc-library-down'):
            self.refuse(['hc-input-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the isolated hc-input source')
        self.refuse(['hc-input-bench', 'q2-fixture', '--source-variant',
                     'hc-input', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_up_chain_benchmark_requires_measured_sources(self):
        for variant in ('qualified', 'hc-up-fused', 'hc-input'):
            self.refuse(['hc-up-chain-bench', 'q2-fixture', '--source-variant', variant],
                        'requires palette or hc-up-chains')
        self.refuse(['hc-up-chain-bench', 'q2-fixture', '--source-variant',
                     'hc-up-chains', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_library_requires_current_native_control(self):
        for variant in ('qualified', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-moe-fused', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
            self.refuse(['hc-library-bench', 'q2-fixture', '--source-variant', variant],
                        'requires the measured affine-palette source')
        self.refuse(['hc-library-bench', 'q2-fixture', '--source-variant',
                     'affine-palette', '--rebuild-mmq'], 'requires bench2k')

    def test_hc_up_entry_requires_correct_source(self):
        self.refuse(['hc-up-operators', 'q2-fixture'], 'require the isolated hc-up-fused source')
        self.refuse(['hc-up-operators', 'q2-fixture', '--source-variant', 'hc-prefetch'],
                    'require the isolated hc-up-fused source')
        self.refuse(['hc-up-operators', 'q2-fixture', '--source-variant', 'hc-prefetch2'],
                    'require the isolated hc-up-fused source')

    def test_hc_up_bench_requires_measured_source_family(self):
        self.refuse(['hc-up-bench', 'q2-fixture'], 'requires the measured hc-up-fused source')
        self.refuse(['hc-up-bench', 'q2-fixture', '--source-variant', 'packed'],
                    'requires the measured hc-up-fused source')

    def test_hc_moe_entry_requires_fused_source(self):
        for mode in ('hc-moe-operators', 'hc-moe-bench'):
            for variant in ('qualified', 'hc-up-vec-exact', 'packed'):
                self.refuse([mode, 'q2-fixture', '--source-variant', variant],
                            'require the isolated hc-moe-fused source')

    def test_q2_source_cannot_replace_ud_control(self):
        for variant in ('packed', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'staged-palette', 'down-scatter', 'shared-overlap', 'scaled-input', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-sequence', 'hc-sequence-half-row', 'hc-single-chain', 'hc-full-row', 'hc-half-row', 'hc-row80', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
            self.refuse(['ud-bench2k', 'q2-fixture', '--source-variant', variant],
                        'Stack source requires')

    def test_rebuild_flag_does_not_silently_apply_elsewhere(self):
        self.refuse(['q2-profile', 'q2-fixture', '--rebuild-mmq'], 'requires bench2k')


class WmmaCycleReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'wmma_report', path.with_name('analyze-q2-iq2-wmma-signs.py'))
        cls.report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.report)

    @staticmethod
    def events():
        rows = [dict(event='iq2_wmma_weights', bytes=432537600,
                     gate_sha256='a'*64, up_sha256='b'*64)]
        for n, active, tile, tiles in ((2040,512,64,512), (2048,128,128,256)):
            rows.extend(dict(event='iq2_wmma_cycle', sample=i, warmup=i < 2, tokens=n,
                             active_experts=active, tile=tile, calls=8,
                             microseconds_per_call=100+i) for i in range(7))
            rows.append(dict(event='iq2_wmma_geometry', tokens=n, active_experts=active,
                             tile=tile, tiles=tiles, output_values=n*10*640,
                             active_weight_bytes=active*640*10*66*2,
                             input_sha256='c'*64, ids_sha256='d'*64))
        rows.append(dict(event='iq2_wmma_complete', numerical_pass=True,
                         independent_checks=20, failures=0, model_inference=False))
        return rows

    def parse(self, rows):
        return self.report.observations('\n'.join(json.dumps(row) for row in rows))

    def test_complete_cycles_exclude_warmup(self):
        result = self.parse(self.events())
        self.assertEqual([r['median_us'] for r in result['cases'].values()], [104,104])
        self.assertEqual(len(self.report.output_inventory()), 22)

    def test_incomplete_and_invalid_timing_is_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(self.events()[:-1])
        for change in (dict(microseconds_per_call=0), dict(microseconds_per_call=float('nan')),
                       dict(warmup=0), dict(calls=1), dict(sample=2), dict(tile=128)):
            rows = self.events()
            rows[1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(rows)

    def test_numerical_failure_is_retained_without_success(self):
        rows = self.events()
        rows[-1].update(numerical_pass=False, failures=3)
        result = self.parse(rows)
        self.assertFalse(result['completion']['numerical_pass'])
        self.assertEqual(len(result['cases']), 2)
        rows[-1]['numerical_pass'] = True
        with self.assertRaises(ValueError):
            self.parse(rows)

    def test_model_artifacts_still_reject_command_failure(self):
        with patch.object(self.report.common, 'artifact_integrity', return_value=(
                {'commands': [{'exit_code': 0}, {'exit_code': 1}]}, {'exit_code': 1})):
            with self.assertRaises(ValueError):
                self.report.common.artifacts(Path('/unused-no-access'))


class EpilogueCycleReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'epilogue_report', path.with_name('analyze-q2-iq2-live-epilogue.py'))
        cls.report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.report)
        cls.geometry = cls.report.cases()

    def events(self):
        rows = [dict(event='iq2_epilogue_weights', bytes=432537600,
                     gate_sha256='a'*64, up_sha256='b'*64)]
        for name, geometry in self.geometry.items():
            rows.extend(dict(event='iq2_epilogue_cycle', sample=i, warmup=i < 2,
                             case=name, tokens=geometry['tokens'],
                             active_experts=geometry['active_experts'], tile=geometry['tile'],
                             calls=8, microseconds_per_call=100+i) for i in range(7))
            rows.append(dict(event='iq2_epilogue_geometry', input_sha256='c'*64, **geometry))
        rows.append(dict(event='iq2_epilogue_complete', numerical_pass=True,
                         independent_checks=51, failures=0, model_inference=False))
        return rows

    def parse(self, rows):
        return self.report.observations('\n'.join(json.dumps(row) for row in rows))

    def test_complete_cycles_and_full_tile_control(self):
        result = self.parse(self.events())
        self.assertEqual([r['median_us'] for r in result['cases'].values()], [104]*5)
        full = self.geometry['full-tiles']
        self.assertEqual(full['live_fragments'], full['reserved_fragments'])
        self.assertGreater(full['active_weight_bytes'], 32*1024**2)
        self.assertEqual(len(self.report.output_inventory()), 102)

    def test_partial_duplicate_and_wrong_work_is_rejected(self):
        for rows in (self.events()[:-1], self.events() + self.events()[:1]):
            with self.assertRaises(ValueError):
                self.parse(rows)
        for change in (dict(case='full-tiles'), dict(calls=1), dict(warmup=0),
                       dict(microseconds_per_call=float('nan'))):
            rows = self.events()
            rows[1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(rows)
        for change in (dict(counts_sha256='f'*64), dict(ids_sha256='f'*64),
                       dict(live_fragments=0), dict(active_weight_bytes=1024)):
            rows = self.events()
            rows[8].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(rows)

    def test_numerical_failure_preserves_performance(self):
        rows = self.events()
        rows[-1].update(numerical_pass=False, failures=1)
        report = self.parse(rows)
        self.assertFalse(report['completion']['numerical_pass'])
        self.assertEqual(len(report['cases']), 5)
        rows[-1]['numerical_pass'] = True
        with self.assertRaises(ValueError):
            self.parse(rows)

    def test_malformed_counts_cannot_create_a_case(self):
        for value in (True, -1, 2041, 1.5):
            plan = json.loads(self.report.PLAN_PATH.read_text())
            plan['representative_routing'][0]['counts'][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.report.cases(plan)

    def test_candidate_cannot_replace_reference(self):
        for variant, manifest in (
                ('iq2-live-epilogue', 'q2-iq2-live-epilogue-source.json'),
                ('iq2-epilogue-break', 'q2-iq2-epilogue-break-source.json'),
                ('iq2-live-stage', 'q2-iq2-live-stage-source.json'),
                ('iq2-prefill-scale-reuse', 'q2-iq2-prefill-scale-reuse-source.json'),
                ('iq2-prefill-grid-lds', 'q2-iq2-prefill-grid-lds-source.json')):
            self.assertEqual(self.report.source_manifest(variant, True), manifest)
            with self.assertRaises(ValueError):
                self.report.source_manifest(variant, False)
        self.assertEqual(self.report.source_manifest('iq2-epilogue-reference', False),
                         'q2-iq2-signs-ordered-asm-source.json')
        for variant in ('iq2-epilogue-reference', 'qualified', 'curve-iq2-q2'):
            with self.assertRaises(ValueError):
                self.report.source_manifest(variant, True)


class MixedTileReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'mixed_report', path.with_name('analyze-q2-iq2-mixed.py'))
        cls.report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.report)

    def events(self, mixed):
        rows = [dict(event='iq2_mixed_weights', bytes=432537600,
                     gate_sha256='a'*64, up_sha256='b'*64)]
        for name, geometry in self.report.geometry(mixed).items():
            for scope in self.report.SCOPES:
                rows.extend(dict(event='iq2_mixed_cycle', sample=i, warmup=i < 2,
                    case=name, scope=scope, policy='mixed' if mixed else 'reference',
                    calls=8, microseconds_per_call=100+i,
                    wall_microseconds_per_call=110+i) for i in range(7))
            rows.append(dict(event='iq2_mixed_geometry', input_sha256='c'*64, **geometry))
        rows.append(dict(event='iq2_mixed_complete', numerical_pass=True,
                         independent_checks=5, failures=0, model_inference=False))
        return rows

    def parse(self, rows, mixed):
        return self.report.observations('\n'.join(json.dumps(r) for r in rows), mixed)

    def test_both_scopes_and_policy(self):
        for mixed in (False, True):
            result = self.parse(self.events(mixed), mixed)
            self.assertEqual(len(result['cases']), 5)
            for case in result['cases'].values():
                self.assertEqual(case['scopes']['map-upload-cycle']['median_us'], 104)
                self.assertEqual(case['scopes']['resident-map-cycle']['median_wall_us'], 114)
            with self.assertRaises(ValueError):
                self.parse(self.events(mixed), not mixed)
        self.assertEqual(len(self.report.output_inventory()), 10)
        self.assertEqual(self.report.geometry(False)['full-tiles'],
                         self.report.geometry(True)['full-tiles'])

    def test_incomplete_wrong_map_and_scope_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(self.events(True)[:-1], True)
        for index, change in ((1, dict(calls=1)), (1, dict(scope='resident-kernel-only')),
                              (1, dict(wall_microseconds_per_call=float('nan'))),
                              (15, dict(wide_tiles=0)), (15, dict(map_sha256='f'*64)),
                              (-1, dict(independent_checks=1))):
            rows = self.events(True)
            rows[index].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(rows, True)

    def test_numeric_failure_keeps_timings(self):
        rows = self.events(True)
        rows[-1].update(failures=1, numerical_pass=False)
        report = self.parse(rows, True)
        self.assertFalse(report['completion']['numerical_pass'])
        self.assertEqual(len(report['cases']), 5)


class PleHostReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'ple_report', path.with_name('analyze-q2-ple-cache-first.py'))
        cls.report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.report)

    @staticmethod
    def rows():
        return [dict(fixture='ple-cache-first', format=fmt, strict=strict,
                     unique_cold_rows=1024, resident_rows=128, exact_rows=True,
                     pread_calls=1024 if strict else 1152,
                     resident_pread_calls=0 if strict else 128)
                for fmt in ('BF16', 'IQ4_NL') for strict in (True, False)]

    @staticmethod
    def log(rows):
        return '\n'.join('20: '+json.dumps(row, separators=(',', ':')) for row in rows)

    def test_paired_ctest_prefix_and_unobserved_control(self):
        rows = self.rows()
        self.assertEqual(self.report.observations(self.log(rows)), rows)
        for row in rows:
            row.update(pread_calls=1024, resident_pread_calls=0)
        self.assertEqual(self.report.observations(self.log(rows)), rows)

    def test_incomplete_or_duplicated_pair_is_rejected(self):
        rows = self.rows()
        for invalid in (rows[:-1], rows + rows[:1], rows[:3] + rows[:1]):
            with self.assertRaises(ValueError):
                self.report.observations(self.log(invalid))

    def test_false_success_and_inconsistent_reads_are_rejected(self):
        for change in (dict(exact_rows=False), dict(strict=1),
                       dict(resident_pread_calls=1, pread_calls=1025),
                       dict(pread_calls=1025), dict(pread_calls=True),
                       dict(resident_rows=127), dict(unique_cold_rows=1023)):
            rows = self.rows()
            rows[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.report.observations(self.log(rows))


if __name__ == '__main__':
    unittest.main()
