<!-- SPDX-License-Identifier: MIT -->
# Numeric-byte codec CPU qualification

13 focused ASan/UBSan suites ON, six headless suites OFF, final report check.
Legacy LZ4 read, exact special bits, final byte tails, random/raw fallback,
static codec contexts, bounds, core restore and SSD restart. No CPU model
forward or GPU performance claim. All commands exit 0; local thermal guard 98 C.
