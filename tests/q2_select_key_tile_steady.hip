// SPDX-License-Identifier: MIT
// Diagnose launch-order/idle effects without changing the selector kernels.
#define main SelectKeyTileSingleMain
#include "q2_select_key_tile.hip"
#undef main

static bool SteadyCase(const std::string& name, unsigned n, unsigned pos,
                       unsigned first, hipStream_t stream) {
  constexpr unsigned pairs = 8;
  Inputs in(n, pos, first, 0);
  std::array<std::unique_ptr<State>, pairs * 2> states;
  std::array<hipEvent_t, pairs * 2> begin{}, end{};
  for (unsigned i = 0; i < states.size(); ++i) {
    states[i] = std::make_unique<State>(n);
    states[i]->Clear();
    Hip(hipEventCreate(&begin[i]));
    Hip(hipEventCreate(&end[i]));
  }
  State warm_original(n), warm_candidate(n);
  warm_original.Clear(); warm_candidate.Clear();
  Hip(hipDeviceSynchronize());
  for (unsigned i = 0; i < 2; ++i) {
    Launch(false, in, warm_original, stream);
    Launch(true, in, warm_candidate, stream);
  }
  Hip(hipStreamSynchronize(stream));
  const auto wall_start = std::chrono::steady_clock::now();
  for (unsigned rep = 0; rep < pairs; ++rep) {
    for (unsigned order = 0; order < 2; ++order) {
      const unsigned arm = (rep + order) % 2, i = rep * 2 + arm;
      Hip(hipEventRecord(begin[i], stream));
      Launch(arm, in, *states[i], stream);
      Hip(hipEventRecord(end[i], stream));
    }
  }
  Hip(hipStreamSynchronize(stream));
  const auto wall_end = std::chrono::steady_clock::now();
  Hip(hipGetLastError());
  // Independent outputs retain every timed result until its full check.
  bool pass = true;
  for (unsigned rep = 0; rep < pairs; ++rep) {
    const auto label = name + "-r" + std::to_string(rep);
    for (unsigned order = 0; order < 2; ++order) {
      const unsigned arm = (rep + order) % 2, i = rep * 2 + arm;
      float ms = 0; Hip(hipEventElapsedTime(&ms, begin[i], end[i]));
      Require(std::isfinite(ms) && ms > 0, "Invalid steady GPU timing");
      std::cout << "{\"event\":\"select_key_tile_steady_timing\",\"case\":\"" << name
        << "\",\"rep\":" << rep << ",\"order\":" << order << ",\"candidate\":" << bool(arm)
        << ",\"iterations\":1,\"rows\":" << n << ",\"start_pos\":" << pos
        << ",\"first_token\":" << first << ",\"gpu_event_us\":" << double(ms) * 1000 << "}\n";
      pass = Oracle(in, *states[i], label, arm) && pass;
      Hip(hipEventDestroy(end[i])); Hip(hipEventDestroy(begin[i]));
    }
    pass = Pair(states[rep*2]->scores, states[rep*2+1]->scores, label, "scores") && pass;
    pass = Pair(states[rep*2]->mask, states[rep*2+1]->mask, label, "mask") && pass;
  }
  pass = Oracle(in, warm_original, name+"-warmup", false) && pass;
  pass = Oracle(in, warm_candidate, name+"-warmup", true) && pass;
  pass = Pair(warm_original.scores, warm_candidate.scores, name+"-warmup", "scores") && pass;
  pass = Pair(warm_original.mask, warm_candidate.mask, name+"-warmup", "mask") && pass;
  in.Unchanged();
  std::cout << "{\"event\":\"select_key_tile_steady_case\",\"case\":\"" << name
    << "\",\"pairs\":" << pairs << ",\"rows\":" << n << ",\"start_pos\":" << pos
    << ",\"first_token\":" << first << ",\"inputs_unchanged\":true,\"guards_finite_written\":true"
    << ",\"completed_wall_total_us\":"
    << std::chrono::duration<double,std::micro>(wall_end-wall_start).count() << "}\n";
  return pass;
}

int main() {
  try {
    std::cout << std::boolalpha << std::defaultfloat << std::setprecision(12);
    hipStream_t stream{}; Hip(hipStreamCreateWithFlags(&stream,hipStreamNonBlocking));
    bool pass = Case("budget-ties",7,2046,0,1,false,stream);
    pass = Case("one-tiny",1,129024,1899,2,false,stream) && pass;
    pass = Case("three-tail",3,129024,1898,0,false,stream) && pass;
    pass = SteadyCase("last-full32",512,28672,1536,stream) && pass;
    pass = SteadyCase("last-full128",512,126976,1536,stream) && pass;
    pass = SteadyCase("last-tail128",365,129024,1536,stream) && pass;
    Hip(hipStreamSynchronize(stream)); Hip(hipStreamDestroy(stream));
    std::cout << "{\"event\":\"select_key_tile_steady_complete\",\"numerical_pass\":" << pass
      << ",\"timing_retained\":true,\"safe_completion\":true,\"model_inference\":false}\n";
    return pass ? 0 : 1;
  } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 2; }
}
