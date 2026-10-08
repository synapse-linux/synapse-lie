<!-- SPDX-License-Identifier: MIT -->

# Synapse LIE GitHub Pages site

This is the static site published from `gh-pages` at
<https://synapse-linux.github.io/synapse-lie/>. It has no third-party
JavaScript, remote fonts, build step or CDN. Relative links work under the
`/synapse-lie/` project path.

The benchmark explorer is driven by `data/catalog.json`. It lists workloads,
model weights and GPU platforms independently; a combination without qualified
data displays an explicit empty state. To add a result, place the qualified CSV
under `data/`, add a catalog entry with a supported `format`, and document its
method, quality limits and source hash here. Current formats are:

| Format | CSV fields read | Display |
| --- | --- | --- |
| `core-flow-v1` | `tokens`, `users`, phase rates and seconds | One complete literary prompt; or serialized prefill plus native batch decode. |
| `full-prefill-v1` | `model`, `prompt_tokens`, `prefill_chunk`, measured `warmup=False` rows and phase rates/seconds | Full prompt from empty state through 128K. |

The UI does not overlay results from these two protocols. Prefill and decode
remain distinct. A model/platform without a measured CSV never receives a
fabricated number.

## Source and quality

Both source CSVs are copied byte-for-byte from
`feature/antirez-compat-audit` at
`6d0098a0f4ac60c3f13946e5d017f6e206ac168e`:

| Site file | Original in that branch | SHA-256 |
| --- | --- | --- |
| `data/q2-core-model-flow-2k8k.csv` | `docs/figures/q2-core-model-flow-2k8k.csv` | `319339b4964fea1d96667d02dfcb5fec1f6850894a71c9e739904869b7ee0bc1` |
| `data/q2-core-model-flow-2k8k-quality.json` | `docs/figures/q2-core-model-flow-2k8k-quality.json` | `0692edb1899bf328401d8567b00b2e44856a16fce3428732b7d1c0b6f2bd79b5` |
| `data/q2-counting-curve128.csv` | `docs/figures/q2-counting-curve128.csv` | `7936e157176ce65996f4d416eb4e6877ec123a372606c378422136cfba10c77c` |

The literary-prompt dataset has 20 original-weight GPU arms, with one sample
per arm, no warmup, model loading excluded. It uses exact 2K/4K/6K/8K
prefixes of *I promessi sposi*, Strix Halo/gfx1151 and IOMMU off. For one
user, the four C1 rows form the site's “One request” view. For several users,
prefill is serialized and native decode is batched. C1 output matches the
saved single-user reference; C2–C8 output differs from C1, so batch output
equivalence is **not qualified**. See `docs/Q2-CORE-MULTI-2K8K.md` at the
source commit.

The full-context dataset has 176 measured combinations (112 Q2, 64 UD-Q4)
and a warmup row for each, 352 rows total. It uses an exact repeated counting
chat, IOMMU on, empty state at every point, 128 generated tokens, and one
measured repetition after one warmup. Q2 has 2K/4K/8K chunk settings; UD-Q4
has 2K. Identical physical prompts and matching continuations at common
frontiers are recorded, but this text does not establish broad quality. See
`docs/Q2-COUNTING-CURVE128.md` at the source commit. These results are not a
matched comparison against the literary-prompt run.

## Build information

The site leads with `make strix-halo`, implemented in
`feature/integrate-antirez-qwen` at `d415d8dfd132650b7d6927439ddea067de152f69`.
That target configures the verified pinned provider for gfx1151 and builds the
GPU-enabled server and native tools under `build/strix-halo/`. It does not
install packages, download weights or start a service. Its host-side build
contract tests pass; a new end-to-end HIP build was not run for this entry
point. The page keeps a separate advanced C17-only build command visibly
distinct from actual GPU inference. Python is not linked into or required to
run the server; historical Python test oracles are opt-in.

## Local check and publication

From this worktree, run `python3 -m http.server 8000 --bind 127.0.0.1` only
to preview this static site locally, then open `http://127.0.0.1:8000/`.
That preview command is unrelated to the LIE server runtime. A direct
`file://` visit may block CSV fetches.

GitHub Pages uses **Settings → Pages → Deploy from a branch → gh-pages →
/(root)**. The `.nojekyll` file makes GitHub serve the static files directly.
No custom domain is configured. GitHub's
[branch-publishing instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
describe the repository setting.
