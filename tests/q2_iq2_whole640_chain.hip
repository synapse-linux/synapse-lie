// SPDX-License-Identifier: MIT
// Complete mixed IQ2 producer -> dyadic packing -> unchanged Q2 down chain.
// Synthetic routed rows qualify buffer ownership, not model throughput.
#include <chrono>
#include <filesystem>
#include <numeric>

#include "experiments/iq2_mixed_tiles.h"
#include "experiments/q2_iq2_whole640_tiles.h"
#include "q2_expert_order_support.hpp"

static std::vector<std::uint8_t> Payload(Output& output, bool finite) {
  auto raw = Read(output.device, nullptr);
  const auto end = output.offset + output.count * (output.half ? 2 : 4);
  for (std::size_t i = 0; i < raw.size(); ++i)
    if (i < output.offset || i >= end)
      Require(raw[i] == 0xa5, "Output guard changed; stop device work");
  std::vector<std::uint8_t> values(raw.begin() + output.offset,
                                   raw.begin() + end);
  if (finite)
    for (std::size_t i = 0; i < output.count; ++i) {
      float value;
      if (output.half) {
        std::uint16_t bits;
        std::memcpy(&bits, values.data() + i * 2, 2);
        value = FromHalf(bits);
      } else {
        std::memcpy(&value, values.data() + i * 4, 4);
      }
      Require(std::isfinite(value),
              "Nonfinite or unwritten output; stop device work");
    }
  return values;
}

struct Chain {
  unsigned n, experts;
  bool half_down;
  std::vector<unsigned> counts;
  std::vector<int> bounds, tokens, slots, parent_map, candidate_map, down_map;
  std::vector<bool> fused;
  lie_iq2_tile_spans parent{};
  lie_iq2_tail16_spans candidate{};
  std::unique_ptr<Device> bd, td, sd, pm, cm, dm, input;
  std::array<std::unique_ptr<Device>, 3> gate_weights, up_weights, down_weights;
  std::array<std::unique_ptr<Output>, 2> gate, packed, inverse, down;
  std::vector<std::pair<Device*, std::string>> immutable;

  Chain(std::vector<unsigned> rows, bool h, unsigned misalign = 0)
      : n(std::accumulate(rows.begin(), rows.end(), 0U)),
        experts(rows.size()),
        half_down(h),
        counts(std::move(rows)),
        bounds(experts + 1),
        fused(n) {
    Require(n && n <= 4096 && experts <= 512, "Invalid chain geometry");
    std::size_t capacity = 0;
    for (unsigned e = 0; e < experts; ++e) {
      bounds[e + 1] = bounds[e] + ((counts[e] + 15) / 16) * 16;
      capacity += (counts[e] + 127) / 128;
      for (unsigned j = 0; j < unsigned(bounds[e + 1] - bounds[e]); j += 48)
        down_map.push_back(int(e | ((j / 48) << 16)));
    }
    parent_map.resize(capacity);
    candidate_map.resize(capacity);
    Require(lie_iq2_mixed_tiles(counts.data(), experts, n, 1, parent_map.data(),
                                capacity, &parent),
            "Parent partition refused");
    Require(lie_iq2_whole640_tiles(counts.data(), experts, n, 1,
                                   candidate_map.data(), capacity, &candidate),
            "Candidate partition refused");
    Require(parent.wide == candidate.wide128 &&
                parent.tail == candidate.tail64 + candidate.tail16,
            "Descriptor capacity changed");
    tokens.assign(bounds.back(), -1);
    slots.assign(bounds.back(), -1);
    unsigned logical = 0;
    for (unsigned e = 0; e < experts; ++e)
      for (unsigned row = 0; row < counts[e]; ++row) {
        const unsigned slot = n - 1 - logical++;
        // A permutation avoids an accidental compact-row/slot equivalence.
        tokens[bounds[e] + row] = int(slot);
        slots[bounds[e] + row] = int(slot);
        const unsigned tail = counts[e] % 128;
        fused[slot] = tail && tail <= 16 && row >= counts[e] - tail;
      }
    const auto ints = [&](const auto& values) {
      auto result = std::make_unique<Device>(values.size() * 4);
      Upload(*result, values, nullptr);
      return result;
    };
    bd = ints(bounds);
    td = ints(tokens);
    sd = ints(slots);
    pm = ints(parent_map);
    cm = ints(candidate_map);
    dm = ints(down_map);
    Random rng;
    std::vector<std::uint16_t> activation(std::size_t(n) * 2560);
    for (std::size_t i = 0; i < activation.size(); ++i) {
      const unsigned row = i / 2560;
      const float value = row % 17 == 0 ? -0.F
                          : row % 19 == 0
                              ? 1e-7F
                              : float(int(rng.Next() >> 16) - 32768) / 262144.F;
      activation[i] = HalfBits(value);
    }
    input = std::make_unique<Device>(activation.size() * 2);
    Upload(*input, activation, nullptr);
    for (unsigned r = 0; r < 3; ++r) {
      gate_weights[r] =
          std::make_unique<Device>(std::size_t(experts) * 640 * 10 * 66);
      up_weights[r] = std::make_unique<Device>(gate_weights[r]->bytes);
      down_weights[r] =
          std::make_unique<Device>(std::size_t(experts) * 2560 * 3 * 84);
      for (auto* weight : {gate_weights[r].get(), up_weights[r].get(),
                           down_weights[r].get()}) {
        const bool q2 = weight == down_weights[r].get();
        const unsigned block = q2 ? 84 : 66;
        std::vector<std::uint8_t> bytes(weight->bytes);
        for (std::size_t off = 0; off < bytes.size(); off += block) {
          for (unsigned j = 0; j < block; ++j)
            bytes[off + j] = rng.Next() >> 24;
          const auto scale = HalfBits((off / block) % 29 == 0 ? 0.F : .00125F);
          std::memcpy(bytes.data() + off + (q2 ? 80 : 0), &scale, 2);
          if (q2) {
            const auto minimum = HalfBits(.00075F);
            std::memcpy(bytes.data() + off + 82, &minimum, 2);
          }
        }
        Upload(*weight, bytes, nullptr);
        immutable.emplace_back(weight, Hash(bytes));
      }
    }
    for (auto* device : {bd.get(), td.get(), sd.get(), pm.get(), cm.get(),
                         dm.get(), input.get()})
      immutable.emplace_back(device, Hash(Read(*device, nullptr)));
    for (unsigned a = 0; a < 2; ++a) {
      gate[a] = std::make_unique<Output>(std::size_t(n) * 640, false);
      packed[a] =
          std::make_unique<Output>(std::size_t(n) * 640, true, 64 + misalign);
      inverse[a] = std::make_unique<Output>(n, false);
      down[a] = std::make_unique<Output>(std::size_t(n) * 2560, half_down);
    }
  }
  void Reset(unsigned a) {
    for (auto* p :
         {gate[a].get(), packed[a].get(), inverse[a].get(), down[a].get()})
      p->Poison(nullptr);
  }
  void Run(unsigned a, unsigned rotation) {
    const auto* map = static_cast<const int*>((a ? cm : pm)->data);
    const auto* bound = static_cast<const int*>(bd->data);
    const auto* token = static_cast<const int*>(td->data);
    const auto* slot = static_cast<const int*>(sd->data);
    auto* half = static_cast<__half*>(packed[a]->Data());
    auto* scale = static_cast<float*>(inverse[a]->Data());
    const unsigned wide = a ? candidate.wide128 : parent.wide;
    const unsigned tail = a ? candidate.tail64 : parent.tail;
    const auto ordinary = [&](unsigned offset, unsigned count, unsigned width) {
      if (count)
        Require(q::RoutedGatedIQ2Gemm(
                    gate_weights[rotation]->data, up_weights[rotation]->data,
                    static_cast<const __half*>(input->data), map + offset,
                    count, width, bound, token, slot,
                    static_cast<float*>(gate[a]->Data()), 640, 2560, nullptr),
                "Ordinary producer refused");
    };
    ordinary(0, wide, 128);
    ordinary(wide, tail, 64);
    if (a && candidate.tail16) {
      Require(q::RoutedGatedIQ2Whole640(
                  gate_weights[rotation]->data, up_weights[rotation]->data,
                  static_cast<const __half*>(input->data), map + wide + tail,
                  candidate.tail16, bound, token, slot, half, scale, nullptr),
              "Fused producer refused");
      Require(q::PackQ2ScaledOrdinaryRows(
                  static_cast<const float*>(gate[a]->Data()), half, scale, map,
                  wide, tail, bound, slot, nullptr),
              "Selective packing refused");
    } else {
      Require(q::PackQ2ScaledRows(static_cast<const float*>(gate[a]->Data()),
                                  half, scale, n, 640, nullptr),
              "Original packing refused");
    }
    const auto* tiles = static_cast<const int*>(dm->data);
    Require(half_down
                ? q::RoutedQ2ScaledHalfGemm(
                      down_weights[rotation]->data, half, scale, tiles,
                      down_map.size(), 48, bound, slot,
                      static_cast<__half*>(down[a]->Data()), 2560, 640, nullptr)
                : q::RoutedQ2ScaledGemm(
                      down_weights[rotation]->data, half, scale, tiles,
                      down_map.size(), 48, bound, slot,
                      static_cast<float*>(down[a]->Data()), 2560, 640, nullptr),
            "Unchanged down consumer refused");
    Hip(hipGetLastError());
  }
  std::vector<std::uint8_t> ReadGate(unsigned a) {
    auto bytes = Payload(*gate[a], false);
    for (unsigned row = 0; row < n; ++row)
      for (unsigned column = 0; column < 640; ++column) {
        std::uint32_t bits;
        std::memcpy(&bits, bytes.data() + (std::size_t(row) * 640 + column) * 4,
                    4);
        if (a && fused[row])
          Require(bits == 0x7fc0beefu,
                  "Fused slot wrote its obsolete F32 intermediate");
        else
          Require(std::isfinite(std::bit_cast<float>(bits)),
                  "Ordinary F32 output nonfinite/unwritten; stop device work");
      }
    return bytes;
  }
  void Safe(unsigned a) {
    (void)ReadGate(a);
    for (auto* output : {packed[a].get(), inverse[a].get(), down[a].get()})
      (void)Payload(*output, true);
  }
  void Unchanged() {
    for (const auto& [device, expected] : immutable)
      Require(Hash(Read(*device, nullptr)) == expected,
              "Immutable chain input changed");
  }
  std::size_t Validate(const std::string& label, bool timed) {
    std::array<std::vector<std::uint8_t>, 2> gates, halves, scales, outputs;
    std::size_t changed = 0, pack_errors = 0;
    for (unsigned a = 0; a < 2; ++a) {
      gates[a] = ReadGate(a);
      halves[a] = Payload(*packed[a], true);
      scales[a] = Payload(*inverse[a], true);
      outputs[a] = Payload(*down[a], true);
      const auto prefix = label + "-arm" + std::to_string(a);
      Save(prefix + "-gate.f32", gates[a]);
      Save(prefix + "-packed.f16", halves[a]);
      Save(prefix + "-inverse.f32", scales[a]);
      Save(prefix + (half_down ? "-down.f16" : "-down.f32"), outputs[a]);
    }
    for (const auto* values : {&halves, &scales, &outputs})
      changed += (*values)[0] != (*values)[1];
    for (unsigned row = 0; row < n; ++row) {
      std::array<float, 640> values;
      std::memcpy(values.data(), gates[0].data() + std::size_t(row) * 640 * 4,
                  640 * 4);
      if (!fused[row])
        changed += std::memcmp(values.data(),
                               gates[1].data() + std::size_t(row) * 640 * 4,
                               640 * 4) != 0;
      float maxabs = 0.F;
      for (float value : values)
        maxabs = std::max(maxabs, std::fabs(value));
      int exponent = 0;
      (void)std::frexp(maxabs, &exponent);
      const int shift =
          maxabs == 0.F ? 0 : std::clamp(14 - exponent, -120, 120);
      const float expected_inverse = std::ldexp(1.F, -shift);
      for (unsigned a = 0; a < 2; ++a) {
        pack_errors +=
            std::memcmp(&expected_inverse, scales[a].data() + row * 4, 4) != 0;
        for (unsigned column = 0; column < 640; ++column) {
          const auto expected = HalfBits(std::ldexp(values[column], shift));
          pack_errors += std::memcmp(&expected,
                                     halves[a].data() +
                                         (std::size_t(row) * 640 + column) * 2,
                                     2) != 0;
        }
      }
    }
    std::cout
        << "{\"event\":\"whole640_chain_replay\",\"label\":\"" << label
        << "\",\"rows\":" << n << ",\"wide\":" << candidate.wide128
        << ",\"ordinary\":" << candidate.tail64
        << ",\"fused\":" << candidate.tail16
        << ",\"changed_buffers_or_rows\":" << changed
        << ",\"scalar_pack_mismatches\":" << pack_errors
        << ",\"guards_finite_written_ownership\":true,\"actual_timed_outputs\":"
        << (timed ? "true" : "false") << "}\n";
    return changed + pack_errors;
  }
};

int main() {
  try {
    std::filesystem::create_directories("results");
    std::cout << std::setprecision(12);
    std::size_t changed = 0;
    const std::vector<std::vector<unsigned>> edges = {
        {1, 2, 7, 8, 15, 16, 0},
        {17, 33, 48, 49, 63, 64},
        {65, 80, 127, 128},
        {129, 145, 193, 257, 0, 16}};
    for (unsigned edge = 0; edge < edges.size(); ++edge)
      for (bool half : {false, true}) {
        Chain chain(edges[edge], half);
        for (unsigned arm = 0; arm < 2; ++arm) {
          chain.Reset(arm);
          chain.Run(arm, 0);
          Hip(hipDeviceSynchronize());
          chain.Safe(arm);
        }
        changed += chain.Validate(
            "edge-" + std::to_string(edge) + (half ? "-half" : "-float"),
            false);
        chain.Unchanged();
      }
    for (bool half : {false, true}) {
      Chain chain(edges.back(), half, 2);
      for (unsigned arm = 0; arm < 2; ++arm) {
        chain.Reset(arm);
        chain.Run(arm, 0);
        Hip(hipDeviceSynchronize());
        chain.Safe(arm);
      }
      changed +=
          chain.Validate(half ? "unaligned-half" : "unaligned-float", false);
      chain.Unchanged();
    }
    std::vector<unsigned> rows(64, 5);
    std::fill(rows.begin(), rows.begin() + 8, 129);
    std::fill(rows.begin() + 8, rows.begin() + 24, 49);
    std::fill(rows.begin() + 24, rows.begin() + 56, 6);
    Chain chain(rows, false);
    Require(chain.n == 2048, "Fixed chain diagnostic row count differs");
    for (unsigned sample = 0; sample < 7; ++sample) {
      for (unsigned order = 0; order < 2; ++order) {
        const unsigned arm = sample % 2 ? 1 - order : order;
        chain.Reset(arm);
        Hip(hipDeviceSynchronize());
        const auto begin = std::chrono::steady_clock::now();
        for (unsigned rotation = 0; rotation < 3; ++rotation)
          chain.Run(arm, rotation);
        Hip(hipDeviceSynchronize());
        const double us = std::chrono::duration<double, std::micro>(
                              std::chrono::steady_clock::now() - begin)
                              .count() /
                          3;
        std::cout << "{\"event\":\"whole640_chain_timing\",\"arm\":" << arm
                  << ",\"sample\":" << sample
                  << ",\"warmup\":" << (sample < 2 ? "true" : "false")
                  << ",\"rotations\":3,\"gate_pack_down_wall_us\":" << us
                  << "}\n";
        chain.Safe(arm);
      }
      // Inspect the actual final timed rotation before any reset or replay.
      changed += chain.Validate("timed-" + std::to_string(sample), true);
    }
    chain.Unchanged();
    std::cout
        << "{\"event\":\"whole640_chain_complete\",\"numeric_mismatches\":"
        << changed
        << ",\"safe_device_work\":true,\"immutable_inputs\":true,\"model_"
           "inference\":false}\n";
    return changed ? 1 : 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 2;
  }
}
