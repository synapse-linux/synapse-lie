// SPDX-License-Identifier: MIT
// Complete routing/producer/packing/down cycle with canonical slot replays.
#include "q2_expert_order_support.hpp"

static std::vector<std::uint8_t> RawChecked(Output& output,
                                            hipStream_t stream) {
  auto bytes = Read(output.device, stream);
  for (unsigned i = 0; i < 64; ++i)
    Require(bytes[i] == 0xa5 && bytes[bytes.size() - 1 - i] == 0xa5,
            "Map guard changed; refusing further device work");
  return bytes;
}
static std::vector<int> Integers(const std::vector<std::uint8_t>& raw) {
  std::vector<int> values((raw.size() - 128) / 4);
  std::memcpy(values.data(), raw.data() + 64, values.size() * 4);
  return values;
}

struct Route {
  Output padded, logical, cursor, tokens, slots;
  Route(unsigned ne, unsigned cap)
      : padded(ne + 1, false),
        logical(ne + 1, false),
        cursor(ne, false),
        tokens(cap, false),
        slots(cap, false) {}
  std::int32_t* P(Output& o) { return static_cast<std::int32_t*>(o.Data()); }
};

struct Chain {
  unsigned n, used, experts, inner, out_width, gate_width, cap;
  bool skew;
  std::vector<int> ids, pad, logical, down_tiles, narrow_tiles, wide_tiles;
  std::vector<unsigned> counts;
  std::unique_ptr<Device> id_d, count_d, input, wg, wu, wd, dt, nt, wt;
  std::array<std::unique_ptr<Route>, 2> route;
  std::array<std::unique_ptr<Output>, 2> gate, half, inverse, down;
  std::vector<std::pair<Device*, std::string>> immutable;

  Chain(unsigned tokens, unsigned top, unsigned ne, unsigned k, unsigned m,
        unsigned bn, bool nonuniform, hipStream_t stream)
      : n(tokens),
        used(top),
        experts(ne),
        inner(k),
        out_width(m),
        gate_width(bn),
        cap(q::RoutedCompactRows(n * used, ne)),
        skew(nonuniform),
        ids(n * used),
        pad(ne + 1),
        logical(ne + 1),
        counts(ne) {
    Require(used <= experts && inner % 256 == 0, "Invalid fixture shape");
    for (unsigned t = 0; t < n; ++t) {
      const unsigned base = skew && t % 4 ? (t * 73) % 64 : (t * 73) % ne;
      for (unsigned s = 0; s < used; ++s) {
        const unsigned e = (base + s) % ne;
        ids[t * used + s] = e;
        ++counts[e];
      }
    }
    for (unsigned e = 0; e < ne; ++e) {
      pad[e + 1] = pad[e] + ((counts[e] + 15) / 16) * 16;
      logical[e + 1] = logical[e] + counts[e];
      for (unsigned j = 0; j < unsigned(pad[e + 1] - pad[e]); j += 48)
        down_tiles.push_back(e | ((j / 48) << 16));
      if (bn) {
        for (unsigned j = 0; j < unsigned(pad[e + 1] - pad[e]); j += bn)
          narrow_tiles.push_back(e | ((j / bn) << 16));
      } else {
        const unsigned groups = (counts[e] + 63) / 64;
        for (unsigned j = 0; j < groups / 2; ++j)
          wide_tiles.push_back(e | (j << 16));
        if (groups & 1)
          narrow_tiles.push_back(e | ((groups - 1) << 16));
      }
    }
    auto ints = [&](const auto& values) {
      auto p = std::make_unique<Device>(values.size() * 4);
      Upload(*p, values, stream);
      return p;
    };
    id_d = ints(ids);
    count_d = ints(counts);
    dt = ints(down_tiles);
    nt = ints(narrow_tiles);
    wt = ints(wide_tiles);
    Random rng;
    std::vector<std::uint16_t> activation(std::size_t(n) * inner);
    for (auto& x : activation)
      x = HalfBits(float(int(rng.Next() >> 16) - 32768) / 262144.0f);
    input = std::make_unique<Device>(activation.size() * 2);
    Upload(*input, activation, stream);
    wg = std::make_unique<Device>(std::size_t(ne) * 640 * (inner / 256) * 66);
    wu = std::make_unique<Device>(wg->bytes);
    wd = std::make_unique<Device>(std::size_t(ne) * m * 3 * 84);
    for (Device* weight : {wg.get(), wu.get(), wd.get()}) {
      std::vector<std::uint8_t> encoded(weight->bytes);
      const unsigned block = weight == wd.get() ? 84 : 66;
      for (std::size_t off = 0; off < encoded.size(); off += block) {
        for (unsigned j = 0; j < block; ++j)
          encoded[off + j] = rng.Next() >> 24;
        const std::uint16_t scale = HalfBits(0.00125f);
        if (block == 66)
          std::memcpy(encoded.data() + off, &scale, 2);
        else {
          const std::uint16_t minimum = HalfBits(0.00075f);
          std::memcpy(encoded.data() + off + 80, &scale, 2);
          std::memcpy(encoded.data() + off + 82, &minimum, 2);
        }
      }
      Upload(*weight, encoded, stream);
    }
    for (unsigned a = 0; a < 2; ++a) {
      route[a] = std::make_unique<Route>(ne, cap);
      gate[a] = std::make_unique<Output>(std::size_t(n) * used * 640, false);
      half[a] = std::make_unique<Output>(std::size_t(n) * used * 640, true);
      inverse[a] = std::make_unique<Output>(n * used, false);
      down[a] = std::make_unique<Output>(std::size_t(n) * used * m, true);
      // The control never reads/writes logical bounds. Seed the CPU expectation
      // there so its untouched bytes are checked beside the candidate output.
      auto bytes = Read(route[a]->logical.device, stream);
      std::fill(bytes.begin(), bytes.end(), 0xa5);
      std::memcpy(bytes.data() + 64, logical.data(), logical.size() * 4);
      Upload(route[a]->logical.device, bytes, stream);
    }
    for (Device* p : {id_d.get(), count_d.get(), input.get(), wg.get(),
                      wu.get(), wd.get(), dt.get(), nt.get(), wt.get()})
      immutable.emplace_back(p, Hash(Read(*p, stream)));
  }

  void Routing(unsigned a, hipStream_t stream) {
    auto& r = *route[a];
    if (a)
      Require(q::RoutedCompactLogical(
                  static_cast<const int*>(id_d->data),
                  static_cast<const unsigned*>(count_d->data), r.P(r.padded),
                  r.P(r.logical), r.P(r.cursor), r.P(r.tokens), r.P(r.slots), n,
                  used, experts, stream),
              "Compact routing refused");
    else
      q::RoutedCompact(static_cast<const int*>(id_d->data),
                       static_cast<const unsigned*>(count_d->data),
                       r.P(r.padded), r.P(r.cursor), r.P(r.tokens),
                       r.P(r.slots), n, used, experts, stream);
    Hip(hipGetLastError());
  }
  void Gate(unsigned a, hipStream_t stream) {
    auto& r = *route[a];
    auto launch = [&](Device& tiles, unsigned count, unsigned width) {
      if (!count)
        return;
      bool ok;
      if (a)
        ok = q::RoutedGatedIQ2CompactGemm(
            wg->data, wu->data, static_cast<const __half*>(input->data),
            static_cast<const int*>(tiles.data), count, width, r.P(r.padded),
            r.P(r.tokens), r.P(r.slots), r.P(r.logical),
            static_cast<float*>(gate[a]->Data()), 640, inner, stream);
      else
        ok = q::RoutedGatedIQ2Gemm(
            wg->data, wu->data, static_cast<const __half*>(input->data),
            static_cast<const int*>(tiles.data), count, width, r.P(r.padded),
            r.P(r.tokens), r.P(r.slots), static_cast<float*>(gate[a]->Data()),
            640, inner, stream);
      Require(ok, "Gate dispatch refused");
    };
    launch(*wt, wide_tiles.size(), 128);
    launch(*nt, narrow_tiles.size(), gate_width ? gate_width : 64);
  }
  void PackDown(unsigned a, hipStream_t stream) {
    auto& r = *route[a];
    Require(q::PackQ2ScaledRows(static_cast<const float*>(gate[a]->Data()),
                                static_cast<__half*>(half[a]->Data()),
                                static_cast<float*>(inverse[a]->Data()),
                                n * used, 640, stream),
            "Packing refused");
    bool ok;
    if (a)
      ok = q::RoutedQ2CompactHalfGemm(
          wd->data, static_cast<const __half*>(half[a]->Data()),
          static_cast<const float*>(inverse[a]->Data()),
          static_cast<const int*>(dt->data), down_tiles.size(), 48,
          r.P(r.padded), r.P(r.slots), r.P(r.logical),
          static_cast<__half*>(down[a]->Data()), out_width, 640, stream);
    else
      ok = q::RoutedQ2ScaledHalfGemm(
          wd->data, static_cast<const __half*>(half[a]->Data()),
          static_cast<const float*>(inverse[a]->Data()),
          static_cast<const int*>(dt->data), down_tiles.size(), 48,
          r.P(r.padded), r.P(r.slots), static_cast<__half*>(down[a]->Data()),
          out_width, 640, stream);
    Require(ok, "Down dispatch refused");
  }
  void Run(unsigned a, hipStream_t stream) {
    Routing(a, stream);
    Gate(a, stream);
    PackDown(a, stream);
  }

  bool Check(const std::string& name, hipStream_t stream) {
    std::array<std::vector<std::uint8_t>, 2> gates, halves, scales, outputs;
    std::vector<unsigned> compact_to_slot(n * used);
    std::size_t half_errors[2]{}, scale_errors[2]{};
    for (unsigned a = 0; a < 2; ++a) {
      auto& r = *route[a];
      for (auto* p : {&r.padded, &r.cursor, &r.tokens, &r.slots, gate[a].get(),
                      half[a].get(), inverse[a].get(), down[a].get()})
        p->Poison(stream);
      if (a)
        r.logical.Poison(stream);
      Run(a, stream);
      std::vector<int> physical_slots, physical_tokens;
      for (auto [label, p] :
           std::initializer_list<std::pair<const char*, Output*>>{
               {"bounds", &r.padded},
               {"logical", &r.logical},
               {"cursor", &r.cursor},
               {"tokens", &r.tokens},
               {"slots", &r.slots}}) {
        auto raw = RawChecked(*p, stream);
        auto values = Integers(raw);
        Save(name + (a ? "-candidate-" : "-parent-") + label, raw);
        if (std::string(label) == "bounds")
          Require(values == pad, "Padded prefix mismatch");
        if (std::string(label) == "logical")
          Require(values == logical, "Logical prefix mismatch");
        if (std::string(label) == "cursor")
          Require(std::equal(values.begin(), values.end(), counts.begin()),
                  "Count mismatch");
        if (std::string(label) == "slots")
          physical_slots = values;
        if (std::string(label) == "tokens")
          physical_tokens = values;
      }
      std::vector<unsigned> seen(n * used);
      for (unsigned e = 0; e < experts; ++e) {
        for (unsigned j = 0; j < unsigned(pad[e + 1] - pad[e]); ++j) {
          const int slot = physical_slots[pad[e] + j],
                    tok = physical_tokens[pad[e] + j];
          if (j >= counts[e])
            Require(slot == -1 && tok == -1, "Routing padding is not empty");
          else {
            Require(slot >= 0 && unsigned(slot) < n * used &&
                        ids[slot] == int(e) && tok == slot / int(used),
                    "Routing identity mismatch");
            ++seen[slot];
            if (a)
              compact_to_slot[logical[e] + j] = slot;
          }
        }
      }
      for (unsigned j = pad.back(); j < cap; ++j)
        Require(physical_slots[j] == -1 && physical_tokens[j] == -1,
                "Map tail mutated");
      Require(
          std::all_of(seen.begin(), seen.end(), [](auto x) { return x == 1; }),
          "Routing is not a permutation");
      gates[a] = gate[a]->Checked(stream);
      halves[a] = half[a]->Checked(stream);
      scales[a] = inverse[a]->Checked(stream);
      outputs[a] = down[a]->Checked(stream);
      for (auto [label, raw] : std::initializer_list<
               std::pair<const char*, const std::vector<std::uint8_t>*>>{
               {"gate", &gates[a]},
               {"half", &halves[a]},
               {"scale", &scales[a]},
               {"down", &outputs[a]}})
        Save(name + (a ? "-candidate-" : "-parent-") + label, *raw);
      for (unsigned row = 0; row < n * used; ++row) {
        double peak = 0;
        for (unsigned c = 0; c < 640; ++c) {
          float x;
          std::memcpy(
              &x, gates[a].data() + 64 + (std::size_t(row) * 640 + c) * 4, 4);
          peak = std::max(peak, std::fabs(double(x)));
        }
        const int shift =
            peak == 0 ? 0 : std::clamp(13 - std::ilogb(peak), -120, 120);
        unsigned observed;
        std::memcpy(&observed, scales[a].data() + 64 + row * 4, 4);
        scale_errors[a] +=
            observed != std::bit_cast<unsigned>(float(std::ldexp(1.0, -shift)));
        for (unsigned c = 0; c < 640; ++c) {
          float x;
          std::uint16_t h;
          const auto i = std::size_t(row) * 640 + c;
          std::memcpy(&x, gates[a].data() + 64 + i * 4, 4);
          std::memcpy(&h, halves[a].data() + 64 + i * 2, 2);
          half_errors[a] += h != HalfBits(float(std::ldexp(double(x), shift)));
        }
      }
    }
    bool gate_exact = true, half_exact = true, scale_exact = true;
    for (unsigned r = 0; r < n * used; ++r) {
      const auto slot = compact_to_slot[r];
      gate_exact &=
          !std::memcmp(gates[1].data() + 64 + std::size_t(r) * 2560,
                       gates[0].data() + 64 + std::size_t(slot) * 2560, 2560);
      half_exact &=
          !std::memcmp(halves[1].data() + 64 + std::size_t(r) * 1280,
                       halves[0].data() + 64 + std::size_t(slot) * 1280, 1280);
      scale_exact &= !std::memcmp(scales[1].data() + 64 + r * 4,
                                  scales[0].data() + 64 + slot * 4, 4);
    }
    const bool down_exact = outputs[0] == outputs[1];
    for (auto [p, digest] : immutable)
      Require(Hash(Read(*p, stream)) == digest, "Input/weight/tile mutated");
    std::cout << "{\"event\":\"compact_chain_check\",\"case\":\"" << name
              << "\",\"tokens\":" << n << ",\"used\":" << used
              << ",\"experts\":" << experts << ",\"inner\":" << inner
              << ",\"out_width\":" << out_width
              << ",\"gate_width\":" << gate_width << ",\"capacity\":" << cap
              << ",\"skew\":" << skew << ",\"gate_exact\":" << gate_exact
              << ",\"half_exact\":" << half_exact
              << ",\"scale_exact\":" << scale_exact
              << ",\"down_exact\":" << down_exact
              << ",\"parent_half_oracle_errors\":" << half_errors[0]
              << ",\"candidate_half_oracle_errors\":" << half_errors[1]
              << ",\"parent_scale_oracle_errors\":" << scale_errors[0]
              << ",\"candidate_scale_oracle_errors\":" << scale_errors[1]
              << "}\n";
    return gate_exact && half_exact && scale_exact && down_exact &&
           !half_errors[0] && !half_errors[1] && !scale_errors[0] &&
           !scale_errors[1];
  }
};

static void Time(Chain& c, const std::string& name, hipStream_t stream) {
  std::size_t active = std::count_if(c.counts.begin(), c.counts.end(),
                                     [](auto n) { return n > 0; });
  const auto working_weights =
      active * (c.wg->bytes + c.wu->bytes + c.wd->bytes) / c.experts;
  Require(working_weights > 32u * 1024 * 1024,
          "Active weights do not exceed MALL");
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (unsigned scope = 0; scope < 2; ++scope)
    for (unsigned rep = 0; rep < 7; ++rep)
      for (unsigned order = 0; order < 2; ++order) {
        const unsigned arm = (rep + order) % 2, iterations = 3;
        Hip(hipEventRecord(begin, stream));
        for (unsigned i = 0; i < iterations; ++i) {
          if (scope)
            c.Run(arm, stream);
          else
            c.Gate(arm, stream);
        }
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms;
        Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << "{\"event\":\"compact_chain_timing\",\"case\":\"" << name
                  << "\",\"scope\":\"" << (scope ? "expert_chain" : "gate_up")
                  << "\",\"rep\":" << rep << ",\"order\":" << order
                  << ",\"candidate\":" << bool(arm)
                  << ",\"warmup\":" << (rep < 2)
                  << ",\"iterations\":" << iterations
                  << ",\"active_experts\":" << active
                  << ",\"active_weight_bytes\":" << working_weights
                  << ",\"us_per_iteration\":" << double(ms) * 1000 / iterations
                  << "}\n";
      }
  Hip(hipEventDestroy(end));
  Hip(hipEventDestroy(begin));
}

int main() {
  try {
    std::cout << std::boolalpha << std::setprecision(12);
    hipStream_t stream{};
    Hip(hipStreamCreateWithFlags(&stream, hipStreamNonBlocking));
    bool pass = true;
    for (unsigned n : {1u, 9u, 17u, 33u, 97u})
      for (unsigned width : {16u, 48u, 64u, 128u}) {
        Chain c(n, 3, 7, 256, 129, width, false, stream);
        pass = c.Check("tokens-" + std::to_string(n) + "-tile-" +
                           std::to_string(width),
                       stream) &&
               pass;
      }
    for (bool skew : {false, true}) {
      Chain c(2048, 10, 512, 2560, 2560, 0, skew, stream);
      const std::string name = skew ? "skew" : "balanced";
      pass = c.Check(name + "-before", stream) && pass;
      Time(c, name, stream);
      pass = c.Check(name + "-after", stream) && pass;
    }
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"complete\",\"pass\":" << pass << "}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << "Unsafe chain fixture failure: " << e.what() << '\n';
    return 2;
  }
}
