// SPDX-License-Identifier: MIT
// Complete guarded packing/down comparisons; original model timing is separate.
#include "q2_expert_order_support.hpp"

struct OrderedCase {
  unsigned rows, experts, width, tile_rows, capacity;
  std::vector<std::int32_t> bounds, slots, tiles;
  std::vector<float> values;
  std::unique_ptr<Device> input, bd, sd, td, weights;
  std::array<std::unique_ptr<Output>, 2> packed, scales, down;
  std::array<std::string, 5> immutable;
  bool extreme;

  OrderedCase(unsigned n, unsigned ne, unsigned m, unsigned bn, bool special,
              hipStream_t stream)
      : rows(n),
        experts(ne),
        width(m),
        tile_rows(bn),
        capacity(unsigned(q::RoutedCompactRows(n, ne))),
        bounds(ne + 1),
        slots(capacity, -1),
        values(std::size_t(n) * 640),
        extreme(special) {
    Random rng;
    std::vector<std::vector<int>> buckets(ne);
    for (unsigned s = 0; s < n; ++s)
      buckets[(s * 73u + 3u) % ne].push_back(s);
    for (unsigned e = 0; e < ne; ++e) {
      auto& bucket = buckets[e];
      // Different physical order inside each expert, independent of slot order.
      for (unsigned j = bucket.size(); j > 1; --j)
        std::swap(bucket[j - 1], bucket[rng.Next() % j]);
      bounds[e + 1] = bounds[e] + ((bucket.size() + 15) / 16) * 16;
      Require(unsigned(bounds[e + 1]) <= capacity, "Padded capacity exceeded");
      for (unsigned j = 0; j < bucket.size(); ++j)
        slots[bounds[e] + j] = bucket[j];
      for (unsigned j = 0; j < unsigned(bounds[e + 1] - bounds[e]); j += bn)
        tiles.push_back(e | ((j / bn) << 16));
    }
    std::vector<unsigned> seen(n);
    for (int s : slots)
      if (s >= 0) {
        Require(unsigned(s) < n, "Invalid source slot");
        ++seen[s];
      }
    Require(
        std::all_of(seen.begin(), seen.end(), [](auto v) { return v == 1; }),
        "Routing is not a complete permutation");
    for (unsigned row = 0; row < n; ++row) {
      for (unsigned c = 0; c < 640; ++c) {
        float v = float(int(rng.Next() >> 16) - 32768) / 32768.0f;
        if (special) {
          if (row % 4 == 0)
            v = c & 1 ? -0.0f : 0.0f;
          else if (row % 4 == 1)
            v = std::bit_cast<float>((rng.Next() & 0x807fffffu) | 1u);
          else
            v = std::ldexp(v, row % 4 == 2 ? -116 : 116);
        }
        values[std::size_t(row) * 640 + c] = v;
      }
    }
    input = std::make_unique<Device>(values.size() * 4);
    bd = std::make_unique<Device>(bounds.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    td = std::make_unique<Device>(tiles.size() * 4);
    weights = std::make_unique<Device>(std::size_t(ne) * m * 3 * 84);
    Upload(*input, values, stream);
    Upload(*bd, bounds, stream);
    Upload(*sd, slots, stream);
    Upload(*td, tiles, stream);
    std::vector<std::uint8_t> encoded(weights->bytes);
    for (std::size_t off = 0; off < encoded.size(); off += 84) {
      for (unsigned j = 0; j < 80; ++j)
        encoded[off + j] = rng.Next() >> 24;
      const std::uint16_t d = HalfBits(0.00125f), minimum = HalfBits(0.00075f);
      std::memcpy(encoded.data() + off + 80, &d, 2);
      std::memcpy(encoded.data() + off + 82, &minimum, 2);
    }
    Upload(*weights, encoded, stream);
    unsigned i = 0;
    for (Device* p : {input.get(), bd.get(), sd.get(), td.get(), weights.get()})
      immutable[i++] = Hash(Read(*p, stream));
    for (unsigned a = 0; a < 2; ++a) {
      packed[a] = std::make_unique<Output>(
          std::size_t(a ? capacity : rows) * 640, true);
      scales[a] = std::make_unique<Output>(rows, false);
      down[a] = std::make_unique<Output>(std::size_t(rows) * m, true);
    }
  }

  void Pack(unsigned arm, hipStream_t stream) {
    const auto* x = static_cast<const float*>(input->data);
    auto* h = static_cast<__half*>(packed[arm]->Data());
    auto* sc = static_cast<float*>(scales[arm]->Data());
    const bool ok =
        arm ? q::PackQ2ExpertOrder(x, h, sc,
                                   static_cast<const std::int32_t*>(sd->data),
                                   capacity, stream)
            : q::PackQ2ScaledRows(x, h, sc, rows, 640, stream);
    Require(ok, "Packing dispatch refused");
  }

  void Down(unsigned arm, hipStream_t stream) {
    const auto fn =
        arm ? q::RoutedQ2ExpertOrderGemm : q::RoutedQ2ScaledHalfGemm;
    Require(fn(weights->data, static_cast<const __half*>(packed[arm]->Data()),
               static_cast<const float*>(scales[arm]->Data()),
               static_cast<const std::int32_t*>(td->data), tiles.size(),
               tile_rows, static_cast<const std::int32_t*>(bd->data),
               static_cast<const std::int32_t*>(sd->data),
               static_cast<__half*>(down[arm]->Data()), width, 640, stream),
            "Down dispatch refused");
  }

  void CheckInputs(hipStream_t stream) {
    unsigned i = 0;
    for (Device* p : {input.get(), bd.get(), sd.get(), td.get(), weights.get()})
      Require(Hash(Read(*p, stream)) == immutable[i++],
              "Input or routing mutated");
  }

  bool Check(const std::string& name, hipStream_t stream) {
    std::array<std::vector<std::uint8_t>, 2> ph, sc, outputs;
    for (unsigned a = 0; a < 2; ++a) {
      packed[a]->Poison(stream);
      scales[a]->Poison(stream);
      Pack(a, stream);
      ph[a] = packed[a]->Checked(stream);
      sc[a] = scales[a]->Checked(stream);
      Save(name + (a ? "-candidate-half" : "-parent-half"), ph[a]);
      Save(name + (a ? "-candidate-scale" : "-parent-scale"), sc[a]);
      if (!extreme) {
        down[a]->Poison(stream);
        Down(a, stream);
        outputs[a] = down[a]->Checked(stream);
        Save(name + (a ? "-candidate-down" : "-parent-down"), outputs[a]);
      }
    }
    std::size_t layout_errors = 0, padding_errors = 0;
    for (unsigned r = 0; r < capacity; ++r) {
      const auto* p = ph[1].data() + packed[1]->offset + std::size_t(r) * 1280;
      if (slots[r] >= 0) {
        const auto* ref =
            ph[0].data() + packed[0]->offset + std::size_t(slots[r]) * 1280;
        layout_errors += std::memcmp(p, ref, 1280) != 0;
      } else {
        padding_errors +=
            std::any_of(p, p + 1280, [](auto v) { return v != 0; });
      }
    }
    std::array<std::size_t, 2> half_errors{}, scale_errors{};
    std::vector<unsigned> sorted_row(rows);
    for (unsigned r = 0; r < capacity; ++r)
      if (slots[r] >= 0)
        sorted_row[slots[r]] = r;
    for (unsigned r = 0; r < rows; ++r) {
      double peak = 0;
      for (unsigned c = 0; c < 640; ++c)
        peak =
            std::max(peak, std::fabs(double(values[std::size_t(r) * 640 + c])));
      const int shift =
          peak == 0 ? 0 : std::clamp(13 - std::ilogb(peak), -120, 120);
      const auto expected_scale =
          std::bit_cast<unsigned>(float(std::ldexp(1.0, -shift)));
      for (unsigned a = 0; a < 2; ++a) {
        unsigned observed;
        std::memcpy(&observed, sc[a].data() + scales[a]->offset + r * 4, 4);
        scale_errors[a] += observed != expected_scale;
        const unsigned physical = a ? sorted_row[r] : r;
        for (unsigned c = 0; c < 640; ++c) {
          std::uint16_t h;
          std::memcpy(&h,
                      ph[a].data() + packed[a]->offset +
                          (std::size_t(physical) * 640 + c) * 2,
                      2);
          const float v = float(
              std::ldexp(double(values[std::size_t(r) * 640 + c]), shift));
          half_errors[a] += h != HalfBits(v);
        }
      }
    }
    const bool scale_exact = sc[0] == sc[1];
    const bool down_exact = extreme || outputs[0] == outputs[1];
    CheckInputs(stream);
    std::cout << "{\"event\":\"expert_order_check\",\"case\":\"" << name
              << "\",\"rows\":" << rows << ",\"experts\":" << experts
              << ",\"width\":" << width << ",\"tile_rows\":" << tile_rows
              << ",\"capacity\":" << capacity
              << ",\"layout_errors\":" << layout_errors
              << ",\"padding_errors\":" << padding_errors
              << ",\"scale_exact\":" << scale_exact
              << ",\"down_checked\":" << !extreme
              << ",\"down_exact\":" << down_exact
              << ",\"parent_half_oracle_errors\":" << half_errors[0]
              << ",\"candidate_half_oracle_errors\":" << half_errors[1]
              << ",\"parent_scale_oracle_errors\":" << scale_errors[0]
              << ",\"candidate_scale_oracle_errors\":" << scale_errors[1]
              << "}\n";
    return !layout_errors && !padding_errors && scale_exact && down_exact &&
           !half_errors[0] && !half_errors[1] && !scale_errors[0] &&
           !scale_errors[1];
  }
};

static void Time(OrderedCase& p, hipStream_t stream) {
  Require(p.input->bytes > 32u * 1024 * 1024 &&
              p.weights->bytes > 32u * 1024 * 1024,
          "Each production input/weight working set must exceed MALL");
  hipEvent_t begin{}, end{};
  Hip(hipEventCreate(&begin));
  Hip(hipEventCreate(&end));
  for (unsigned cycle = 0; cycle < 2; ++cycle) {
    const unsigned iterations = cycle ? 3 : 8;
    for (unsigned rep = 0; rep < 7; ++rep) {
      for (unsigned order = 0; order < 2; ++order) {
        const unsigned arm = (rep + order) % 2;
        Hip(hipEventRecord(begin, stream));
        for (unsigned i = 0; i < iterations; ++i) {
          p.Pack(arm, stream);
          if (cycle)
            p.Down(arm, stream);
        }
        Hip(hipEventRecord(end, stream));
        Hip(hipEventSynchronize(end));
        float ms;
        Hip(hipEventElapsedTime(&ms, begin, end));
        std::cout << "{\"event\":\"expert_order_timing\",\"scope\":\""
                  << (cycle ? "pack_down" : "pack") << "\",\"rep\":" << rep
                  << ",\"order\":" << order << ",\"candidate\":" << bool(arm)
                  << ",\"warmup\":" << (rep < 2)
                  << ",\"iterations\":" << iterations
                  << ",\"input_bytes\":" << p.input->bytes
                  << ",\"weight_bytes\":" << (cycle ? p.weights->bytes : 0)
                  << ",\"us_per_iteration\":" << double(ms) * 1000 / iterations
                  << "}\n";
      }
    }
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
    for (unsigned rows : {1u, 7u, 8u, 9u, 15u, 16u, 17u, 31u, 33u, 97u, 257u}) {
      for (unsigned bn : {16u, 48u, 64u}) {
        OrderedCase p(rows, 7, rows & 1 ? 129 : 128, bn, false, stream);
        pass = p.Check(
                   "rows-" + std::to_string(rows) + "-bn-" + std::to_string(bn),
                   stream) &&
               pass;
      }
    }
    {
      OrderedCase p(257, 19, 128, 48, true, stream);
      pass = p.Check("extreme", stream) && pass;
    }
    OrderedCase production(20480, 512, 2560, 48, false, stream);
    Require(!q::PackQ2ExpertOrder(
                nullptr, static_cast<__half*>(production.packed[1]->Data()),
                static_cast<float*>(production.scales[1]->Data()),
                static_cast<const std::int32_t*>(production.sd->data),
                production.capacity, stream),
            "Null input accepted");
    pass = production.Check("production-before", stream) && pass;
    Time(production, stream);
    pass = production.Check("production-after", stream) && pass;
    Hip(hipStreamSynchronize(stream));
    Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"complete\",\"pass\":" << pass << "}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) {
    std::cerr << "Unsafe fixture/dispatch failure: " << e.what() << '\n';
    return 2;
  }
}
