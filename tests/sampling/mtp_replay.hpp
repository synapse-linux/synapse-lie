// SPDX-License-Identifier: MIT
// Independent saved MTP controller replay; no model or device forward.
#ifndef LIE_MTP_REPLAY_HPP
#define LIE_MTP_REPLAY_HPP
namespace mtp_model = gufo::models::qwen38_flash_next;
uint64_t rng_hex(const Value &v, const char *key) {
  const auto value = string(v, key); require(value.size() == 16, "MTP RNG width invalid");
  uint64_t result = 0;
  for (const auto c : value) {
    require((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'), "MTP RNG encoding invalid");
    result = (result << 4) | static_cast<uint64_t>(c <= '9' ? c - '0' : c - 'a' + 10);
  }
  return result;
}
std::vector<TokenId> optional_tokens(const Value &v, const char *key, size_t limit, size_t vocab) {
  const auto &array = field(v, key); require(array.is_array(), "MTP token array invalid");
  return array.items().empty() ? std::vector<TokenId>{} : tokens(v, key, limit, vocab);
}
std::vector<unsigned char> mtp_blob(int directory, const Value &v, const std::string &name,
                                  size_t bytes, uint64_t &total_bytes) {
  keys(v, {"file", "sha256", "bytes"});
  constexpr uint64_t maximum = UINT64_C(4) * 1024 * 1024 * 1024;
  require(bytes <= maximum - total_bytes, "MTP aggregate blob budget exceeded");
  require(string(v, "file") == name && integer(v, "bytes", max_vocab * 4) == bytes, "MTP blob identity invalid");
  struct stat before{}, after{};
  require(!fstatat(directory, name.c_str(), &before, AT_SYMLINK_NOFOLLOW) && S_ISREG(before.st_mode) &&
      before.st_size == static_cast<off_t>(bytes), "MTP blob incomplete or not regular");
  FD input(openat(directory, name.c_str(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC));
  require(!fstat(input.fd, &after) && S_ISREG(after.st_mode) && after.st_size == before.st_size &&
      after.st_dev == before.st_dev && after.st_ino == before.st_ino, "MTP blob identity changed");
  std::vector<unsigned char> data(bytes);
  for (size_t at = 0; at < bytes;) {
    const ssize_t n = read(input.fd, data.data() + at, bytes - at);
    if (n < 0 && errno == EINTR) continue;
    require(n > 0, "MTP blob short read"); at += static_cast<size_t>(n);
  }
  unsigned char hash[32]; unsigned length = 0; char hex[65];
  require(EVP_Digest(data.data(), bytes, hash, &length, EVP_sha256(), nullptr) && length == 32, "MTP blob hash failed");
  for (unsigned i = 0; i < length; ++i) std::snprintf(hex + i * 2, 3, "%02x", hash[i]);
  require(string(v, "sha256") == hex, "MTP blob checksum mismatch");
  total_bytes += bytes; return data;
}
mtp_model::MtpProposal mtp_proposal(const Value &v, size_t vocab) {
  keys(v, {"ids", "probabilities", "token", "probability"});
  const auto ids = tokens(v, "ids", 64, vocab); const auto &mass = field(v, "probabilities");
  require(mass.is_array() && mass.items().size() == ids.size(), "MTP proposal mass length invalid");
  mtp_model::MtpProposal q; q.size = ids.size();
  q.token = static_cast<TokenId>(integer(v, "token", vocab - 1));
  const double selected = real(v, "probability"); q.probability = static_cast<float>(selected);
  require(selected == q.probability && selected > 0 && selected <= 1, "MTP selected mass invalid");
  double total = 0, chosen = 0;
  for (size_t i = 0; i < q.size; ++i) {
    require(std::find(ids.begin(), ids.begin() + i, ids[i]) == ids.begin() + i, "MTP proposal ID duplicated");
    require(mass.items()[i].is_number(), "MTP proposal mass type invalid");
    const double p = mass.items()[i].as_double();
    require(std::isfinite(p) && p >= 0 && p <= 1 && static_cast<float>(p) == p, "MTP proposal F32 mass invalid");
    q.ids[i] = ids[i]; q.probabilities[i] = static_cast<float>(p); total += p;
    if (ids[i] == q.token) chosen += p;
  }
  require(total == 1 && chosen == selected, "MTP proposal total or selected mass inconsistent"); return q;
}
void same_proposal(const mtp_model::MtpProposal &a, const mtp_model::MtpProposal &b) {
  require(a.size == b.size && a.token == b.token && a.probability == b.probability &&
      std::equal(a.ids.begin(), a.ids.begin() + a.size, b.ids.begin()) &&
      std::equal(a.probabilities.begin(), a.probabilities.begin() + a.size, b.probabilities.begin()),
      "MTP captured proposal differs from actual replay or pending chain");
}
void observed_history(const Value &v, const SamplerState &sampler, size_t vocab) {
  const auto history = optional_tokens(v, "history_ids", 64, vocab);
  require(std::ranges::equal(history, sampler.history()), "MTP captured sampler history differs");
  const auto &penalties = field(v, "penalties"); const auto expected = sampler.penalties();
  require(penalties.is_array() && penalties.items().size() == expected.size(), "MTP penalty length differs");
  for (size_t i = 0; i < expected.size(); ++i) {
    const auto &p = penalties.items()[i]; keys(p, {"token", "generated_count", "repeated"});
    require(integer(p, "token", vocab - 1) == expected[i].token &&
        integer(p, "generated_count", 135) == expected[i].generated_count &&
        integer(p, "repeated", 64) == expected[i].repeated, "MTP captured penalty state differs");
  }
}
uint64_t independent_next_word(uint64_t &state) {
  uint64_t x = state ? state : UINT64_C(0x9e3779b97f4a7c15);
  x ^= x >> 12; x ^= x << 25; x ^= x >> 27; state = x;
  return x * UINT64_C(0x2545f4914f6cdd1d);
}
void proposal_oracle(const SamplingDistribution &p, std::span<const TokenId> mapping,
                     const mtp_model::MtpProposal &q, uint64_t before, uint64_t after) {
  constexpr uint32_t units = 1u << 24;
  std::vector<uint32_t> mass; uint64_t total = 0;
  require(p.entries().size() == q.size, "MTP proposal support count differs");
  for (size_t i = 0; i < q.size; ++i) {
    const auto entry = p.entries()[i];
    require(entry.token < mapping.size() && mapping[entry.token] == q.ids[i], "MTP proposal mapping differs");
    const auto value = static_cast<uint32_t>(std::floor(entry.value * units)); mass.push_back(value); total += value;
  }
  require(total <= units, "MTP integer proposal mass overflow"); mass[0] += units - static_cast<uint32_t>(total);
  auto state = before; const uint32_t target = static_cast<uint32_t>(uniform(state) * units);
  uint64_t cumulative = 0; std::optional<TokenId> token;
  for (size_t i = 0; i < mass.size(); ++i) {
    require(q.probabilities[i] == static_cast<float>(mass[i]) / units, "MTP proposal quantization differs");
    cumulative += mass[i]; if (!token && target < cumulative) token = q.ids[i];
  }
  require(token && *token == q.token && state == after, "MTP integer proposal draw/RNG differs");
}
std::pair<TokenId, bool> verification_oracle(const SamplingDistribution &p,
    const mtp_model::MtpProposal &q, uint64_t &rng) {
  double probability = 0; for (const auto entry : p.entries()) if (entry.token == q.token) probability += entry.value;
  if (uniform(rng) * q.probability < probability) return {q.token, true};
  std::vector<Probability> residual_mass; double total = 0;
  for (auto entry : p.entries()) {
    double draft = 0; for (size_t i = 0; i < q.size; ++i) if (q.ids[i] == entry.token) draft += q.probabilities[i];
    const double residual_value = std::max(entry.value - draft, 0.0);
    if (residual_value > 0) { residual_mass.push_back({entry.token, residual_value}); total += residual_value; }
  }
  if (!(total > 0)) return {draw(p.entries(), rng), false};
  for (auto &entry : residual_mass) entry.value /= total;
  return {draw(residual_mass, rng), false};
}
int replay_mtp(int directory, FILE *file, const Value &identity, bool allow_synthetic) {
  keys(identity, {"event", "schema", "program", "build_id", "engine", "source_pin", "dense_sampling", "synthetic",
      "classification", "scope", "row_encoding", "decode_mode", "mtp_model", "mtp_draft_tokens_requested",
      "observer_abi", "greedy_reservation", "tools", "eos_policy", "context", "prefill_chunk", "profiles", "tokens_per_profile"});
  const bool synthetic = boolean(identity, "synthetic"), tools = boolean(identity, "tools");
  require(!synthetic || allow_synthetic, "synthetic MTP capture requires explicit --allow-synthetic");
  require(string(identity, "schema") == "synapse-lie.sampling-capture.v3" &&
      string(identity, "program") == "lie-sampling-capture" && string(identity, "decode_mode") == "mtp" &&
      !string(identity, "mtp_model").empty() && integer(identity, "observer_abi", 1) == 1 &&
      integer(identity, "greedy_reservation", 1) == 1 && integer(identity, "context", 8192) == 8192 &&
      integer(identity, "prefill_chunk", 2048) == 2048 && integer(identity, "profiles", 6) == 6 &&
      string(identity, "classification") == (synthetic ? "NOT-INFERENCE" : "ORIGINAL-WEIGHT-ROW-CAPTURE") &&
      string(identity, "row_encoding") == "IEEE754-F32-little-endian" &&
      string(identity, "eos_policy") == (tools ? "stop; un-emitted EOS is captured without position advance" :
                                                "ignore; EOS remains an ordinary sampled token"), "MTP capture identity invalid");
  const unsigned drafts = static_cast<unsigned>(integer(identity, "mtp_draft_tokens_requested", 7));
  const unsigned budget = static_cast<unsigned>(integer(identity, "tokens_per_profile", 128));
  require(drafts && budget, "MTP empty draft/output budget");
  std::printf("classification=%s scope=MTP-target-proposal-verification-controller;greedy-host-head;not-performance\n",
      synthetic ? "NOT-INFERENCE" : "CAPTURE-DECLARED-ORIGINAL-WEIGHTS-REQUIRE-SUPERVISOR-PROVENANCE");
  std::vector<Piece> pieces; std::vector<TokenId> prompt, output_ids, cycle_ids;
  std::vector<uint32_t> generated, draft_generated;
  std::unique_ptr<SamplerState> sampler, draft_sampler;
  SamplingConfig current; JsonConstraint::State grammar_state; std::string output;
  std::vector<mtp_model::MtpProposal> proposals;
  std::optional<TokenId> anchor, correction;
  size_t vocab = 0; unsigned profile = 0, cycle = 0, index = 0, all_rows = 0, verification = 0, reservation = 0;
  uint64_t draft_rng = 0, total_bytes = 0;
  bool complete = false, in_cycle = false, stopped = false, anchor_committed = false;
  unsigned proposals_total = 0, accepted_total = 0, rejected_total = 0, deferred_total = 0;
  auto is_stop = [&](TokenId token) { return tools && token < pieces.size() && pieces[token].stop; };
  auto accept = [&](TokenId token) {
    sampler->Accept(token); ++generated[token]; cycle_ids.push_back(token);
    if (tools) {
      const auto &piece = pieces.at(token);
      require(!piece.stop && !piece.text.empty() && piece.text.find('\0') == std::string::npos &&
          piece.text.size() <= LIE_CAPTURE_OUTPUT_BYTES_MAX - output.size(), "MTP emitted tool piece invalid");
      output += piece.text;
      for (const unsigned char byte : piece.text) grammar_state = current.constraint->grammar->Advance(grammar_state, byte);
      require(!grammar_state.empty(), "MTP emitted token violates independent grammar");
    }
  };
  auto accept_anchor = [&] {
    require(anchor.has_value(), "MTP anchor missing");
    if (!anchor_committed && !stopped) { accept(*anchor); anchor_committed = true; }
  };
  std::vector<char> line(max_line + 2);
  while (std::fgets(line.data(), static_cast<int>(line.size()), file)) {
    const size_t bytes = std::strlen(line.data());
    require(bytes && bytes <= max_line && line[bytes - 1] == '\n', "MTP JSON line truncated, oversized or contains NUL");
    const auto v = gufo::json::parse(std::string_view(line.data(), bytes));
    require(!complete, "MTP data after completion"); const auto event = string(v, "event");
    if (event == "vocabulary") {
      require(tools && pieces.empty() && !sampler && !profile, "MTP vocabulary ordering invalid");
      pieces = vocabulary_file(directory, v);
    } else if (event == "profile_begin") {
      if (tools) keys(v, {"event", "profile", "name", "vocab", "generation", "prompt_ids", "constraint"});
      else keys(v, {"event", "profile", "name", "vocab", "generation", "prompt_ids"});
      require(!sampler && !in_cycle && profile < 6 && integer(v, "profile", 5) == profile, "MTP profile ordering invalid");
      const char *names[]{"greedy", "ds4-temperature1-minp", "top-k", "nucleus-minp", "generated-penalties", "temperature2-negative-penalties"};
      require(string(v, "name") == names[profile], "MTP profile name mismatch");
      vocab = integer(v, "vocab", max_vocab); require(vocab, "MTP vocabulary empty");
      current = config(field(v, "generation"), profile); prompt = tokens(v, "prompt_ids", 8192 - budget, vocab);
      if (tools) {
        require(vocab == pieces.size(), "MTP vocabulary missing or inconsistent");
        current.constraint = tool_constraint(field(v, "constraint"), pieces);
        grammar_state = current.constraint->grammar->Start(); output.clear();
      }
      sampler = std::make_unique<SamplerState>(current, prompt); generated.assign(vocab, 0);
      output_ids.clear(); cycle = index = 0; stopped = false;
    } else if (event == "cycle_begin") {
      keys(v, {"event", "profile", "cycle", "position", "reservation"});
      require(sampler && !in_cycle && !stopped && output_ids.size() < budget && cycle < budget &&
          integer(v, "profile", 5) == profile && integer(v, "cycle", 127) == cycle &&
          integer(v, "position", 8192) == prompt.size() + output_ids.size(), "MTP cycle admission invalid");
      reservation = static_cast<unsigned>(integer(v, "reservation", drafts + 1));
      require(reservation == (profile ? std::min<size_t>(drafts + 1, budget - output_ids.size()) : 1), "MTP reservation differs");
      in_cycle = true; anchor.reset(); correction.reset(); anchor_committed = false; verification = 0;
      proposals.clear(); draft_sampler.reset(); cycle_ids.clear();
    } else if (event == "sampling_trace") {
      keys(v, {"event", "profile", "cycle", "index", "kind", "token", "accepted", "deferred", "rng_before", "rng_after",
          "logit_count", "raw", "logit_ids", "history_ids", "penalties", "allowed", "proposal"});
      require(sampler && in_cycle && !stopped && !correction && index < 128 * 9 &&
          integer(v, "profile", 5) == profile && integer(v, "cycle", 127) == cycle && integer(v, "index", 128 * 9 - 1) == index,
          "MTP trace ordering invalid");
      const auto kind = string(v, "kind"); const size_t count = integer(v, "logit_count", max_vocab);
      require(count && (kind == "proposal" ? count <= 64 : count == vocab), "MTP raw row geometry invalid");
      const std::string prefix = "profile-" + std::to_string(profile) + "-trace-" + std::to_string(index);
      const auto raw = mtp_blob(directory, field(v, "raw"), prefix + ".f32le", count * 4, total_bytes);
      std::vector<float> logits(count); std::memcpy(logits.data(), raw.data(), raw.size());
      for (const auto value : logits) require(std::isfinite(value), "MTP raw row nonfinite");
      const auto mapping = optional_tokens(v, "logit_ids", 64, vocab);
      const auto before = rng_hex(v, "rng_before"), after = rng_hex(v, "rng_after");
      const auto token = static_cast<TokenId>(integer(v, "token", vocab - 1));
      const bool accepted = integer(v, "accepted", 1), deferred = integer(v, "deferred", 1);
      std::printf("profile=%u cycle=%u index=%u kind=%s sha256=%s before=%016llx after=%016llx\n", profile, cycle, index,
          kind.c_str(), string(field(v, "raw"), "sha256").c_str(), (unsigned long long)before, (unsigned long long)after);
      if (kind == "proposal") {
        require(profile && anchor && !verification && proposals.size() < reservation - 1 && mapping.size() == count &&
            field(v, "allowed").is_null() && !accepted && !deferred, "MTP proposal phase invalid");
        for (size_t i = 0; i < count; ++i) require(std::find(mapping.begin(), mapping.begin() + i, mapping[i]) == mapping.begin() + i,
            "MTP compact logit ID duplicated");
        if (!draft_sampler) {
          auto independent_state = sampler->rng_state(); const auto seed = independent_next_word(independent_state);
          require(NextRandom(sampler->mutable_rng_state()) == seed && sampler->rng_state() == independent_state,
              "MTP independent cycle seed differs");
          draft_rng = seed; accept_anchor(); draft_sampler = std::make_unique<SamplerState>(sampler->WithoutConstraint());
          draft_generated = generated;
        }
        require(before == draft_rng, "MTP proposal stream RNG frontier differs"); observed_history(v, *draft_sampler, vocab);
        const auto p = draft_sampler->Distribution(logits, mapping);
        std::vector<uint32_t> compact_generated; for (const auto id : mapping) compact_generated.push_back(draft_generated[id]);
        check_mass(p, math_distribution(logits, current, compact_generated), count);
        for (const auto entry : p.entries()) std::printf("q-base=%u:%a\n", entry.token, entry.value);
        mtp_model::MtpCandidateLogits candidates; candidates.size = count;
        std::copy(mapping.begin(), mapping.end(), candidates.ids.begin()); std::copy(logits.begin(), logits.end(), candidates.logits.begin());
        const auto q = mtp_model::SampleMtpProposal(candidates, *draft_sampler, &draft_rng), actual = mtp_proposal(field(v, "proposal"), vocab);
        same_proposal(q, actual); proposal_oracle(p, mapping, actual, before, after);
        require(q.token == token && draft_rng == after, "MTP proposal draw differs");
        for (size_t i = 0; i < q.size; ++i) std::printf("q=%u:%a\n", q.ids[i], double(q.probabilities[i]));
        proposals.push_back(q); draft_sampler->Accept(q.token); ++draft_generated[q.token]; ++proposals_total;
      } else {
        require(mapping.empty() && (kind == "target-draw" || kind == "verification"), "MTP target role/mapping invalid");
        if (kind == "target-draw") require(!anchor && proposals.empty() && !accepted && field(v, "proposal").is_null(), "MTP duplicate target draw");
        else { require(!deferred && verification < proposals.size(), "MTP verification phase invalid"); accept_anchor(); }
        observed_history(v, *sampler, vocab); require(before == sampler->rng_state(), "MTP target RNG frontier differs");
        std::vector<uint8_t> allowed;
        if (tools) {
          allowed = direct_allowed(*current.constraint->grammar, grammar_state, pieces);
          const auto mask = mtp_blob(directory, field(v, "allowed"), prefix + ".u8", vocab, total_bytes);
          require(mask == allowed && *current.constraint->Allowed(grammar_state) == allowed, "MTP independent full mask differs");
          std::fputs("allowed=", stdout); for (const auto bit : allowed) std::printf("%u", unsigned(bit)); std::putchar('\n');
        } else require(field(v, "allowed").is_null(), "MTP unconstrained mask unexpected");
        const auto p = sampler->Distribution(logits); check_mass(p, math_distribution(logits, current, generated, allowed), vocab);
        for (const auto entry : p.entries()) std::printf("p=%u:%a\n", entry.token, entry.value);
        if (kind == "target-draw") {
          const auto state = sampler->SaveDrawState(); require(deferred == state.pending.has_value(), "MTP deferred frontier differs");
          auto independent_rng = before; const auto independent = deferred ? *state.pending : draw(p.entries(), independent_rng);
          require(sampler->Sample(logits) == independent && independent == token && sampler->rng_state() == after && independent_rng == after,
              "MTP target draw/RNG differs");
          anchor = token; stopped = is_stop(token); if (deferred) ++deferred_total;
        } else {
          const auto q = mtp_proposal(field(v, "proposal"), vocab); same_proposal(q, proposals[verification]);
          auto independent_rng = before; const auto independent = verification_oracle(p, q, independent_rng);
          const auto result = mtp_model::VerifyMtpProposal(logits, q, *sampler);
          require(result.token == independent.first && result.accepted == independent.second && result.token == token &&
              result.accepted == accepted && independent_rng == after && sampler->rng_state() == after, "MTP acceptance/residual/RNG differs");
          ++verification; if (accepted) ++accepted_total; else ++rejected_total;
          stopped = is_stop(token);
          if (!stopped) { if (accepted) accept(token); else correction = token; }
        }
      }
      ++index; ++all_rows;
    } else if (event == "cycle_complete") {
      keys(v, {"event", "profile", "cycle", "position", "drafted", "accepted", "stop", "output_ids"});
      require(in_cycle && anchor && integer(v, "profile", 5) == profile && integer(v, "cycle", 127) == cycle, "MTP cycle completion ordering invalid");
      accept_anchor();
      require(proposals.empty() || (verification && (stopped || correction || verification == proposals.size())), "MTP incomplete verification chain");
      require(integer(v, "drafted", drafts) == proposals.size() && integer(v, "accepted", drafts) == (cycle_ids.empty() ? 0 : cycle_ids.size() - 1) &&
          boolean(v, "stop") == stopped && optional_tokens(v, "output_ids", reservation, vocab) == cycle_ids &&
          integer(v, "position", 8192) == prompt.size() + output_ids.size() + cycle_ids.size(), "MTP committed frontier/counters differ");
      output_ids.insert(output_ids.end(), cycle_ids.begin(), cycle_ids.end());
      if (correction) sampler->DeferSample(*correction);
      in_cycle = false; ++cycle;
    } else if (event == "profile_complete") {
      if (tools) keys(v, {"event", "profile", "rows", "cycles", "output_ids", "tool_call"});
      else keys(v, {"event", "profile", "rows", "cycles", "output_ids"});
      require(sampler && !in_cycle && integer(v, "profile", 5) == profile && integer(v, "rows", 128 * 9) == index &&
          integer(v, "cycles", budget) == cycle && tokens(v, "output_ids", budget, vocab) == output_ids &&
          (tools ? stopped : output_ids.size() == budget), "MTP completed profile invalid");
      if (tools) completed_tool(field(v, "tool_call"), output);
      sampler.reset(); ++profile;
    } else if (event == "complete") {
      keys(v, {"event", "exit_code", "profiles", "rows"});
      require(!sampler && !in_cycle && profile == 6 && integer(v, "exit_code", 0) == 0 &&
          integer(v, "profiles", 6) == 6 && integer(v, "rows", 6 * 128 * 9) == all_rows, "MTP terminal aggregate invalid");
      complete = true;
    } else throw std::runtime_error("MTP failure or unknown event; no acceptance");
  }
  require(!std::ferror(file) && complete, "MTP terminal record missing");
  std::printf("MTP_ROWS=%u PROPOSALS=%u ACCEPTED=%u REJECTED=%u DEFERRED=%u COMPLETE_OFFLINE_WITNESSES_NOT_FULL_ACCEPTANCE\n",
      all_rows, proposals_total, accepted_total, rejected_total, deferred_total);
  return std::ferror(stdout) ? 1 : 0;
}
#endif
