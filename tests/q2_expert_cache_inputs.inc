// SPDX-License-Identifier: MIT
// Input construction retained from qualified IQ2 and Q2 fixtures.
namespace gate_case {
struct Inputs {
  unsigned n, m, k, experts, used, width;
  std::vector<__half> activation;
  std::vector<std::int32_t> bounds, tokens, slots, narrow, wide;
  std::vector<std::uint8_t> encoded;
  std::array<std::unique_ptr<Device>, 3> gate, up;
  std::array<std::string, 3> gate_hash, up_hash;
  Device x;
  std::unique_ptr<Device> bd, td, sd, nd, wd;

  Inputs(unsigned rows, unsigned output, unsigned inner, unsigned active,
         unsigned top, unsigned tile, hipStream_t stream)
      : n(rows),
        m(output),
        k(inner),
        experts(active),
        used(top),
        width(tile),
        activation(std::size_t(n) * k),
        bounds(experts + 1),
        encoded(std::size_t(experts) * m * (k / 256) * 66),
        x(activation.size() * 2) {
    Require(k % 256 == 0 && used <= experts, "Invalid IQ2 shape");
    Random rng;
    for (std::size_t i = 0; i < activation.size(); ++i) {
      const float value = i % 37 == 0 ? -0.0f
                          : i % 41 == 0
                              ? 0.0000001f
                              : float(int(rng.Next() >> 16) - 32768) / 262144;
      activation[i] = __float2half_rn(value);
    }
    Upload(x, activation, stream);
    std::vector<unsigned> counts(experts), cursor(experts);
    for (unsigned slot = 0; slot < n * used; ++slot)
      ++counts[slot % experts];
    for (unsigned e = 0; e < experts; ++e)
      bounds[e + 1] = bounds[e] + ((counts[e] + 15) / 16) * 16;
    tokens.assign(bounds.back(), -1);
    slots.assign(bounds.back(), -1);
    for (unsigned slot = 0; slot < n * used; ++slot) {
      const unsigned expert = slot % experts;
      const auto offset = unsigned(bounds[expert]) + cursor[expert]++;
      tokens[offset] = std::int32_t(slot / used);
      slots[offset] = std::int32_t(slot);
    }
    for (unsigned e = 0; e < experts; ++e) {
      if (width) {
        for (unsigned j = 0; j < (counts[e] + 15) / 16 * 16; j += width)
          narrow.push_back(std::int32_t(e | (j / width) << 16));
      } else {
        const unsigned groups = (counts[e] + 63) / 64;
        for (unsigned j = 0; j < groups / 2; ++j)
          wide.push_back(std::int32_t(e | j << 16));
        if (groups & 1)
          narrow.push_back(std::int32_t(e | (groups - 1) << 16));
      }
    }
    bd = std::make_unique<Device>(bounds.size() * 4);
    td = std::make_unique<Device>(tokens.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    nd = std::make_unique<Device>(narrow.size() * 4);
    wd = std::make_unique<Device>(wide.size() * 4);
    Upload(*bd, bounds, stream);
    Upload(*td, tokens, stream);
    Upload(*sd, slots, stream);
    Upload(*nd, narrow, stream);
    Upload(*wd, wide, stream);
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      for (unsigned projection = 0; projection < 2; ++projection) {
        for (std::size_t block = 0; block < encoded.size(); block += 66) {
          const float scale = (block / 66) % 29 == 0   ? 0.0f
                              : (block / 66) % 31 == 0 ? -0.0000001f
                              : (block / 66) % 43 == 0 ? -0.00125f
                                                       : 0.00125f;
          const __half d = __float2half_rn(scale);
          std::memcpy(encoded.data() + block, &d, 2);
          for (unsigned group = 0; group < 8; ++group) {
            const std::uint32_t indices = rng.Next(), signs = rng.Next();
            std::memcpy(encoded.data() + block + 2 + group * 8, &indices, 4);
            std::memcpy(encoded.data() + block + 6 + group * 8, &signs, 4);
          }
        }
        auto& device = projection ? up[rotation] : gate[rotation];
        auto& digest = projection ? up_hash[rotation] : gate_hash[rotation];
        device = std::make_unique<Device>(encoded.size());
        Upload(*device, encoded, stream);
        digest = Hash(encoded);
      }
    }
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned r = 0; r < 3; ++r) {
      Require(Hash(Read(*gate[r], stream)) == gate_hash[r],
              "Gate weights changed");
      Require(Hash(Read(*up[r], stream)) == up_hash[r], "Up weights changed");
    }
    const auto bytes = Read(x, stream);
    Require(std::memcmp(bytes.data(), activation.data(), bytes.size()) == 0,
            "Activations changed");
  }
};
}
namespace down_case {
struct Inputs {
  unsigned n, m, k, experts, used, width;
  std::vector<__half> activation;
  std::vector<float> inverse;
  std::vector<std::int32_t> bounds, slots, tiles;
  std::vector<std::uint8_t> encoded;
  std::array<std::unique_ptr<Device>, 3> weights;
  std::array<std::string, 3> weight_hash;
  Device x, scale;
  std::unique_ptr<Device> bd, sd, td;

  Inputs(unsigned tokens, unsigned output, unsigned inner, unsigned active,
         unsigned top, unsigned tile, hipStream_t stream)
      : n(tokens),
        m(output),
        k(inner),
        experts(active),
        used(top),
        width(tile),
        activation(std::size_t(n) * used * k),
        inverse(std::size_t(n) * used),
        bounds(experts + 1),
        encoded(std::size_t(experts) * m * ((k + 255) / 256) * 84),
        x(activation.size() * 2),
        scale(inverse.size() * 4) {
    Require(k % 64 == 0 && used <= experts, "Invalid Q2 shape");
    Random rng;
    for (std::size_t i = 0; i < activation.size(); ++i) {
      const float magnitude = i % 97 == 0 ? 8192.0f : 16.0f;
      const float value = i % 37 == 0   ? -0.0f
                          : i % 41 == 0 ? 0.0000001f
                                        : float(int(rng.Next() >> 16) - 32768) /
                                              32768 * magnitude;
      activation[i] = __float2half_rn(value);
    }
    for (std::size_t i = 0; i < inverse.size(); ++i)
      inverse[i] = std::ldexp(1.0f, int(i % 23) - 30);
    Upload(x, activation, stream);
    Upload(scale, inverse, stream);
    std::vector<unsigned> counts(experts), cursor(experts);
    for (unsigned slot = 0; slot < n * used; ++slot)
      ++counts[slot % experts];
    for (unsigned e = 0; e < experts; ++e)
      bounds[e + 1] = bounds[e] + ((counts[e] + 15) / 16) * 16;
    slots.assign(bounds.back(), -1);
    for (unsigned slot = 0; slot < n * used; ++slot) {
      const unsigned e = slot % experts;
      slots[unsigned(bounds[e]) + cursor[e]++] = std::int32_t(slot);
    }
    for (unsigned e = 0; e < experts; ++e)
      for (unsigned j = 0; j < (counts[e] + 15) / 16 * 16; j += width)
        tiles.push_back(std::int32_t(e | (j / width) << 16));
    bd = std::make_unique<Device>(bounds.size() * 4);
    sd = std::make_unique<Device>(slots.size() * 4);
    td = std::make_unique<Device>(tiles.size() * 4);
    Upload(*bd, bounds, stream);
    Upload(*sd, slots, stream);
    Upload(*td, tiles, stream);
    for (unsigned rotation = 0; rotation < 3; ++rotation) {
      for (std::size_t block = 0; block < encoded.size(); block += 84) {
        for (unsigned i = 0; i < 80; ++i)
          encoded[block + i] = std::uint8_t(rng.Next() >> 24);
        const auto index = block / 84 + rotation;
        const float value = index % 29 == 0   ? 0.0f
                            : index % 31 == 0 ? -0.0000001f
                            : index % 43 == 0 ? -0.00125f
                                              : 0.00125f;
        const __half d = __float2half_rn(value),
                     minimum = __float2half_rn(value * 0.75f);
        std::memcpy(encoded.data() + block + 80, &d, 2);
        std::memcpy(encoded.data() + block + 82, &minimum, 2);
      }
      weights[rotation] = std::make_unique<Device>(encoded.size());
      Upload(*weights[rotation], encoded, stream);
      weight_hash[rotation] = Hash(encoded);
    }
  }
  void Unchanged(hipStream_t stream) {
    for (unsigned r = 0; r < 3; ++r)
      Require(Hash(Read(*weights[r], stream)) == weight_hash[r],
              "Weights changed");
    for (const auto& pair :
         {std::pair<const Device*, const void*>{&x, activation.data()},
          std::pair<const Device*, const void*>{&scale, inverse.data()}}) {
      const auto bytes = Read(*pair.first, stream);
      Require(std::memcmp(bytes.data(), pair.second, bytes.size()) == 0,
              "Input changed");
    }
  }
};

}
