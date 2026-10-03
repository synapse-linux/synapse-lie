// SPDX-License-Identifier: MIT
// Synthetic original-shape shared branch and real GPU event/drain checks.
#include "q2_shared_fork.hpp"
#include "q2_operator_fixture.hpp"
#include "src/core/crypto/sha256.hpp"
#include <span>
namespace q = gufo::models::qwen38_flash_next::rocm;

struct Streams {
  hipStream_t parent{}, branch{};
  hipEvent_t ready{}, done{};
  Streams() {
    Hip(hipStreamCreateWithFlags(&parent, hipStreamNonBlocking));
    Hip(hipStreamCreateWithFlags(&branch, hipStreamNonBlocking));
    Hip(hipEventCreateWithFlags(&ready, hipEventDisableTiming));
    Hip(hipEventCreateWithFlags(&done, hipEventDisableTiming));
  }
  ~Streams() {
    (void)hipStreamSynchronize(branch);
    (void)hipStreamSynchronize(parent);
    (void)hipEventDestroy(done);
    (void)hipEventDestroy(ready);
    (void)hipStreamDestroy(branch);
    (void)hipStreamDestroy(parent);
  }
};
static std::vector<unsigned char> Q8Weights(unsigned rows, unsigned cols,
                                            unsigned seed) {
  std::vector<unsigned char> out(std::size_t(rows) * (cols / 32) * 34);
  for (std::size_t block = 0; block < out.size() / 34; ++block) {
    const __half d = __float2half_rn(0.00031f * (1 + (block + seed) % 5));
    std::memcpy(out.data() + block * 34, &d, 2);
    for (unsigned c = 0; c < 32; ++c)
      out[block * 34 + 2 + c] =
          static_cast<unsigned char>(static_cast<signed char>(
              int((block * 73 + c * 29 + seed) % 127) - 63));
  }
  return out;
}
static std::vector<unsigned char> Read(const Device &d, std::size_t bytes) {
  std::vector<unsigned char> out(bytes);
  Hip(hipMemcpy(out.data(), d.data, bytes, hipMemcpyDeviceToHost));
  return out;
}
static std::string Digest(const std::vector<unsigned char> &data) {
  return gufo::crypto::Sha256Hex(std::span(data));
}
static int FailedLaunch(void *c) noexcept {
  const int rc = q::LieSharedFork::Launch(c);
  return rc ? rc : -17; // Submitted real work, then report an injected failure.
}
static int FailedJoin(void *) noexcept { return -19; }

static void Case(unsigned tokens, unsigned pattern) {
  constexpr unsigned hidden = 2560, width = 640, guard = 16;
  const std::size_t input_n = std::size_t(tokens) * hidden;
  const std::size_t gate_n = std::size_t(tokens) * width;
  const std::size_t output_bytes = (input_n + 2 * guard) * sizeof(float);
  const auto gate = Q8Weights(width, hidden, 1),
             up = Q8Weights(width, hidden, 3),
             down = Q8Weights(hidden, width, 5);
  Device wg(gate.size()), wu(up.size()), wd(down.size());
  Device x(input_n * sizeof(float)), xq(q::Q8TiledBytes(tokens, hidden));
  Device g(gate_n * sizeof(float)), u(gate_n * sizeof(float));
  Device half(gate_n * sizeof(__half)), output(output_bytes),
      capture(output_bytes);
  Device independent(input_n * sizeof(__half));
  Streams s; // Drains before Device destructors on error/unwind.
  Hip(hipMemcpy(wg.data, gate.data(), gate.size(), hipMemcpyHostToDevice));
  Hip(hipMemcpy(wu.data, up.data(), up.size(), hipMemcpyHostToDevice));
  Hip(hipMemcpy(wd.data, down.data(), down.size(), hipMemcpyHostToDevice));
  std::vector<float> input(input_n);
  for (std::size_t i = 0; i < input.size(); ++i)
    input[i] = float(int((i * 19 + pattern * 7) % 257) - 128) *
               (pattern ? 0.000019f : 0.0019f);
  auto prepare = [&] {
    Hip(hipMemcpyAsync(x.data, input.data(), input.size() * sizeof(float),
                       hipMemcpyHostToDevice, s.parent));
    q::QuantizeQ8Tiled(static_cast<float *>(x.data), xq.data, tokens, hidden,
                       s.parent);
    Hip(hipMemsetAsync(output.data, 0xA5, output_bytes, s.parent));
  };
  lie_gpu_fork flow{};
  q::LieSharedFork branch{&flow,
                          s.parent,
                          s.branch,
                          s.ready,
                          s.done,
                          wg.data,
                          wu.data,
                          wd.data,
                          xq.data,
                          static_cast<float *>(g.data),
                          static_cast<float *>(u.data),
                          static_cast<float *>(output.data) + guard,
                          static_cast<__half *>(half.data),
                          tokens,
                          hidden,
                          width};
  prepare();
  branch.branch = s.parent;
  Check(q::LieSharedFork::Launch(&branch) == 0,
        "Sequential shared branch failed");
  Hip(hipStreamSynchronize(s.parent));
  const auto reference = Read(output, output_bytes),
             ref_g = Read(g, gate_n * 4), ref_u = Read(u, gate_n * 4),
             ref_half = Read(half, gate_n * 2);
  for (std::size_t i = 0; i < input_n; ++i) {
    float value;
    std::memcpy(&value, reference.data() + (i + guard) * 4, 4);
    Check(std::isfinite(value), "Non-finite sequential shared output");
  }
  branch.branch = s.branch;
  for (unsigned mode = 0; mode < 4; ++mode) {
    // Invalidate prior packed inputs before testing the ready dependency.
    Hip(hipMemset(xq.data, 0xA5, q::Q8TiledBytes(tokens, hidden)));
    prepare();
    lie_gpu_fork_ops ops = q::LieSharedFork::ops;
    if (mode == 1)
      ops.launch = FailedLaunch;
    if (mode == 2)
      ops.join = FailedJoin;
    const auto started = lie_gpu_fork_begin(&flow, &ops, &branch);
    if (mode == 1) {
      Check(started == LIE_GPU_FAILED, "Partial launch did not fail/drain");
    } else {
      Check(started == LIE_GPU_OK, "Concurrent shared branch failed");
      // Independent parent work while the shared branch owns its output.
      q::NarrowActivations(static_cast<float *>(x.data), independent.data,
                           false, input_n, s.parent);
      const auto rc =
          mode == 3 ? lie_gpu_fork_abort(&flow) : lie_gpu_fork_join(&flow);
      Check(rc == (mode == 2 ? LIE_GPU_FAILED : LIE_GPU_OK),
            "Join/drain status changed");
    }
    Check(flow.state == LIE_GPU_IDLE, "Branch storage still owned");
    if (mode != 0) {
      Hip(hipStreamQuery(s.branch));
      Hip(hipStreamQuery(s.parent));
    }
    // A real parent-stream consumer must observe the joined shared output.
    Hip(hipMemcpyAsync(capture.data, output.data, output_bytes,
                       hipMemcpyDeviceToDevice, s.parent));
    Hip(hipStreamSynchronize(s.parent));
    const auto actual = Read(capture, output_bytes);
    Check(actual == reference && Read(g, gate_n * 4) == ref_g &&
              Read(u, gate_n * 4) == ref_u &&
              Read(half, gate_n * 2) == ref_half,
          "Concurrent/drained shared output differs");
    for (unsigned side = 0; side < 2; ++side)
      for (unsigned i = 0; i < guard * 4; ++i)
        Check(actual[side ? (guard + input_n) * 4 + i : i] == 0xA5,
              "Output allocation guard changed");
    std::cout << "{\"event\":\"shared_fork_check\",\"tokens\":" << tokens
              << ",\"pattern\":" << pattern << ",\"mode\":" << mode
              << ",\"bytes_compared\":" << output_bytes + gate_n * 10
              << ",\"exact\":true,\"output_sha256\":\"" << Digest(actual)
              << "\"}\n";
  }
}
int main() {
  try {
    std::cout << std::unitbuf;
    for (unsigned n : {96, 97, 129, 2048})
      for (unsigned p : {0, 1})
        Case(n, p);
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
  return 0;
}
