// SPDX-License-Identifier: MIT
// New whole640 producer/packing operator fixture. Synthetic expert rows inside
// a 2048-row input; this is not a substitute model prompt or a model benchmark.
#include <array>
#include <chrono>
#include <filesystem>
#include <iomanip>
#include <memory>

#include "q2_operator_fixture.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
namespace gufo::models::qwen38_flash_next::rocm {
#include "experiments/q2-iq2-whole640-draft.inc"
#include "experiments/q2-iq2-whole640-lds-draft.inc"
}  // namespace gufo::models::qwen38_flash_next::rocm
namespace q = gufo::models::qwen38_flash_next::rocm;

static void Upload(void* target, const void* source, std::size_t bytes) {
  Hip(hipMemcpy(target, source, bytes, hipMemcpyHostToDevice));
}
static std::vector<unsigned char> Download(const void* source,
                                           std::size_t bytes) {
  std::vector<unsigned char> result(bytes);
  Hip(hipMemcpy(result.data(), source, bytes, hipMemcpyDeviceToHost));
  return result;
}
static void Save(const std::string& name,
                 const std::vector<unsigned char>& data) {
  std::ofstream file("results/" + name, std::ios::binary);
  file.write(reinterpret_cast<const char*>(data.data()), data.size());
  Check(bool(file), "Could not save complete operator output");
}
struct Guarded {
  std::size_t bytes, offset, cell;
  Device device;
  Guarded(std::size_t values, bool half, unsigned misalign = 0)
      : bytes(values * (half ? 2 : 4)),
        offset(64 + misalign),
        cell(half ? 2 : 4),
        device(offset + bytes + 64) {
    Reset();
  }
  void* Data() { return static_cast<unsigned char*>(device.data) + offset; }
  void Reset() {
    std::vector<unsigned char> data(offset + bytes + 64, 0xa5);
    for (std::size_t i = offset; i < offset + bytes; i += cell) {
      if (cell == 2) {
        const std::uint16_t poison = 0x7e01;
        std::memcpy(data.data() + i, &poison, 2);
      } else {
        const std::uint32_t poison = 0x7fc00001;
        std::memcpy(data.data() + i, &poison, 4);
      }
    }
    Upload(device.data, data.data(), data.size());
  }
  std::vector<unsigned char> Read(bool finite = true) {
    auto data = Download(device.data, offset + bytes + 64);
    for (std::size_t i = 0; i < offset; ++i)
      Check(data[i] == 0xa5, "Leading guard changed; stop device work");
    for (std::size_t i = offset + bytes; i < data.size(); ++i)
      Check(data[i] == 0xa5, "Trailing guard changed; stop device work");
    std::vector<unsigned char> payload(data.begin() + offset,
                                       data.begin() + offset + bytes);
    if (finite) {
      for (std::size_t i = 0; i < bytes; i += cell) {
        float value;
        if (cell == 2) {
          __half h;
          std::memcpy(&h, payload.data() + i, 2);
          value = __half2float(h);
        } else {
          std::memcpy(&value, payload.data() + i, 4);
        }
        Check(std::isfinite(value),
              "Nonfinite or unwritten output; stop device work");
      }
    }
    return payload;
  }
  void RequireUnwritten() {
    const auto data = Read(false);
    const std::uint16_t half_poison = 0x7e01;
    const std::uint32_t float_poison = 0x7fc00001;
    const void* poison = cell == 2 ? static_cast<const void*>(&half_poison)
                                   : static_cast<const void*>(&float_poison);
    for (std::size_t i = 0; i < bytes; i += cell)
      Check(std::memcmp(data.data() + i, poison, cell) == 0,
            "Ineligible route wrote output; stop device work");
  }
};

struct Fixture {
  unsigned experts, live, lead, slots;
  std::vector<int> bounds, tokens, destinations, tiles;
  std::vector<__half> input;
  Device bd, td, sd, md, xd;
  std::array<std::unique_ptr<Device>, 3> gate, up;
  Guarded wide;
  std::array<std::unique_ptr<Guarded>, 3> packed, inverse;
  std::vector<std::pair<Device*, std::vector<unsigned char>>> immutable;

  Fixture(unsigned ne, unsigned rows, unsigned prefix, unsigned misalign)
      : experts(ne),
        live(rows),
        lead(prefix),
        slots(ne * rows),
        bounds(ne + 1),
        tokens(ne * (prefix + ((rows + 15) / 16) * 16), -1),
        destinations(tokens.size(), -1),
        tiles(ne),
        input(2048 * 2560),
        bd(bounds.size() * 4),
        td(tokens.size() * 4),
        sd(destinations.size() * 4),
        md(tiles.size() * 4),
        xd(input.size() * 2),
        wide(std::size_t(slots) * 640, false) {
    Check(rows >= 1 && rows <= 17 && (prefix == 0 || prefix == 128),
          "Invalid fixture geometry");
    std::uint32_t random = 913;
    const auto next = [&]() {
      return random = random * 1664525U + 1013904223U;
    };
    for (std::size_t i = 0; i < input.size(); ++i) {
      const unsigned row = i / 2560;
      const float value = row % 17 == 0   ? -0.F
                          : row % 19 == 0 ? 1e-7F
                          : i % 37 == 0   ? -0.F
                          : i % 41 == 0
                              ? 1e-7F
                              : float(int(next() >> 16) - 32768) / 262144.F;
      input[i] = __float2half_rn(value);
    }
    const unsigned stride = prefix + ((rows + 15) / 16) * 16;
    for (unsigned expert = 0; expert < ne; ++expert) {
      bounds[expert + 1] = int((expert + 1) * stride);
      tiles[expert] = int(expert | ((prefix / 64) << 16));
      for (unsigned row = 0; row < rows; ++row) {
        const unsigned slot = expert * rows + row;
        tokens[expert * stride + prefix + row] = int((slot * 37) % 2048);
        destinations[expert * stride + prefix + row] = int(slots - 1 - slot);
      }
    }
    Upload(bd.data, bounds.data(), bounds.size() * 4);
    Upload(td.data, tokens.data(), tokens.size() * 4);
    Upload(sd.data, destinations.data(), destinations.size() * 4);
    Upload(md.data, tiles.data(), tiles.size() * 4);
    Upload(xd.data, input.data(), input.size() * 2);
    for (auto [device, size] : {std::pair{&bd, bounds.size() * 4},
                                {&td, tokens.size() * 4},
                                {&sd, destinations.size() * 4},
                                {&md, tiles.size() * 4},
                                {&xd, input.size() * 2}})
      immutable.emplace_back(device, Download(device->data, size));
    const std::size_t weight_bytes = std::size_t(ne) * 640 * 10 * 66;
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      for (auto* collection : {&gate, &up}) {
        auto& device = (*collection)[rotation];
        device = std::make_unique<Device>(weight_bytes);
        std::vector<unsigned char> encoded(weight_bytes);
        for (std::size_t b = 0; b < weight_bytes; b += 66) {
          for (unsigned j = 2; j < 66; ++j)
            encoded[b + j] = next() >> 24;
          const float scale = (b / 66) % 29 == 0   ? 0.F
                              : (b / 66) % 31 == 0 ? -1e-7F
                              : (b / 66) % 43 == 0 ? -.00125F
                                                   : .00125F;
          const __half half = __float2half_rn(scale);
          std::memcpy(encoded.data() + b, &half, 2);
        }
        Upload(device->data, encoded.data(), weight_bytes);
        immutable.emplace_back(device.get(), std::move(encoded));
      }
      packed[rotation] =
          std::make_unique<Guarded>(std::size_t(slots) * 640, true, misalign);
      inverse[rotation] = std::make_unique<Guarded>(slots, false);
    }
  }
  void Run(unsigned arm, unsigned rotation) {
    auto* half = static_cast<__half*>(packed[arm]->Data());
    auto* scale = static_cast<float*>(inverse[arm]->Data());
    const auto* map = static_cast<const int*>(md.data);
    const auto* bound = static_cast<const int*>(bd.data);
    const auto* token = static_cast<const int*>(td.data);
    const auto* slot = static_cast<const int*>(sd.data);
    if (arm == 0) {
      Check(q::RoutedGatedIQ2Gemm(gate[rotation]->data, up[rotation]->data,
                                  static_cast<const __half*>(xd.data), map,
                                  experts, 64, bound, token, slot,
                                  static_cast<float*>(wide.Data()), 640, 2560,
                                  nullptr),
            "Parent gate/up launch failed");
      Check(q::PackQ2ScaledRows(static_cast<float*>(wide.Data()), half, scale,
                                slots, 640, nullptr),
            "Parent packing launch failed");
    } else if (arm == 1) {
      hipLaunchKernelGGL(q::RoutedIq2Whole640DraftKernel, dim3(experts),
                         dim3(256), 0, nullptr, gate[rotation]->data,
                         up[rotation]->data,
                         static_cast<const __half*>(xd.data), map, bound, token,
                         slot, half, scale);
    } else {
      hipLaunchKernelGGL(q::RoutedIq2Whole640LdsDraftKernel, dim3(experts),
                         dim3(256), 0, nullptr, gate[rotation]->data,
                         up[rotation]->data,
                         static_cast<const __half*>(xd.data), map, bound, token,
                         slot, half, scale);
    }
    Hip(hipGetLastError());
  }
  void Unchanged() {
    for (const auto& [device, original] : immutable)
      Check(Download(device->data, original.size()) == original,
            "Immutable input changed; stop device work");
  }
};

// Read exactly the last completed launches. In particular, timed outputs are
// never reset or replaced by a validation replay before they are inspected.
static std::size_t ValidateCase(Fixture& f, const std::string& label,
                                bool timed_outputs) {
  std::size_t changed = 0;
  std::array<std::vector<unsigned char>, 3> half, scales;
  std::array<std::size_t, 3> arm_changed{};
  for (unsigned arm = 0; arm < 3; ++arm) {
    if (arm && f.live > 16) {
      f.packed[arm]->RequireUnwritten();
      f.inverse[arm]->RequireUnwritten();
      continue;
    }
    half[arm] = f.packed[arm]->Read();
    scales[arm] = f.inverse[arm]->Read();
    Save(label + "-arm" + std::to_string(arm) + ".f16", half[arm]);
    Save(label + "-arm" + std::to_string(arm) + "-inverse.f32", scales[arm]);
    if (arm) {
      for (std::size_t i = 0; i < half[0].size(); i += 2)
        arm_changed[arm] +=
            std::memcmp(half[0].data() + i, half[arm].data() + i, 2) != 0;
      for (std::size_t i = 0; i < scales[0].size(); i += 4)
        arm_changed[arm] +=
            std::memcmp(scales[0].data() + i, scales[arm].data() + i, 4) != 0;
      changed += arm_changed[arm];
    }
  }
  const auto wide = f.wide.Read();
  Save(label + "-parent.f32", wide);
  std::size_t scalar_mismatches = 0;
  for (unsigned row = 0; row < f.slots; ++row) {
    float peak = 0.F;
    std::array<float, 640> values;
    std::memcpy(values.data(), wide.data() + std::size_t(row) * 640 * 4,
                640 * 4);
    for (float value : values)
      peak = std::max(peak, std::abs(value));
    int exponent = 0;
    (void)std::frexp(peak, &exponent);
    const int shift = peak == 0.F ? 0 : std::clamp(14 - exponent, -120, 120);
    const float expected_inverse = std::ldexp(1.F, -shift);
    scalar_mismatches +=
        std::memcmp(&expected_inverse, scales[0].data() + row * 4, 4) != 0;
    for (unsigned column = 0; column < 640; ++column) {
      const __half expected =
          __float2half_rn(std::ldexp(values[column], shift));
      scalar_mismatches +=
          std::memcmp(&expected,
                      half[0].data() + (std::size_t(row) * 640 + column) * 2,
                      2) != 0;
    }
  }
  f.Unchanged();
  std::cout << "{\"event\":\"whole640_replay\",\"label\":\"" << label
            << "\",\"rows_per_expert\":" << f.live
            << ",\"experts\":" << f.experts << ",\"changed_values\":" << changed
            << ",\"scalar_pack_mismatches\":" << scalar_mismatches
            << ",\"register_changed_values\":" << arm_changed[1]
            << ",\"lds_changed_values\":" << arm_changed[2]
            << ",\"actual_timed_outputs\":"
            << (timed_outputs ? "true" : "false")
            << ",\"guards_finite_immutable\":true,\"ineligible\":"
            << (f.live > 16 ? "true" : "false") << "}\n";
  return changed + scalar_mismatches;
}

static std::size_t CheckCase(Fixture& f, const std::string& label) {
  f.wide.Reset();
  for (unsigned arm = 0; arm < 3; ++arm) {
    f.packed[arm]->Reset();
    f.inverse[arm]->Reset();
    f.Run(arm, 0);
    Hip(hipDeviceSynchronize());
    if (arm && f.live > 16) {
      f.packed[arm]->RequireUnwritten();
      f.inverse[arm]->RequireUnwritten();
    } else {
      (void)f.packed[arm]->Read();
      (void)f.inverse[arm]->Read();
      if (arm == 0)
        (void)f.wide.Read();
    }
  }
  return ValidateCase(f, label, false);
}

int main() {
  try {
    std::filesystem::create_directories("results");
    std::cout << std::setprecision(12);
    std::size_t mismatches = 0;
    for (unsigned rows : {1U, 2U, 7U, 8U, 9U, 15U, 16U, 17U})
      for (unsigned lead : {0U, 128U})
        for (unsigned misalign : {0U, 2U}) {
          Fixture f(1, rows, lead, misalign);
          const auto label = "edge-" + std::to_string(rows) + "-" +
                             std::to_string(lead) + "-" +
                             std::to_string(misalign);
          mismatches += CheckCase(f, label);
        }
    for (unsigned rows : {4U, 8U, 16U}) {
      Fixture f(64, rows, 0, 0);
      const auto label = "timed-" + std::to_string(rows);
      mismatches += CheckCase(f, label + "-before");
      for (unsigned sample = 0; sample < 7; ++sample) {
        for (unsigned order = 0; order < 3; ++order) {
          const unsigned arm = sample % 2 ? 2 - order : order;
          f.packed[arm]->Reset();
          f.inverse[arm]->Reset();
          if (arm == 0)
            f.wide.Reset();
          Hip(hipDeviceSynchronize());
          const auto begin = std::chrono::steady_clock::now();
          for (unsigned rotation = 0; rotation < 3; ++rotation)
            f.Run(arm, rotation);
          Hip(hipDeviceSynchronize());
          const auto end = std::chrono::steady_clock::now();
          const double us =
              std::chrono::duration<double, std::micro>(end - begin).count() /
              3;
          std::cout << "{\"event\":\"whole640_timing\",\"label\":\"" << label
                    << "\",\"arm\":" << arm << ",\"sample\":" << sample
                    << ",\"warmup\":" << (sample < 2 ? "true" : "false")
                    << ",\"rotations\":3,\"gate_up_pack_wall_us\":" << us
                    << "}\n";
          // Check guards and finite/written values before the next GPU arm.
          (void)f.packed[arm]->Read();
          (void)f.inverse[arm]->Read();
          if (arm == 0)
            (void)f.wide.Read();
        }
        mismatches +=
            ValidateCase(f, label + "-sample" + std::to_string(sample), true);
      }
    }
    std::cout << "{\"event\":\"whole640_complete\",\"numeric_mismatches\":"
              << mismatches
              << ",\"safe_device_work\":true,\"model_inference\":false}\n";
    return mismatches ? 1 : 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 2;
  }
}
