<!-- SPDX-License-Identifier: MIT -->
# Cache utility/compression CPU evidence

13 focused ASan/UBSan suites with both features ON; 6 headless suites with both
OFF and no LZ4 dependency. Final state-benchmark/build-info changes also pass
focused benchmark/HTTP SSD reruns. Original Python/matplotlib failures remain
in the receipt/archive; no dependency was installed. Builds use at most -j2.
The receipt binds all source files and ON/OFF Release executables. CPU fixtures
are NOT-INFERENCE and establish no original-weight compression ratio or speedup.
