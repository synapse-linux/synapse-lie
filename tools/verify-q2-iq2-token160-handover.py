#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the append-only token160 release amendment and its complete inventory."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-iq2-token160-component-r1'
SUMMARY = ROOT / 'config/q2-iq2-token160-handover-summary.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    require(not SUMMARY.exists(), 'Preserve existing handover summary')
    old_path = ROOT / 'config/q2-select-live-grid-pair-r2-window-release.json'
    old = json.loads(old_path.read_text())
    release_path = EVIDENCE / 'release.json'
    release = json.loads(release_path.read_text())
    result_path = EVIDENCE / 'result.json'
    result = json.loads(result_path.read_text())
    handover_path = EVIDENCE / 'handover.json'
    handover = json.loads(handover_path.read_text())
    require(handover['schema'] == 'synapse-lie.q2-iq2-token160-handover.v1' and
            handover['state'] == 'Q2_IQ2_TOKEN160_HANDOVER_RELEASED' and
            handover['previous_release_sha256'] == sha(release_path) and
            handover['prior_full_release_sha256'] == sha(old_path) and
            handover['component_result_sha256'] == sha(result_path) and
            handover['plan_sha256'] ==
            sha(ROOT / 'config/q2-iq2-token160-window-plan.json') and
            handover['handover_helper_sha256'] ==
            sha(ROOT / 'tools/q2-iq2-token160-handover.py'),
            'Handover chain differs')
    require(type(release['retired_identities']) is int and
            type(release['retired_groups']) is int and
            release['retired_identities'] == len(old['retired_identities']) + 1 and
            release['retired_groups'] == len(old['retired_groups']) + 1,
            'Original terminal receipt defect differs')
    require(handover['retired_identities'] ==
            old['retired_identities'] +
            [{'pid': result['pid'], 'start_ticks': result['start_ticks']}] and
            handover['retired_groups'] ==
            sorted(set(old['retired_groups']) | {result['process_group']}),
            'Full retired inventory differs')
    require(handover['core_cpu_lease'] == old['core_cpu_lease'] and
            handover['leases'] == old['leases'] and
            handover['models'] == old['models'] and
            handover['kfd'] == [] and handover['leases_free'] == 5 and
            handover['models_unchanged'] == 7 and
            not handover['gpu_reserved'] and not handover['model_access'] and
            not handover['remote_cleanup'], 'Lease/model/release state differs')
    check = (EVIDENCE / 'handover-remote-check.txt').read_text().splitlines()
    require(len(check) == 3 and
            check[0].split()[0] == sha(handover_path) and
            check[1].split()[0] ==
            sha(ROOT / 'tools/q2-iq2-token160-handover.py'),
            'Remote handover hashes differ')
    latest = json.loads(check[2])
    require(latest['event'] == 'window_release' and
            latest['receipt_sha256'] == sha(handover_path) and
            latest['owner'] == 'synapse-lie-q2' and
            latest['label'] == handover['label'],
            'Remote registry handover differs')
    summary = {
        'schema': 'synapse-lie.q2-iq2-token160-handover-summary.v1',
        'original_release_sha256': sha(release_path),
        'handover_release_sha256': sha(handover_path),
        'prior_full_release_sha256': sha(old_path),
        'component_result_sha256': sha(result_path),
        'retired_identity_count': len(handover['retired_identities']),
        'retired_group_count': len(handover['retired_groups']),
        'lease_count': len(handover['leases']) + 1,
        'model_stat_count': len(handover['models']),
        'remote_registry_receipt_exact': True,
        'kfd_empty': True,
        'remote_cleanup': False,
        'original_receipt_preserved': True,
        'reason': 'The terminal release stored process inventory counts; the append-only handover restores full identity lists for future preflight.',
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
