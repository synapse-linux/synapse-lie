// SPDX-License-Identifier: MIT
// Independent sampled FP64 synthetic operator, outside every GPU timer.
// This is not a CPU model executor or original-weight inference.
static bool Oracle(const Inputs& in, const State& state, unsigned rotation,
                   hipStream_t stream, const char* label, const char* arm) {
  const auto weights = Read(*in.w[rotation], stream);
  const auto projection = Read(state.out, stream);
  const auto convolution = Read(state.convolved, stream);
  const auto dot = [&](unsigned token, unsigned row) {
    double sum = 0;
    for (unsigned k = 0; k < in.k; ++k) {
      const std::size_t offset = (std::size_t(row) * (in.k / 32) + k / 32) * 34;
      __half scale;
      std::int8_t code;
      std::memcpy(&scale, weights.data() + offset, 2);
      std::memcpy(&code, weights.data() + offset + 2 + k % 32, 1);
      // The production operand is rounded to F16 before its WMMA product.
      const double weight = __half2float(__float2half_rn(__half2float(scale) * float(code)));
      const double input = __half2float(in.activation[std::size_t(token) * in.k + k]);
      sum += weight * input;
    }
    return sum;
  };
  const std::array<unsigned, 12> tokens{
      0, 1, 2, 3, 29, 31, 32, 33, 127, 128, in.n - 2, in.n - 1};
  bool all_pass = true;
  for (unsigned field = 0; field < 2; ++field) {
    double squared = 0, reference_squared = 0, peak = 0, reference_peak = 0;
    bool finite = true;
    for (unsigned sample = 0; sample < 24; ++sample) {
      const unsigned token = tokens[sample % tokens.size()];
      unsigned row = (sample * 431u) % 10240;
      double expected;
      const std::vector<std::uint8_t>* output;
      std::size_t index;
      if (field == 0) {
        // Interior raw QKV is intentionally unwritten; sample live rows only.
        if (!(token % 32 < 3 || token % 32 >= 29 || token + 3 >= in.n))
          row = 10240 + (row % 6144);
        expected = dot(token, row);
        output = &projection;
        index = std::size_t(token) * in.m + row;
      } else {
        double sum = 0;
        for (int tap = 0; tap < 4; ++tap) {
          const int source = int(token) - 3 + tap;
          const double value = source < 0
              ? double(in.history[std::size_t(source + 3) * 10240 + row])
              : dot(unsigned(source), row);
          sum += double(in.convolution[row * 4 + unsigned(tap)]) * value;
        }
        expected = sum / (1.0 + std::exp(-sum));
        output = &convolution;
        index = std::size_t(token) * 10240 + row;
      }
      float got;
      std::memcpy(&got, output->data() + index * 4, 4);
      finite = finite && std::isfinite(got) && std::isfinite(expected);
      const double delta = double(got) - expected;
      squared += delta * delta;
      reference_squared += expected * expected;
      peak = std::max(peak, std::abs(delta));
      reference_peak = std::max(reference_peak, std::abs(expected));
    }
    const double relative = std::sqrt(squared / std::max(reference_squared, 1e-24));
    const double scaled = peak / std::max(reference_peak, 1e-12);
    const bool pass = finite && relative <= 0.002 && scaled <= 0.002;
    std::cout << "{\"event\":\"ssm_row_group_oracle\",\"shape\":\"" << label
              << "\",\"arm\":\"" << arm << "\",\"rotation\":" << rotation
              << ",\"field\":\"" << (field ? "convolution" : "projection")
              << "\",\"samples\":24,\"relative_rms\":" << relative
              << ",\"scaled_error\":" << scaled << ",\"limit\":0.002,\"pass\":"
              << pass << "}\n";
    all_pass = pass && all_pass;
  }
  return all_pass;
}
