// SPDX-License-Identifier: MIT
// Synthetic GPU operators only; no original model access or CPU model forward.
#include "qfn_mmq_prelude.h"
namespace qfn_mmq {
#include "common.hpp"
#include "vecdotq.hpp"
}
#include "qfn_mmq.h"
#include "q2_operator_fixture.hpp"
#include <iomanip>

namespace {
constexpr unsigned kCases = 256 * 128;
constexpr unsigned kOutputs = kCases * 32;

__global__ void SignProbe(const qfn_mmq::block_iq2_xxs* weights,
                          const qfn_mmq::block_q8_1* x, float* out) {
  const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < kOutputs)
    out[i] = qfn_mmq::vec_dot_iq2_xxs_q8_1(weights, x + i % 32, i / 32, 0);
}

void Save(const std::string& name, const std::vector<float>& values) {
  std::ofstream out("results/iq2-signs-" + name + ".f32", std::ios::binary);
  out.write(reinterpret_cast<const char*>(values.data()), values.size() * sizeof(float));
  Check(bool(out), "Cannot save IQ2 evidence");
}

void Exhaustive() {
  std::vector<qfn_mmq::block_iq2_xxs> w(kCases);
  std::vector<qfn_mmq::block_q8_1> x(32);
  for (unsigned i = 0; i < kCases; ++i) {
    w[i].d = __float2half(8.f); // Neutralizes the exact factor 1/8.
    std::uint32_t signs = 0;
    for (unsigned part = 0; part < 4; ++part) {
      reinterpret_cast<unsigned char*>(w[i].qs)[part] = i / 128;
      signs |= ((i % 128) ^ (17 * part)) << (7 * part);
    }
    std::memcpy(reinterpret_cast<unsigned char*>(w[i].qs) + 4, &signs, 4);
  }
  for (unsigned lane = 0; lane < 32; ++lane) {
    x[lane].ds = __floats2half2_rn(1.f, 1.f);
    x[lane].qs[lane] = 1;
  }
  Device wd(w.size() * sizeof(w[0])), xd(x.size() * sizeof(x[0]));
  Device yd((kOutputs + 2) * sizeof(float));
  Hip(hipMemcpy(wd.data,w.data(),w.size()*sizeof(w[0]),hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data,x.data(),x.size()*sizeof(x[0]),hipMemcpyHostToDevice));
  Hip(hipMemset(yd.data,0xa5,(kOutputs+2)*sizeof(float)));
  SignProbe<<<(kOutputs+255)/256,256>>>(
      static_cast<qfn_mmq::block_iq2_xxs*>(wd.data),
      static_cast<qfn_mmq::block_q8_1*>(xd.data),static_cast<float*>(yd.data)+1);
  Hip(hipGetLastError());Hip(hipDeviceSynchronize());
  std::vector<float> got(kOutputs+2);
  Hip(hipMemcpy(got.data(),yd.data,got.size()*sizeof(float),hipMemcpyDeviceToHost));
  Check(std::bit_cast<std::uint32_t>(got.front())==0xa5a5a5a5u &&
        std::bit_cast<std::uint32_t>(got.back())==0xa5a5a5a5u,"Sign probe overwrote guard");
  for (unsigned i=0;i<kOutputs;++i) {
    const unsigned c=i/32, lane=i%32;
    const unsigned sign7=(c%128)^(17*(lane/8));
    const unsigned signs=sign7|((std::popcount(sign7)&1u)<<7);
    const int mag=(grid[c/128]>>(8*(lane%8)))&255;
    const float expected=(signs&(1u<<(lane%8)))?-float(mag):float(mag);
    Check(std::bit_cast<std::uint32_t>(got[i+1])==std::bit_cast<std::uint32_t>(expected),
          "Exhaustive codebook/sign GPU result changed");
  }
  Save("exhaustive",got);
  std::cout << "{\"event\":\"iq2_signs_exhaustive\",\"codebook_entries\":256,"
               "\"sign_indices\":128,\"lane_outputs\":" << kOutputs <<
               ",\"exact\":true}\n";
}

// Generate encoded bytes directly: the benchmark rotates 512 experts and
// retains no dense expansion of their weights, either on host or device.
std::vector<unsigned char> Encoded(int seed) {
  constexpr unsigned experts=512, m=640, blocks=10;
  std::vector<unsigned char> out(std::size_t(experts)*m*blocks*66);
  for (unsigned row=0;row<experts*m;++row)
    for (unsigned block=0;block<blocks;++block) {
      auto* p=out.data()+(std::size_t(row)*blocks+block)*66;
      const __half d=__float2half(0.00319f*(1+(row+seed)%3));
      std::memcpy(p,&d,2);
      for (unsigned group=0;group<8;++group) {
        std::uint32_t bits=((group+block+row+seed)%16)<<28;
        for (unsigned part=0;part<4;++part) {
          p[2+group*8+part]=(row*13+block*17+group*19+part*23+seed)%256;
          bits|=((row+block*13+part*17+seed)%128)<<(7*part);
        }
        std::memcpy(p+2+group*8+4,&bits,4);
      }
    }
  return out;
}

double Weight(const std::vector<unsigned char>& w, int expert, int row, int j) {
  const auto* p=w.data()+((std::size_t(expert)*640+row)*10+j/256)*66;
  __half dh;std::memcpy(&dh,p,2);
  const unsigned g=(j%256)/32, part=(j%32)/8, lane=j%8;
  std::uint32_t bits;std::memcpy(&bits,p+2+g*8+4,4);
  const unsigned sign7=(bits>>(7*part))&127;
  const unsigned signs=sign7|((std::popcount(sign7)&1u)<<7);
  const unsigned code=p[2+g*8+part];
  const double mag=(grid[code]>>(8*lane))&255;
  return double(__half2float(dh))*(2*(bits>>28)+1)*0.125*mag*
         ((signs&(1u<<lane))?-1:1);
}

void Cycle() {
  constexpr int m=640,k=2560,experts=512,used=10,steps=64;
  auto gate=Encoded(3),up=Encoded(11);
  std::vector<float> x(k);
  for(int i=0;i<k;++i)x[i]=float(i%32==0?127:(i*17+31)%251-125)/256;
  std::vector<std::int32_t> ids(steps*used);
  for(int i=0;i<steps*used;++i)ids[i]=(i*37)%experts;
  Device gd(gate.size()),ud(up.size()),xd(k*sizeof(float)),id(ids.size()*sizeof(ids[0]));
  Device yd((m*used+2)*sizeof(float));
  Hip(hipMemcpy(gd.data,gate.data(),gate.size(),hipMemcpyHostToDevice));
  Hip(hipMemcpy(ud.data,up.data(),up.size(),hipMemcpyHostToDevice));
  Hip(hipMemcpy(xd.data,x.data(),k*sizeof(float),hipMemcpyHostToDevice));
  Hip(hipMemcpy(id.data,ids.data(),ids.size()*sizeof(ids[0]),hipMemcpyHostToDevice));
  Hip(hipMemset(yd.data,0xa5,(m*used+2)*sizeof(float)));
  const auto launch=[&](int step) {
    Check(qfn_mmq_moe_gated_vec(16,gd.data,ud.data,static_cast<float*>(xd.data),
          static_cast<std::int32_t*>(id.data)+step*used,static_cast<float*>(yd.data)+1,
          m,k,1,experts,used,nullptr)==0,"IQ2 complete cycle failed");
  };
  std::vector<float> all;
  for(int step=0;step<steps;++step) {
    launch(step);Hip(hipDeviceSynchronize());
    std::vector<float> got(m*used+2);
    Hip(hipMemcpy(got.data(),yd.data,got.size()*sizeof(float),hipMemcpyDeviceToHost));
    Check(std::bit_cast<std::uint32_t>(got.front())==0xa5a5a5a5u &&
          std::bit_cast<std::uint32_t>(got.back())==0xa5a5a5a5u,"Cycle overwrote guard");
    for(int i=1;i<=m*used;++i)Check(std::isfinite(got[i]),"Cycle non-finite output");
    all.insert(all.end(),got.begin()+1,got.end()-1);
    // Independent FP64 sampled dots spread over all expert rotations.
    std::vector<float> sampled;std::vector<double> expected;
    for(int slot=0;slot<used;++slot) {
      const int row=(step*31+slot*53)%m, expert=ids[step*used+slot];
      double a=0,b=0;
      for(int j=0;j<k;++j) {a+=x[j]*Weight(gate,expert,row,j);b+=x[j]*Weight(up,expert,row,j);}
      sampled.push_back(got[1+slot*m+row]);expected.push_back(a/(1+std::exp(-a))*b);
    }
    Compare(sampled,expected,"iq2-signs-cycle-"+std::to_string(step));
  }
  Save("cycle",all);
  hipEvent_t begin,end;Hip(hipEventCreate(&begin));Hip(hipEventCreate(&end));
  for(int sample=0;sample<7;++sample) {
    Hip(hipEventRecord(begin));
    for(int step=0;step<steps;++step)launch(step);
    Hip(hipEventRecord(end));Hip(hipEventSynchronize(end));
    float ms;Hip(hipEventElapsedTime(&ms,begin,end));
    std::cout << "{\"event\":\"iq2_signs_cycle\",\"sample\":" << sample <<
      ",\"warmup\":" << (sample<2?"true":"false") <<
      ",\"rotated_experts\":512,\"calls\":64,\"weight_bytes\":" << gate.size()+up.size() <<
      ",\"microseconds_per_call\":" << ms*1000/steps << "}\n";
  }
  Hip(hipEventDestroy(begin));Hip(hipEventDestroy(end));
}
} // namespace

int main() {
  try {
    std::cout << std::setprecision(10);
    Check(qfn_mmq_init(0)==0,"HIP init failed");
    Exhaustive();Cycle();
    std::cout << "PASS IQ2 sign operators and synthetic complete cycle; no model throughput\n";
  } catch(const std::exception& e) {std::cerr << e.what() << '\n';return 1;}
}
