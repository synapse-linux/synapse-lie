// SPDX-License-Identifier: MIT
// Included inside the Qwen ROCm namespace in device_model.cpp.
// Compressed slot-cache mechanism follows independently fetched antirez/ds4;
// numerical kernels and weight representation remain the retained LIE route.
class CompressedExpertCache {
public:
  struct Range { std::uint32_t shard; std::uint64_t offset; std::size_t bytes; };
  struct Layer { Range gate, up, down; };
  struct View { const void* base; const std::int32_t* map; };
  lie_cc policy{};
  std::mutex mutex;
  std::vector<Layer> layers;
  std::unique_ptr<hip::WeightUpload> uploader;
  void* gate{nullptr};
  void* up{nullptr};
  void* down{nullptr};
  std::int32_t* map{nullptr};
  std::int32_t* ids{nullptr};
  View* views{nullptr};
  std::size_t ids_capacity{0}, gate_bytes{0}, down_bytes{0}, bytes{0};
  std::uint64_t read_bytes{0}, calls{0};
  hipEvent_t consumed{nullptr};
  hipStream_t last_stream{nullptr};
  bool waiting{false}, failed{false};

  ~CompressedExpertCache() {
    std::lock_guard lock(mutex);
    if (waiting) {
      const bool complete = hipEventSynchronize(consumed) == hipSuccess;
      if (!complete)
        (void)hipStreamSynchronize(last_stream);
      (void)lie_cc_finish(&policy, complete);
    }
    if (uploader) (void)uploader->Finish(nullptr);
    fprintf(stderr, "{\"event\":\"q2_compressed_cache_stats\",\"calls\":%llu,"
        "\"hits\":%llu,\"misses\":%llu,\"evictions\":%llu,\"loads\":%llu,"
        "\"failed_loads\":%llu,\"read_bytes\":%llu,\"slots\":%u,\"weight_bytes\":%zu,"
        "\"dynamic_id_bytes\":%zu}\n",
        (unsigned long long)calls, (unsigned long long)policy.hits,
        (unsigned long long)policy.misses, (unsigned long long)policy.evictions,
        (unsigned long long)policy.loads, (unsigned long long)policy.failed_loads,
        (unsigned long long)read_bytes, policy.capacity, bytes, ids_capacity * sizeof(std::int32_t));
    if (consumed) (void)hipEventDestroy(consumed);
    for (void* p : {gate, up, down, static_cast<void*>(map),
                   static_cast<void*>(ids), static_cast<void*>(views)})
      if (p) (void)hipFree(p);
    lie_cc_destroy(&policy);
  }

  bool Init(const ModelWeights& w, std::span<const core::GgufMappedRegion> shards,
            std::size_t budget, std::string* error) {
    const auto range = [](const TensorRef& t) {
      return Range{t.shard, t.file_offset, t.SizeBytes() / t.experts};
    };
    for (const auto& l : w.layers)
      layers.push_back({range(l.ffn_gate_exps), range(l.ffn_up_exps), range(l.ffn_down_exps)});
    gate_bytes = layers[0].gate.bytes; down_bytes = layers[0].down.bytes;
    const auto per_slot = 2 * gate_bytes + down_bytes;
    std::size_t free_bytes = 0, total_bytes = 0;
    if (hipMemGetInfo(&free_bytes, &total_bytes) != hipSuccess) return false;
    constexpr std::size_t reserve = std::size_t(8) << 30;
    if (free_bytes <= reserve + 3 * kTailMargin) return false;
    const auto available = std::min(budget, free_bytes - reserve) - 3 * kTailMargin;
    std::uint32_t capacity = static_cast<std::uint32_t>(
        std::min<std::size_t>(w.config.num_layers * 512, available / per_slot));
    // Every layer's complete 2048-token expert set must fit without evicting
    // another expert used by the same launch. Failure does not publish a cache.
    if (capacity < 512 || lie_cc_init(&policy, w.config.num_layers * 512, capacity)) return false;
    bytes = capacity * per_slot + 3 * kTailMargin;
    if (hipMalloc(&gate, capacity * gate_bytes + kTailMargin) != hipSuccess ||
        hipMalloc(&up, capacity * gate_bytes + kTailMargin) != hipSuccess ||
        hipMalloc(&down, capacity * down_bytes + kTailMargin) != hipSuccess ||
        hipMalloc(&map, 512 * sizeof(std::int32_t)) != hipSuccess ||
        hipMalloc(&views, 3 * sizeof(View)) != hipSuccess ||
        hipEventCreateWithFlags(&consumed, hipEventDisableTiming) != hipSuccess) return false;
    if (hipMemset(static_cast<char*>(gate) + capacity * gate_bytes, 0, kTailMargin) != hipSuccess ||
        hipMemset(static_cast<char*>(up) + capacity * gate_bytes, 0, kTailMargin) != hipSuccess ||
        hipMemset(static_cast<char*>(down) + capacity * down_bytes, 0, kTailMargin) != hipSuccess) return false;
    View host[3]{{gate, map}, {up, map}, {down, map}};
    if (hipMemcpy(views, host, sizeof(host), hipMemcpyHostToDevice) != hipSuccess) return false;
    uploader = hip::WeightUpload::Create(shards, error);
    if (!uploader) return false;
    fprintf(stderr, "{\"event\":\"q2_compressed_cache_ready\",\"slots\":%u,"
        "\"total_experts\":%zu,\"weight_bytes\":%zu,\"budget_bytes\":%zu,"
        "\"gate_bytes_per_expert\":%zu,\"down_bytes_per_expert\":%zu}\n",
        capacity, layers.size() * 512, bytes, budget, gate_bytes, down_bytes);
    return true;
  }

  bool Prepare(std::uint32_t layer, const std::int32_t* selected,
               std::size_t count, hipStream_t stream, std::string* error) {
    const auto fail = [&](const char* message) {
      if (error && error->empty()) *error = message;
      failed = true; return false;
    };
    if (failed || layer >= layers.size() || !count) return fail("invalid compressed cache request");
    if (waiting) {
      if (hipEventSynchronize(consumed) != hipSuccess) {
        (void)hipStreamSynchronize(last_stream);
        return fail("compressed cache consumer completion failed");
      }
      waiting = false;
      if (lie_cc_finish(&policy, true)) return fail("compressed cache release failed");
    }
    std::vector<std::int32_t> host_ids(count);
    if (hipMemcpyAsync(host_ids.data(), selected, count * sizeof(std::int32_t),
                       hipMemcpyDeviceToHost, stream) != hipSuccess ||
        hipStreamSynchronize(stream) != hipSuccess) return fail("compressed cache routing download failed");
    std::vector<std::uint32_t> keys, slots;
    std::int32_t host_map[512];
    std::fill_n(host_map, 512, -1);
    for (const auto id : host_ids) {
      if (id < 0 || id >= 512) return fail("compressed cache expert outside model");
      if (host_map[id] == -1) {
        host_map[id] = 0;
        keys.push_back(layer * 512 + static_cast<std::uint32_t>(id));
      }
    }
    slots.resize(keys.size());
    if (lie_cc_begin(&policy, keys.data(), keys.size(), slots.data()))
      return fail("compressed cache cannot protect selected experts");
    ++calls;
    for (std::size_t i = 0; i < keys.size(); ++i) {
      const auto expert = keys[i] % 512, slot = slots[i];
      host_map[expert] = static_cast<std::int32_t>(slot);
      if (!policy.slots[slot].pending) continue;
      const auto& l = layers[layer];
      const auto copy = [&](const Range& r, void* base) {
        if (!uploader->Copy(r.shard, r.offset + expert * r.bytes, r.bytes,
                            static_cast<char*>(base) + slot * r.bytes, error)) return false;
        read_bytes += r.bytes; return true;
      };
      if (!copy(l.gate, gate) || !copy(l.up, up) || !copy(l.down, down)) {
        (void)uploader->Finish(error);
        (void)lie_cc_finish(&policy, false);
        return fail("compressed expert upload failed");
      }
    }
    if (!uploader->Finish(error)) {
      (void)lie_cc_finish(&policy, false);
      return fail("compressed expert upload completion failed");
    }
    if (count > ids_capacity) {
      if (ids) { (void)hipFree(ids); ids = nullptr; ids_capacity = 0; }
      if (hipMalloc(&ids, count * sizeof(std::int32_t)) != hipSuccess)
        return fail("compressed cache selected ids allocation failed");
      ids_capacity = count;
    }
    for (auto& id : host_ids) id = host_map[id];
    if (hipMemcpyAsync(map, host_map, sizeof(host_map), hipMemcpyHostToDevice, stream) != hipSuccess ||
        hipMemcpyAsync(ids, host_ids.data(), count * sizeof(std::int32_t), hipMemcpyHostToDevice, stream) != hipSuccess ||
        hipStreamSynchronize(stream) != hipSuccess)
      return fail("compressed cache address publication failed");
    return true;
  }
};

struct CompressedExpertLease::State {
  CompressedExpertCache& cache;
  std::unique_lock<std::mutex> lock;
  hipStream_t stream;
  State(CompressedExpertCache& c, hipStream_t s) : cache(c), lock(c.mutex), stream(s) {}
  ~State() {
    if (cache.policy.active) {
      if (cache.failed || hipEventRecord(cache.consumed, stream) != hipSuccess) {
        (void)hipStreamSynchronize(stream);
        (void)lie_cc_finish(&cache.policy, false);
        cache.failed = true;
      } else {
        cache.last_stream = stream;
        cache.waiting = true;
      }
    }
  }
};
CompressedExpertLease::CompressedExpertLease() = default;
CompressedExpertLease::~CompressedExpertLease() = default;

std::size_t DeviceModel::resident_bytes() const noexcept {
  return bytes_ + (compressed_cache_ ?
      compressed_cache_->ids_capacity * sizeof(std::int32_t) : 0);
}

std::unique_ptr<CompressedExpertLease> DeviceModel::AcquireExperts(
    const DeviceLayer& original, const std::int32_t* selected, std::size_t count,
    hipStream_t stream, std::string* error) const {
  auto lease = std::unique_ptr<CompressedExpertLease>(new CompressedExpertLease());
  auto& cache = *compressed_cache_;
  lease->state_ = std::make_unique<CompressedExpertLease::State>(cache, stream);
  if (!cache.Prepare(original.cache_layer, selected, count, stream, error)) return nullptr;
  lease->layer = original;
  auto bind = [&](DeviceTensor& t, void* base, std::uint32_t index) {
    t.data = base; t.experts = cache.policy.capacity;
    t.compressed_view = cache.views + index;
  };
  bind(lease->layer.ffn_gate_exps, cache.gate, 0);
  bind(lease->layer.ffn_up_exps, cache.up, 1);
  bind(lease->layer.ffn_down_exps, cache.down, 2);
  lease->ids = cache.ids;
  return lease;
}
