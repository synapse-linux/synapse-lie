<!-- SPDX-License-Identifier: MIT -->
# Fixed-input routing diagnosis provenance

First-party Python capture/supervision, C17 host fixtures and analysis are MIT.
No new provider code is imported or changed. The exact retained1027-file
`ssm-fixed-bounds` inventory remains based on independently fetched Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e` with its previously recorded ports.
No sibling CachyOS or DS4 source/artifact is imported.

The installed GDB reads existing host routing counts at the original C function
entry. Its APIs are documented by the GNU project:
[Python breakpoints](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Breakpoints-In-Python.html),
[inferior memory reads](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Inferiors-In-Python.html),
and [events](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Events-In-Python.html).
The read callback changes no inferior execution state. Execution control and
owned-child shutdown happen outside it. No GDB code is copied or installed.

The x86-64 entry ABI and process-group behavior are exercised on .157 with an
owned CPU fixture before model execution. Instrumented times are not new
performance evidence. The exact saved binary, source, libraries and fixed
input are bound by [the plan](../../config/q2-current-routing-v2-plan.json).
Capture and the initial supervision failure remain in local `evidence/` and
durable remote `run/` directories. No source is stored only in `/tmp`.

The proposed BN16 dispatch is an unmeasured first-party map specialization;
the current study uses already compiled upstream-derived kernels and changes
none of their source or arithmetic. See [the report](../../docs/Q2-CURRENT-ROUTING.md).
