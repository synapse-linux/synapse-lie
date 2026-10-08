<!-- SPDX-License-Identifier: MIT -->
# LIE routed expert cache provenance

The experimental provider derives from independently fetched official Gufo
f783fedb9bea2ec7de941f6da4e02f4a4596b29e through retained ssm-fixed-bounds.
Original licenses and notices remain. No sibling-workspace or DS4 project
source/artifact is imported. DS4's official budgeted Q8/F16 cache is a design
reference; this is a new IQ2/Q2_K integration for the Qwen executor.

First-party C17 accounting, source generator, conversion, cache selection and
fixture code are MIT. Kernel template bodies and launch wrappers are adapted
from the retained Gufo numerical source under its original MIT notices. The
independent fixture's 256-entry IQ2 byte-magnitude table is copied from the
recorded official mmq/ggml-common.h; it retains its upstream attribution and
MIT license. Original table/license remain in the complete provider inventory.

Three source attempts, complete patches and the failed first compilation remain.
Only revision3 is selected for new qualification. [Mechanism and status](../../docs/Q2-EXPERT-CACHE.md).
