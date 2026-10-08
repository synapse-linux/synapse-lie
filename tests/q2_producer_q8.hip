// SPDX-License-Identifier: MIT
// Complete old F16/new producer-Q8 expert chains; format and MMQ references.
#include "q2_expert_order_support.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/mmq/qfn_mmq.h"
extern "C" void q2_fixture_quantize_d2s6(const float *, void *, unsigned,
                                         hipStream_t);

static std::vector<std::uint8_t> RawChecked(Output &output,
                                            hipStream_t stream) {
  auto bytes = Read(output.device, stream);
  for (unsigned i = 0; i < 64; ++i)
    Require(bytes[i] == 0xa5 && bytes[bytes.size() - 1 - i] == 0xa5,
            "Map guard changed; refusing further device work");
  return bytes;
}
static std::vector<int> Integers(const std::vector<std::uint8_t> &raw) {
  std::vector<int> values((raw.size() - 128) / 4);
  std::memcpy(values.data(), raw.data() + 64, values.size() * 4);
  return values;
}

struct Route {
  Output padded, logical, cursor, tokens, slots;
  Route(unsigned ne, unsigned cap)
      : padded(ne + 1, false), logical(ne + 1, false), cursor(ne, false),
        tokens(cap, false), slots(cap, false) {}
  std::int32_t *P(Output &o) { return static_cast<std::int32_t *>(o.Data()); }
};

struct Chain {
  unsigned n, used, experts, inner, out_width, gate_width, down_width, cap;
  bool skew;
  std::vector<int> ids, pad, logical, down_tiles, narrow_tiles, wide_tiles;
  std::vector<unsigned> counts;
  std::unique_ptr<Device> id_d, count_d, input, wg, wu, wd, dt, nt, wt;
  std::array<std::unique_ptr<Route>, 2> route;
  std::array<std::unique_ptr<Output>, 2> gate, half, inverse, down;
  std::vector<std::pair<Device *, std::string>> immutable;

  Chain(unsigned tokens, unsigned top, unsigned ne, unsigned k, unsigned m,
        unsigned bn, unsigned dbn, bool nonuniform, hipStream_t stream)
      : n(tokens), used(top), experts(ne), inner(k), out_width(m),
        gate_width(bn), down_width(dbn),
        cap(q::RoutedCompactRows(n * used, ne)), skew(nonuniform),
        ids(n * used), pad(ne + 1), logical(ne + 1), counts(ne) {
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
      for (unsigned j = 0; j < unsigned(pad[e + 1] - pad[e]); j += down_width)
        down_tiles.push_back(e | ((j / down_width) << 16));
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
    auto ints = [&](const auto &values) {
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
    for (auto &x : activation)
      x = n == 1 ? 0
                 : HalfBits(float(int(rng.Next() >> 16) - 32768) / 262144.0f);
    input = std::make_unique<Device>(activation.size() * 2);
    Upload(*input, activation, stream);
    wg = std::make_unique<Device>(std::size_t(ne) * 640 * (inner / 256) * 66);
    wu = std::make_unique<Device>(wg->bytes);
    wd = std::make_unique<Device>(std::size_t(ne) * m * 3 * 84);
    for (Device *weight : {wg.get(), wu.get(), wd.get()}) {
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
      gate[a] = std::make_unique<Output>(
          a ? std::size_t(cap) * 6 * 36 : std::size_t(n) * used * 640, false);
      if (!a)
        half[a] = std::make_unique<Output>(std::size_t(n) * used * 640, true);
      if (!a)
        inverse[a] = std::make_unique<Output>(n * used, false);
      down[a] = std::make_unique<Output>(std::size_t(n) * used * m, true);
      // The control never reads/writes logical bounds. Seed the CPU expectation
      // there so its untouched bytes are checked beside the candidate output.
      auto bytes = Read(route[a]->logical.device, stream);
      std::fill(bytes.begin(), bytes.end(), 0xa5);
      std::memcpy(bytes.data() + 64, logical.data(), logical.size() * 4);
      Upload(route[a]->logical.device, bytes, stream);
    }
    for (Device *p : {id_d.get(), count_d.get(), input.get(), wg.get(),
                      wu.get(), wd.get(), dt.get(), nt.get(), wt.get()})
      immutable.emplace_back(p, Hash(Read(*p, stream)));
  }

  void Routing(unsigned a, hipStream_t stream) {
    auto &r = *route[a];
    q::RoutedCompact(static_cast<const int *>(id_d->data),
                     static_cast<const unsigned *>(count_d->data),
                     r.P(r.padded), r.P(r.cursor), r.P(r.tokens), r.P(r.slots),
                     n, used, experts, stream);
    Hip(hipGetLastError());
  }
  void Gate(unsigned a, hipStream_t stream) {
    auto &r = *route[a];
    auto launch = [&](Device &tiles, unsigned count, unsigned width) {
      if (!count)
        return;
      bool ok;
      if (a)
        ok = q::RoutedGatedIQ2ProducerQ8Gemm(
            wg->data, wu->data, static_cast<const __half *>(input->data),
            static_cast<const int *>(tiles.data), count, width, r.P(r.padded),
            r.P(r.tokens), r.P(r.slots), static_cast<float *>(gate[a]->Data()),
            640, inner, cap, stream);
      else
        ok = q::RoutedGatedIQ2Gemm(
            wg->data, wu->data, static_cast<const __half *>(input->data),
            static_cast<const int *>(tiles.data), count, width, r.P(r.padded),
            r.P(r.tokens), r.P(r.slots), static_cast<float *>(gate[a]->Data()),
            640, inner, stream);
      Require(ok, "Gate dispatch refused");
    };
    launch(*wt, wide_tiles.size(), 128);
    launch(*nt, narrow_tiles.size(), gate_width ? gate_width : 64);
  }
  void PackDown(unsigned a, hipStream_t stream) {
    auto &r = *route[a];
    if (a) {
      Require(qfn_q2_producer_q8_down(
                  wd->data, gate[a]->Data(), static_cast<const int *>(dt->data),
                  down_tiles.size(), down_width,
                  static_cast<const unsigned *>(count_d->data), r.P(r.padded),
                  r.P(r.slots), down[a]->Data(), out_width, cap, stream) == 0,
              "Producer-Q8 down refused");
    } else {
      Require(q::PackQ2ScaledRows(static_cast<const float *>(gate[a]->Data()),
                                  static_cast<__half *>(half[a]->Data()),
                                  static_cast<float *>(inverse[a]->Data()),
                                  n * used, 640, stream),
              "Parent packing refused");
      Require(q::RoutedQ2ScaledHalfGemm(
                  wd->data, static_cast<const __half *>(half[a]->Data()),
                  static_cast<const float *>(inverse[a]->Data()),
                  static_cast<const int *>(dt->data), down_tiles.size(),
                  down_width, r.P(r.padded), r.P(r.slots),
                  static_cast<__half *>(down[a]->Data()), out_width, 640,
                  stream),
              "Parent down refused");
    }
  }
  void Run(unsigned a, hipStream_t stream) {
    Routing(a, stream);
    Gate(a, stream);
    PackDown(a, stream);
  }

  bool Check(const std::string &name, hipStream_t stream) {
    std::array<std::vector<std::uint8_t>, 2> gates, outputs;
    std::vector<unsigned> physical(n * used);
    auto finite = [](const auto &raw, bool half) {
      const unsigned step = half ? 2 : 4;
      for (std::size_t i = 64; i < raw.size() - 64; i += step) {
        unsigned bits = 0;
        std::memcpy(&bits, raw.data() + i, step);
        Require(half ? (bits & 0x7c00) != 0x7c00
                     : (bits & 0x7f800000) != 0x7f800000,
                "Nonfinite output; refusing further device work");
      }
    };
    for (unsigned a = 0; a < 2; ++a) {
      auto &r = *route[a];
      for (auto *p : {&r.padded, &r.cursor, &r.tokens, &r.slots, gate[a].get(),
                      down[a].get()})
        p->Poison(stream);
      if (!a) {
        half[a]->Poison(stream);
        inverse[a]->Poison(stream);
      }
      Run(a, stream);
      std::vector<int> slots, tokens;
      for (auto [label, p] :
           std::initializer_list<std::pair<const char *, Output *>>{
               {"bounds", &r.padded},
               {"cursor", &r.cursor},
               {"tokens", &r.tokens},
               {"slots", &r.slots}}) {
        auto raw = RawChecked(*p, stream);
        auto values = Integers(raw);
        Save(name + (a ? "-candidate-" : "-parent-") + label, raw);
        if (std::string(label) == "bounds")
          Require(values == pad, "Padded prefix mismatch");
        if (std::string(label) == "cursor")
          Require(std::equal(values.begin(), values.end(), counts.begin()),
                  "Count mismatch");
        if (std::string(label) == "slots")
          slots = values;
        if (std::string(label) == "tokens")
          tokens = values;
      }
      std::vector<unsigned> seen(n * used);
      for (unsigned e = 0; e < experts; ++e)
        for (unsigned j = 0; j < unsigned(pad[e + 1] - pad[e]); ++j) {
          const unsigned row = pad[e] + j;
          const int slot = slots[row], tok = tokens[row];
          if (j >= counts[e])
            Require(slot == -1 && tok == -1, "Routing padding is not empty");
          else {
            Require(slot >= 0 && unsigned(slot) < n * used &&
                        ids[slot] == int(e) && tok == slot / int(used),
                    "Routing identity mismatch");
            ++seen[slot];
            if (a)
              physical[slot] = row;
          }
        }
      for (unsigned j = pad.back(); j < cap; ++j)
        Require(slots[j] == -1 && tokens[j] == -1, "Map tail mutated");
      Require(
          std::all_of(seen.begin(), seen.end(), [](auto x) { return x == 1; }),
          "Routing is not a permutation");
      gates[a] = a ? RawChecked(*gate[a], stream) : gate[a]->Checked(stream);
      outputs[a] = down[a]->Checked(stream);
      finite(outputs[a], true);
      if (!a)
        finite(gates[a], false);
      Save(name + (a ? "-candidate-q8" : "-parent-gate"), gates[a]);
      Save(name + (a ? "-candidate-down" : "-parent-down"), outputs[a]);
      if (!a) {
        Save(name + "-parent-half", half[0]->Checked(stream));
        Save(name + "-parent-inverse", inverse[0]->Checked(stream));
      } else {
        // All invalid/padded rows remain poisoned. The consumer must mask
        // them before any read; allocation guards check all stores.
        for (unsigned row = 0; row < cap; ++row)
          if (slots[row] < 0)
            for (unsigned b = 0; b < 6; ++b)
              for (unsigned j = 0; j < 144; j += 4) {
                unsigned bits;
                std::memcpy(&bits,
                            gates[a].data() + 64 +
                                (std::size_t(b) * cap + row) * 144 + j,
                            4);
                Require(bits == 0x7fc0beefu, "Inactive Q8 row mutated");
              }
      }
    }
    Output reference_q8(std::size_t(n) * used * 6 * 36, false);
    Output reference_down(std::size_t(n) * used * out_width, false);
    reference_q8.Poison(stream);
    reference_down.Poison(stream);
    q2_fixture_quantize_d2s6(static_cast<const float *>(gate[0]->Data()),
                             reference_q8.Data(), n * used, stream);
    Hip(hipGetLastError());
    qfn_mmq_set_routed_max_expert_rows(
        *std::max_element(counts.begin(), counts.end()));
    qfn_mmq_set_routed_tile_cols(down_width);
    Require(qfn_mmq_q2_K_moe_raw(
                wd->data, static_cast<const float *>(gate[0]->Data()),
                static_cast<const int *>(id_d->data),
                static_cast<float *>(reference_down.Data()), out_width, 768,
                n * used, experts, 1, stream, 640) == 0,
            "MMQ reference refused");
    auto rq = RawChecked(reference_q8, stream);
    auto rd = reference_down.Checked(stream);
    finite(rd, false);
    Save(name + "-reference-q8", rq);
    Save(name + "-reference-down", rd);
    std::size_t format_errors = 0, reference_half_errors = 0,
                parent_half_changes = 0;
    for (unsigned slot = 0; slot < n * used; ++slot)
      for (unsigned b = 0; b < 6; ++b) {
        const auto *actual = gates[1].data() + 64 +
                             (std::size_t(b) * cap + physical[slot]) * 144;
        const auto *expected =
            rq.data() + 64 + (std::size_t(b) * n * used + slot) * 144;
        for (unsigned byte = 0; byte < 144; ++byte) {
          format_errors += actual[byte] != expected[byte];
          if (b == 5)
            Require(actual[byte] == 0, "Stored K tail is not zero");
        }
      }
    for (std::size_t i = 0; i < std::size_t(n) * used * out_width; ++i) {
      float x;
      std::uint16_t actual, parent;
      std::memcpy(&x, rd.data() + 64 + i * 4, 4);
      std::memcpy(&actual, outputs[1].data() + 64 + i * 2, 2);
      std::memcpy(&parent, outputs[0].data() + 64 + i * 2, 2);
      reference_half_errors += actual != HalfBits(x);
      parent_half_changes += actual != parent;
    }
    // Independent FP64 operator on actual packed activation bytes and original
    // affine Q2 blocks. D2S6 preserves six unquantized sums per128 values;
    // the final two sums are reconstructed from quantized codes by MMQ.
    const auto weights = Read(*wd, stream);
    const unsigned samples = 96;
    double squared_error = 0, squared_reference = 0, max_error = 0,
           max_reference = 0;
    std::vector<double> oracle;
    for (unsigned sample = 0; sample < samples; ++sample) {
      const std::size_t index =
          sample * (std::size_t(n) * used * out_width - 1) / (samples - 1);
      const unsigned slot = index / out_width, row = index % out_width;
      double result = 0;
      for (unsigned b = 0; b < 5; ++b) {
        const auto *activation = gates[1].data() + 64 +
                                 (std::size_t(b) * cap + physical[slot]) * 144;
        const auto *weight =
            weights.data() +
            ((std::size_t(ids[slot]) * out_width + row) * 3 + b / 2) * 84;
        auto h = [](const std::uint8_t *p) {
          std::uint16_t bits;
          std::memcpy(&bits, p, 2);
          return FromHalf(bits);
        };
        for (unsigned group = 0; group < 8; ++group) {
          const unsigned g = (b % 2) * 8 + group;
          const double d =
              FromHalf(HalfBits(h(weight + 80) * (weight[g] & 15)));
          const double minimum =
              FromHalf(HalfBits(h(weight + 82) * (weight[g] >> 4)));
          const double scale = h(activation + (group / 4) * 2);
          int dot = 0, sum = 0;
          for (unsigned j = 0; j < 16; ++j) {
            const unsigned k = (b % 2) * 128 + group * 16 + j;
            const int w = (weight[16 + (k / 128) * 32 + k % 32] >>
                           (2 * ((k % 128) / 32))) &
                          3;
            const int a =
                static_cast<std::int8_t>(activation[16 + group * 16 + j]);
            dot += w * a;
            sum += a;
          }
          const double corrected_sum =
              group < 6 ? h(activation + (2 + group) * 2) : scale * sum;
          result += d * scale * dot - minimum * corrected_sum;
        }
      }
      std::uint16_t bits;
      std::memcpy(&bits, outputs[1].data() + 64 + index * 2, 2);
      const double observed = FromHalf(bits),
                   error = std::abs(result - observed);
      squared_error += error * error;
      squared_reference += result * result;
      max_error = std::max(max_error, error);
      max_reference = std::max(max_reference, std::abs(result));
      oracle.insert(oracle.end(), {double(index), result, observed});
    }
    std::vector<std::uint8_t> oracle_bytes(oracle.size() * sizeof(double));
    std::memcpy(oracle_bytes.data(), oracle.data(), oracle_bytes.size());
    Save(name + "-fp64-oracle", oracle_bytes);
    const double relative_rms =
        std::sqrt(squared_error / std::max(squared_reference, 1e-30));
    const double scaled_error = max_error / std::max(max_reference, 1e-15);
    const bool oracle_pass = relative_rms <= 0.002 && scaled_error <= 0.002;
    for (auto [p, digest] : immutable)
      Require(Hash(Read(*p, stream)) == digest, "Input/weight/tile mutated");
    std::cout << "{\"event\":\"producer_q8_check\",\"case\":\"" << name
              << "\",\"tokens\":" << n << ",\"used\":" << used
              << ",\"experts\":" << experts << ",\"inner\":" << inner
              << ",\"out_width\":" << out_width
              << ",\"gate_width\":" << gate_width
              << ",\"down_width\":" << down_width << ",\"capacity\":" << cap
              << ",\"skew\":" << skew
              << ",\"format_byte_errors\":" << format_errors
              << ",\"reference_half_errors\":" << reference_half_errors
              << ",\"parent_half_changes\":" << parent_half_changes
              << ",\"oracle_samples\":" << samples
              << ",\"relative_rms\":" << relative_rms
              << ",\"scaled_error\":" << scaled_error
              << ",\"oracle_pass\":" << oracle_pass
              << ",\"safety_pass\":true}\n";
    return !format_errors && !reference_half_errors && oracle_pass;
  }
};
static void Time(Chain &c, const std::string &name, hipStream_t stream) {
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
        std::cout << "{\"event\":\"producer_q8_timing\",\"case\":\"" << name
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
    Require(qfn_mmq_init(0) == 0, "MMQ initialization failed");
    bool pass = true;
    for (unsigned n : {1u, 9u, 17u, 33u, 97u})
      for (unsigned width : {16u, 48u, 64u, 128u})
        for (unsigned down_width : {16u, 48u, 64u}) {
          Chain c(n, 3, 7, 256, 129, width, down_width, false, stream);
          pass = c.Check("tokens-" + std::to_string(n) + "-gate-" +
                             std::to_string(width) + "-down-" +
                             std::to_string(down_width),
                         stream) &&
                 pass;
        }
    for (bool skew : {false, true}) {
      Chain c(2048, 10, 512, 2560, 2560, 0, 48, skew, stream);
      const std::string name = skew ? "skew" : "balanced";
      pass = c.Check(name + "-before", stream) && pass;
      Time(c, name, stream);
      pass = c.Check(name + "-after", stream) && pass;
    }
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"complete\",\"pass\":" << pass << "}\n";
    return pass ? 0 : 1;
  } catch (const std::exception &e) {
    std::cerr << "Unsafe producer-Q8 fixture failure: " << e.what() << '\n';
    return 2;
  }
}
