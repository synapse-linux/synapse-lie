// SPDX-License-Identifier: MIT
static void Require(bool condition, const char* message) {
  if (!condition)
    throw std::runtime_error(message);
}
static void Hip(hipError_t value) {
  if (value != hipSuccess)
    throw std::runtime_error(hipGetErrorString(value));
}
struct Device {
  void* storage{};
  void* data{};
  std::size_t bytes{};
  static constexpr std::size_t guard = 64;
  explicit Device(std::size_t size) : bytes(size) {
    Hip(hipMalloc(&storage, bytes + 2 * guard));
    data = static_cast<std::uint8_t*>(storage) + guard;
    Guard(nullptr);
    Hip(hipStreamSynchronize(nullptr));
  }
  void Guard(hipStream_t stream) {
    Hip(hipMemsetAsync(storage, 0xA7, guard, stream));
    Hip(hipMemsetAsync(static_cast<std::uint8_t*>(data) + bytes, 0xA7, guard,
                       stream));
  }
  void CheckGuards(hipStream_t stream) const {
    std::array<std::uint8_t, 2 * guard> got{};
    Hip(hipMemcpyAsync(got.data(), storage, guard, hipMemcpyDeviceToHost,
                       stream));
    Hip(hipMemcpyAsync(got.data() + guard,
                       static_cast<const std::uint8_t*>(data) + bytes, guard,
                       hipMemcpyDeviceToHost, stream));
    Hip(hipStreamSynchronize(stream));
    for (auto byte : got)
      Require(byte == 0xA7, "Corrupted device guard");
  }
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device() {
    if (storage)
      (void)hipFree(storage);
  }
};
static std::string Hash(const std::vector<std::uint8_t>& bytes) {
  return gufo::crypto::Sha256Hex(bytes);
}
static std::vector<std::uint8_t> Read(const Device& buffer,
                                      hipStream_t stream) {
  buffer.CheckGuards(stream);
  std::vector<std::uint8_t> result(buffer.bytes);
  Hip(hipMemcpyAsync(result.data(), buffer.data, buffer.bytes,
                     hipMemcpyDeviceToHost, stream));
  Hip(hipStreamSynchronize(stream));
  return result;
}
template<class T>
static void Upload(Device& destination, const std::vector<T>& source,
                   hipStream_t stream) {
  Require(destination.bytes == source.size() * sizeof(T),
          "Invalid input byte count");
  destination.Guard(stream);
  Hip(hipMemcpyAsync(destination.data, source.data(), destination.bytes,
                     hipMemcpyHostToDevice, stream));
  Hip(hipStreamSynchronize(stream));
}
struct Random {
  std::uint32_t state{713};
  std::uint32_t Next() {
    state = state * 1664525u + 1013904223u;
    return state;
  }
  float Value() { return (float(int(Next() >> 16) - 32768)) / 32768.0f; }
};


// Independent integer IEEE-754 binary32 -> binary16, round to nearest/even.
static std::uint16_t RoundHalf(float value) {
  const auto bits = std::bit_cast<std::uint32_t>(value);
  const auto sign = std::uint16_t((bits >> 16) & 0x8000u);
  const unsigned exponent = (bits >> 23) & 255u;
  const unsigned fraction = bits & 0x7fffffu;
  if (exponent == 255)
    return sign | (fraction ? 0x7e00u : 0x7c00u);
  if (exponent > 142)
    return sign | 0x7c00u;
  if (exponent < 102)
    return sign;
  const unsigned mantissa = fraction | (exponent ? 0x800000u : 0u);
  const unsigned shift = exponent < 113 ? 126u - exponent : 13u;
  const unsigned lost = mantissa & ((1u << shift) - 1u);
  unsigned rounded = mantissa >> shift;
  const unsigned midpoint = 1u << (shift - 1);
  rounded += lost > midpoint || (lost == midpoint && (rounded & 1u));
  const unsigned encoded = exponent < 113 ? rounded : ((exponent - 113) << 10) + rounded;
  return sign | std::uint16_t(encoded);
}

