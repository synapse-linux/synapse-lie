# SPDX-License-Identifier: MIT
"""Validate a window while allowing its owned, terminal cohort events."""


def active_window(rows, digest, admitted_at):
    windows=[row for row in rows if row.get('event') in ('window_admit','window_release')]
    if not windows:
        raise ValueError('No coordinated window event')
    latest=windows[-1]
    if (latest.get('event')!='window_admit' or latest.get('owner')!='synapse-lie-q2' or
            latest.get('receipt_sha256')!=digest or latest.get('at')!=admitted_at):
        raise ValueError('Expected active admission differs')
    for row in rows:
        if row.get('at','')>=admitted_at and row.get('owner')!='synapse-lie-q2':
            raise ValueError('Foreign event inside coordinated window')
    return latest
