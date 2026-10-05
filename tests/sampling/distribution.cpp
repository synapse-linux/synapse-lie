// SPDX-License-Identifier: MIT
// Complete ordered/compact/MTP witnesses against the independent pin.
// NOT-INFERENCE.
#include "src/core/sampling.hpp"
#include "src/models/qwen38_flash_next/mtp_sampling.hpp"
#include <cassert>
#include <cfloat>
#include <cmath>
#include <cstdio>
#include <limits>
#include <vector>
using namespace gufo::sampling;
namespace qfn = gufo::models::qwen38_flash_next;
static void entries(const SamplingDistribution &d, const char *name) {
  for (const auto &p : d.entries())
    std::printf("%s=%u:%a\n", name, p.token, p.value);
  std::printf("best=%u\n", d.best_token());
}
static void grammar(void) {
  auto schema = gufo::json::parse(
      R"({"type":"object","properties":{"ok":{"type":"boolean","enum":[true]}},"required":["ok"],"additionalProperties":false})");
  auto grammar = JsonConstraint::Compile(schema, true);
  const std::string pieces[] = {"{",    "}",     "\"ok\"", ":",
                                "true", "wrong", "",       "{\"ok\":true}"};
  auto vocab = std::make_shared<ConstraintVocabulary>(8, [&](uint32_t t) {
    return ConstraintVocabulary::Piece{pieces[t], t == 6};
  });
  auto constraint = std::make_shared<TokenConstraint>();
  constraint->grammar = grammar;
  constraint->vocabulary = vocab;
  SamplingConfig c;
  c.seed = 77;
  c.temperature = 1;
  c.constraint = constraint;
  c.frequency_penalty = .5f;
  c.repeat_penalty = 1.2f;
  const float logits[] = {1, 2, 3, 4, 5, 6, 7, 8};
  SamplerState sampler(c);
  qfn::MtpCandidateLogits candidates;
  candidates.size = 3;
  candidates.ids = {5, 7, 0};
  candidates.logits = {8, 2, 1};
  for (uint64_t seed = 0; seed < 32; ++seed) {
    auto rng = seed;
    auto s = sampler;
    auto q = qfn::SampleMtpProposal(candidates, s, &rng);
    s.SetRngState(rng);
    auto v = qfn::VerifyMtpProposal(logits, q, s);
    std::printf("grammar=%llu q=%u:%a rng=%llu decision=%u:%d end=%llu\n",
                (unsigned long long)seed, q.token, double(q.probability),
                (unsigned long long)rng, v.token, v.accepted,
                (unsigned long long)s.rng_state());
  }
}
static void raw(void) {
  const double weights[] = {
      0,   1,     std::numeric_limits<double>::denorm_min(), .25, .25, 4,
      100, 1e-200};
  for (unsigned n = 1; n <= 8; ++n) {
    std::vector<Probability> p;
    for (unsigned i = 0; i < n; ++i)
      p.push_back({17 - i, weights[i] + (i ? 0 : 1)});
    SamplingDistribution d(p);
    entries(d, "normalized");
    const uint32_t ids[] = {15, 15, 20, 11, 15, 11, 0};
    const float qs[] = {.125f, .25f, 0, .125f, 1e-20f, FLT_MAX, .5f};
    for (unsigned size = 0; size <= 7; ++size)
      for (uint64_t seed = 0; seed < 16; ++seed) {
        auto rng = seed;
        auto token = d.SampleResidual(std::span(ids).first(size),
                                      std::span(qs).first(size), &rng);
        std::printf("residual n=%u sparse=%u seed=%llu token=%u rng=%llu\n", n,
                    size, (unsigned long long)seed, token,
                    (unsigned long long)rng);
      }
  }
}
int main() {
  unsigned profiles = 0, decisions = 0;
  const size_t sizes[] = {1, 2, 3, 8, 32, 64};
  for (auto size : sizes)
    for (unsigned geometry = 0; geometry < 4; ++geometry)
      for (unsigned penalty = 0; penalty < 4; ++penalty)
        for (unsigned filter = 0; filter < 6; ++filter)
          for (float temperature : {0.0f, .1f, 1.0f}) {
            SamplingConfig c;
            c.seed = 773;
            c.temperature = temperature;
            c.repeat_last_n = 3;
            if (penalty & 1)
              c.repeat_penalty = 1.2f;
            if (penalty & 2) {
              c.frequency_penalty = .5f;
              c.presence_penalty = -.2f;
            }
            if (filter == 1)
              c.top_k = 1;
            if (filter == 2) {
              c.top_k = 7;
              c.top_p = .75f;
              c.min_p = .05f;
            }
            if (filter == 3)
              c.top_p = .999f;
            if (filter == 4) {
              c.top_p = .45f;
              c.min_p = .95f;
              c.min_keep = 5;
            }
            if (filter == 5) {
              c.min_p = .99f;
              c.min_keep = 2;
            }
            const uint32_t prompt[] = {0, 3, 13, 13, 16},
                           accepted[] = {13, 13, 4, 5, 16, 16, 16, 3};
            SamplerState sampler(c, prompt);
            sampler.Accept(accepted);
            std::vector<float> logits(257);
            qfn::MtpCandidateLogits candidates;
            candidates.size = size;
            for (size_t i = 0; i < logits.size(); ++i) {
              logits[i] = geometry == 0   ? 0.0f
                          : geometry == 1 ? float(i % 11) - 5
                          : geometry == 2
                              ? float(i) / 7
                              : float(std::sin(double(i) * .17) * 3);
              if (geometry == 3 && i % 23 == 0)
                logits[i] = -std::numeric_limits<float>::infinity();
            }
            for (size_t i = 0; i < size; ++i) {
              candidates.ids[i] = (uint32_t)((i * 13 + 3) % 257);
              candidates.logits[i] = geometry == 0   ? 0.0f
                                     : geometry == 1 ? float(i % 11) - 5
                                     : geometry == 2
                                         ? float(i) / 7
                                         : float(std::cos(double(i) * .17) * 3);
            }
            std::printf("profile=%u size=%zu geometry=%u penalty=%u filter=%u "
                        "temperature=%a\n",
                        profiles++, size, geometry, penalty, filter,
                        double(temperature));
            const auto compact =
                sampler.Distribution(std::span(candidates.logits).first(size),
                                     std::span(candidates.ids).first(size));
            entries(compact, "compact");
            const auto target = sampler.Distribution(logits);
            entries(target, "target");
            for (uint64_t seed = 0; seed < 4; ++seed) {
              auto rng = seed;
              const auto proposal =
                  qfn::SampleMtpProposal(candidates, sampler, &rng);
              std::printf("q seed=%llu token=%u probability=%a rng=%llu\n",
                          (unsigned long long)seed, proposal.token,
                          double(proposal.probability),
                          (unsigned long long)rng);
              for (size_t i = 0; i < proposal.size; ++i)
                std::printf("q-entry=%u:%a\n", proposal.ids[i],
                            double(proposal.probabilities[i]));
              auto verification = sampler;
              verification.SetRngState(rng);
              auto result =
                  qfn::VerifyMtpProposal(logits, proposal, verification);
              std::printf("v=%u:%d rng=%llu\n", result.token, result.accepted,
                          (unsigned long long)verification.rng_state());
              ++decisions;
            }
          }
  raw();
  grammar();
  std::printf("PROFILES=%u DECISIONS=%u "
              "COMPLETE_DISTRIBUTION_HOST_WITNESSES_NOT_INFERENCE\n",
              profiles, decisions);
}
