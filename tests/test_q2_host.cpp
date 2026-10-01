// SPDX-License-Identifier: MIT
// Small generated GGUF storage/binding fixtures, NOT-INFERENCE. No GPU/model
// load. Directly tests the transitional provider's private Binder in this test
// TU only.
#include "src/models/qwen38_flash_next/weights.cpp"

#include <bit>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace q = gufo::models::qwen38_flash_next;
using gufo::core::GgmlType;
using gufo::core::GgufReader;
using Bytes = std::vector<std::uint8_t>;

static void require(bool ok, const std::string &why) {
  if (!ok)
    throw std::runtime_error(why);
}
static void le(Bytes &b, std::uint64_t v, unsigned n) {
  for (unsigned i = 0; i < n; ++i) {
    b.push_back(v & 255);
    v >>= 8;
  }
}
static void text(Bytes &b, const std::string &s) {
  le(b, s.size(), 8);
  b.insert(b.end(), s.begin(), s.end());
}
static std::size_t row_bytes(unsigned type, std::uint64_t columns) {
  // Independent storage expectations, not the implementation under test.
  switch (type) {
  case 0:
    return columns * 4;
  case 1:
  case 30:
    return columns * 2;
  case 7:
    return columns / 32 * 24;
  case 8:
    return columns / 32 * 34;
  case 10:
    return columns / 256 * 84;
  case 12:
    return columns / 256 * 144;
  case 16:
    return columns / 256 * 66;
  case 39:
    return columns / 32 * 17;
  default:
    return 64;
  }
}
struct Image {
  struct Tensor {
    std::string name;
    std::uint64_t cols, rows, experts;
    unsigned type;
  };
  struct Meta {
    std::string key;
    unsigned type, width;
    std::uint64_t value;
    Bytes raw{};
  };
  std::vector<Tensor> tensors;
  std::vector<Meta> metadata;
  void add(const std::string &name, std::uint64_t cols, std::uint64_t rows = 1,
           unsigned type = 0, std::uint64_t experts = 1) {
    tensors.push_back({name, cols, rows, experts, type});
  }
  void padding(unsigned logical = 640, unsigned physical = 768) {
    metadata.push_back({"ds4.qwen4.down.logical_input", 4, 4, logical});
    metadata.push_back({"ds4.qwen4.down.physical_input", 4, 4, physical});
  }
  Bytes bytes() const {
    Bytes b{'G', 'G', 'U', 'F'};
    le(b, 3, 4);
    le(b, tensors.size(), 8);
    le(b, metadata.size(), 8);
    for (const auto &m : metadata) {
      text(b, m.key);
      le(b, m.type, 4);
      if (m.raw.empty())
        le(b, m.value, m.width);
      else
        b.insert(b.end(), m.raw.begin(), m.raw.end());
    }
    std::size_t offset = 0;
    for (const auto &t : tensors) {
      text(b, t.name);
      le(b, 3, 4);
      le(b, t.cols, 8);
      le(b, t.rows, 8);
      le(b, t.experts, 8);
      le(b, t.type, 4);
      le(b, offset, 8);
      offset += row_bytes(t.type, t.cols) * t.rows * t.experts;
      offset = (offset + 31) / 32 * 32;
    }
    const auto start = (b.size() + 31) / 32 * 32;
    b.resize(start + offset);
    return b;
  }
};
static void string_meta(Image &f, const std::string &key,
                        const std::string &value) {
  Bytes b;
  text(b, value);
  f.metadata.push_back({key, 8, 0, 0, b});
}
static void array_meta(Image &f, const std::string &key,
                       const std::vector<std::uint64_t> &values) {
  Bytes b;
  le(b, 10, 4);
  le(b, values.size(), 8);
  for (const auto v : values)
    le(b, v, 8);
  f.metadata.push_back({key, 9, 0, 0, b});
}
static Image config_image(bool identified) {
  Image f;
  string_meta(f, "general.architecture", "qwen4exp");
  const std::pair<const char *, unsigned> fields[] = {
      {"block_count", 49},
      {"nextn_predict_layers", 1},
      {"embedding_length", 2560},
      {"context_length", 262144},
      {"hyper_connection.count", 4},
      {"hyper_connection.low_rank", 320},
      {"full_attention_interval", 4},
      {"attention.head_count", 24},
      {"attention.head_count_kv", 2},
      {"attention.key_length", 256},
      {"rope.dimension_count", 64},
      {"attention.indexer.head_count", 4},
      {"attention.indexer.key_length", 128},
      {"attention.indexer.top_k", 2048},
      {"ssm.conv_kernel", 4},
      {"ssm.state_size", 128},
      {"ssm.group_count", 16},
      {"ssm.time_step_rank", 48},
      {"ssm.inner_size", 6144},
      {"expert_count", 512},
      {"expert_used_count", 10},
      {"expert_feed_forward_length", 640},
      {"expert_shared_feed_forward_length", 640}};
  for (const auto &[key, value] : fields)
    f.metadata.push_back({"qwen4exp." + std::string(key), 4, 4, value});
  f.metadata.push_back({"qwen4exp.attention.layer_norm_rms_epsilon", 6, 4,
                        std::bit_cast<std::uint32_t>(1e-6F)});
  f.metadata.push_back({"qwen4exp.rope.freq_base", 6, 4,
                        std::bit_cast<std::uint32_t>(10000000.0F)});
  std::vector<std::uint64_t> ratios(49, 0);
  for (unsigned i = 3; i < 48; i += 4)
    ratios[i] = 4;
  array_meta(f, "qwen4exp.attention.compress_ratios", ratios);
  if (identified) {
    f.padding();
    string_meta(f, "ds4.qwen4.ngram.source_repository",
                "Qwen/Qwen3.8-Flash-Next");
    string_meta(f, "ds4.qwen4.ngram.source_revision",
                "de4b8e4d43b917e7706784d8bb445c9af86a3540");
  }
  return f;
}
static void config_rule() {
  auto check = [](const Image &f, bool accepted, bool trunk = true) {
    const auto bytes = f.bytes();
    std::string error;
    auto reader = GgufReader::OpenMemory(bytes.data(), bytes.size(), &error);
    require(reader != nullptr, "config fixture reader: " + error);
    auto c = q::Config::FromGguf(*reader, trunk, &error);
    require(c.has_value() == accepted, "config acceptance mismatch: " + error);
    if (c)
      require(c->rope_sections == std::array<std::uint32_t, 4>{11, 11, 10, 0},
              "canonical sections");
  };
  check(config_image(true), true);
  check(config_image(true), false, false); // Not a permissive MTP default.
  check(config_image(false), false);
  auto ordinary = config_image(false);
  array_meta(ordinary, "qwen4exp.rope.dimension_sections", {11, 11, 10, 0});
  check(ordinary, true);
  for (const std::vector<std::uint64_t> &sections :
       {std::vector<std::uint64_t>{11, 11, 10},
        {12, 10, 10, 0},
        {0, 0, 0, 0},
        {11, 11, 10, 1}}) {
    auto f = config_image(true);
    array_meta(f, "qwen4exp.rope.dimension_sections", sections);
    check(f, false);
  }
  auto bad = config_image(true);
  string_meta(bad, "qwen4exp.rope.dimension_sections", "invalid");
  check(bad, false);
  for (const std::string key :
       {"ds4.qwen4.down.logical_input", "ds4.qwen4.down.physical_input",
        "ds4.qwen4.ngram.source_repository",
        "ds4.qwen4.ngram.source_revision"}) {
    auto f = config_image(true);
    std::erase_if(f.metadata, [&](const auto &m) { return m.key == key; });
    check(f, false);
  }
  auto different = config_image(true);
  for (auto &m : different.metadata)
    if (m.key == "ds4.qwen4.down.physical_input")
      m.value = 1024;
  check(different, false);
  auto typed = config_image(true);
  for (auto &m : typed.metadata)
    if (m.key == "ds4.qwen4.down.physical_input") {
      m.type = 10;
      m.width = 8;
    }
  check(typed, false);
}
static q::Config fixture_config() {
  // Deliberately small binder geometry, not a supported full model profile.
  q::Config c;
  c.hidden_size = 256;
  c.hc_count = 4;
  c.hc_low_rank = 32;
  c.ssm_conv_kernel = 4;
  c.ssm_head_dim = 32;
  c.ssm_num_k_heads = 1;
  c.ssm_num_v_heads = 2;
  c.expert_ff = 640;
  c.shared_expert_ff = 640;
  c.num_experts = 3;
  return c;
}
static Image layer_image(unsigned gate_type = 12, unsigned down_type = 7,
                         unsigned inject_type = 0, unsigned down_cols = 640) {
  const auto c = fixture_config();
  Image f;
  for (const std::string stem : {"blk.0.hc_attn", "blk.0.hc_ffn"}) {
    f.add(stem + "_norm.weight", c.HcDim());
    f.add(stem + "_down.weight", c.HcDim(), c.hc_low_rank, 1);
    f.add(stem + "_up.weight", c.hc_low_rank, c.HcDim(), 1);
    f.add(stem + "_inject.weight", c.HcDim(), c.hc_count, inject_type);
  }
  f.add("blk.0.attn_qkv.weight", c.hidden_size, c.SsmConvChannels(), 8);
  f.add("blk.0.attn_gate.weight", c.hidden_size, c.SsmValueDim(), 8);
  f.add("blk.0.ssm_conv1d.weight", c.ssm_conv_kernel, c.SsmConvChannels());
  f.add("blk.0.ssm_alpha.weight", c.hidden_size, c.ssm_num_v_heads);
  f.add("blk.0.ssm_beta.weight", c.hidden_size, c.ssm_num_v_heads);
  f.add("blk.0.ssm_dt.bias", c.ssm_num_v_heads);
  f.add("blk.0.ssm_a", c.ssm_num_v_heads);
  f.add("blk.0.ssm_norm.weight", c.ssm_head_dim);
  f.add("blk.0.ssm_out.weight", c.SsmValueDim(), c.hidden_size, 8);
  f.add("blk.0.ffn_gate_inp.weight", c.hidden_size, c.num_experts);
  f.add("blk.0.ffn_gate_exps.weight", c.hidden_size, c.expert_ff, gate_type,
        c.num_experts);
  f.add("blk.0.ffn_up_exps.weight", c.hidden_size, c.expert_ff, gate_type,
        c.num_experts);
  f.add("blk.0.ffn_down_exps.weight", down_cols, c.hidden_size, down_type,
        c.num_experts);
  f.add("blk.0.ffn_gate_inp_shexp.weight", c.hidden_size);
  f.add("blk.0.ffn_gate_shexp.weight", c.hidden_size, c.shared_expert_ff, 8);
  f.add("blk.0.ffn_up_shexp.weight", c.hidden_size, c.shared_expert_ff, 8);
  f.add("blk.0.ffn_down_shexp.weight", c.shared_expert_ff, c.hidden_size, 8);
  return f;
}
static void bind(const Image &image, bool accepted,
                 const std::string &reason = "") {
  const auto bytes = image.bytes();
  std::string error;
  auto r = GgufReader::OpenMemory(bytes.data(), bytes.size(), &error);
  require(r != nullptr, "fixture reader: " + error);
  q::Binder b{*r, &error};
  const auto c = fixture_config();
  const auto layer = b.Layer(c, 0, true, false, false);
  require(b.ok == accepted, "binder acceptance mismatch: " + error);
  if (!accepted) {
    require(error.find(reason) != std::string::npos, "wrong refusal: " + error);
    return;
  }
  for (const auto *t :
       {&layer.ffn_gate_exps, &layer.ffn_up_exps, &layer.ffn_down_exps}) {
    const auto *info = r->FindTensor(t->name);
    require(info && info->size_bytes == t->SizeBytes(), "physical tensor size");
    require(t->cols == info->dimensions[0], "physical columns lost");
    require(t->RowBytes() == row_bytes(static_cast<unsigned>(t->type), t->cols),
            "row stride");
    require(t->Expert(1) - t->Expert(0) ==
                static_cast<std::ptrdiff_t>(t->RowBytes() * t->rows),
            "expert stride");
    require(t->file_offset ==
                static_cast<std::uint64_t>(
                    static_cast<const std::uint8_t *>(t->data) - bytes.data()),
            "file offset");
  }
  require(c.expert_ff == 640, "logical activation dimension changed");
}
static void storage() {
  for (unsigned type : {8u, 10u, 12u, 16u, 39u}) {
    Image f;
    f.add("weight", 256, 2, type);
    const auto bytes = f.bytes();
    std::string error;
    auto r = GgufReader::OpenMemory(bytes.data(), bytes.size(), &error);
    require(r != nullptr,
            "storage type " + std::to_string(type) + ": " + error);
    require(r->FindTensor("weight")->size_bytes == row_bytes(type, 256) * 2,
            "encoded size");
  }
  for (auto [columns, type] :
       {std::pair{33u, 39u}, std::pair{256u, 65575u}, std::pair{256u, 4242u}}) {
    Image f;
    f.add("bad", columns, 1, type);
    const auto bytes = f.bytes();
    std::string error;
    require(!GgufReader::OpenMemory(bytes.data(), bytes.size(), &error),
            "invalid storage accepted");
  }
}
static void rejection() {
  auto f = layer_image(16, 10, 1, 768);
  bind(f, false, "padding metadata");
  for (unsigned missing : {0u, 1u}) {
    auto x = f;
    x.padding();
    x.metadata.erase(x.metadata.begin() + missing);
    bind(x, false, "padding metadata");
  }
  for (auto [logical, physical] :
       {std::pair{639u, 768u}, std::pair{640u, 640u}, std::pair{640u, 1024u},
        std::pair{640u, 0u}}) {
    auto x = f;
    x.padding(logical, physical);
    bind(x, false, "padding metadata");
  }
  for (auto [type, width] :
       {std::pair{7u, 1u}, std::pair{10u, 8u}, std::pair{5u, 4u}}) {
    auto x = f;
    x.padding();
    x.metadata[1].type = type;
    x.metadata[1].width = width;
    x.metadata[1].value = type == 7 ? 1 : 768;
    bind(x, false, "padding metadata");
  }
  auto x = layer_image(16, 10, 1, 512);
  x.padding();
  bind(x, false, "shape");
  auto wrong_type = layer_image(16, 7, 1, 768);
  wrong_type.padding();
  bind(wrong_type, false, "padding format");
  auto on_unpadded = layer_image();
  on_unpadded.padding();
  bind(on_unpadded, false, "padding format");
}
int main(int argc, char **argv) {
  try {
    require(argc == 2, "one fixture case required");
    const std::string name = argv[1];
    if (name == "config")
      config_rule();
    else if (name == "storage")
      storage();
    else if (name == "iq2")
      bind(layer_image(16), true);
    else if (name == "padded") {
      auto f = layer_image(12, 10, 0, 768);
      f.padding();
      bind(f, true);
    } else if (name == "inject")
      bind(layer_image(12, 7, 1), true);
    else if (name == "legacy")
      bind(layer_image(), true);
    else if (name == "rejection")
      rejection();
    else if (name == "combined") {
      auto f = layer_image(16, 10, 1, 768);
      f.padding();
      f.add("blk.48.ffn_down_exps.weight", 640, 2, 39);
      bind(f, true);
    } else
      throw std::runtime_error("unknown fixture case");
    std::cout << "NOT-INFERENCE: " << name << " host contract PASS\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
