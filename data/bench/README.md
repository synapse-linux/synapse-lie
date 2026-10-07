<!-- SPDX-License-Identifier: MIT -->

# Native benchmark corpus

`promessi_sposi.txt` is Alessandro Manzoni's *I promessi sposi*, independently
retrieved from the official antirez/ds4 `speed-bench` corpus at commit
`0aaea5a238fb41a35106a551e73c8409dfb751ac`. Its SHA-256 is
`f53e0d80cb2d4492d24ebd63c7000c397b16ae70f9bf09b3763e5d8323ec209f`,
identical to the corpus observed in the owner's DS4 qualification on .157.
See `config/bench-promessi-sposi.json` for the exact source URL and size.

The novel is third-party public-domain text, not first-party MIT source.
Original bytes are preserved, without normalization, padding or rewriting.
The native benchmark tokenizes the raw text and slices exact token prefixes;
it does not apply a chat template, estimate words per token or repeat the
corpus when it is too short. Tokenizer IDs, source hash and actual counts are
recorded separately from inference timings. Token counts depend on the model.
