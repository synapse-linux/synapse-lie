# SPDX-License-Identifier: MIT
# Host-only, independently pinned controls. No HIP discovery or model forward.
cmake_minimum_required(VERSION 3.21)
project(lie_sampling_host_checks LANGUAGES C CXX)
get_filename_component(REPO "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
include("${REPO}/cmake/provider/Source.cmake")
lie_verify_binary64_vendor("${REPO}")
set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(LIE_SANITIZERS "ASan/UBSan host fixtures" ON)
option(LIE_SAMPLING_PERFORMANCE "Host-only cost and separate allocation probes" OFF)
add_compile_options(-Wall -Wextra -Wpedantic -UNDEBUG)
if(LIE_SANITIZERS)
  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()
set(pristine "${REPO}/.deps/gufo-f783fedb")
file(READ "${REPO}/third_party/gufo-source.json" manifest)
string(JSON original_files GET "${manifest}" files)
lie_verify_files("${pristine}" "${original_files}")
lie_variant_files(ON ON files changed)
set(variant "${CMAKE_CURRENT_BINARY_DIR}/variant")
string(JSON count LENGTH "${changed}")
math(EXPR last "${count}-1")
foreach(i RANGE 0 ${last})
  string(JSON name MEMBER "${changed}" ${i})
  string(JSON content GET "${changed}" "${name}")
  get_filename_component(parent "${variant}/${name}" DIRECTORY)
  file(MAKE_DIRECTORY "${parent}")
  file(WRITE "${variant}/${name}" "${content}")
endforeach()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/variant-files.json" "${files}\n")
find_package(ICU REQUIRED COMPONENTS uc i18n)
find_package(Threads REQUIRED)
find_package(OpenSSL REQUIRED COMPONENTS Crypto)
include(CTest)
foreach(arm IN ITEMS reference candidate fallback)
  set(sources "${pristine}/src/core/json_constraint.cpp"
    "${pristine}/src/core/json_schema_lexeme.cpp" "${pristine}/src/core/json_schema_regex.cpp")
  if(arm STREQUAL "reference")
    list(APPEND sources "${pristine}/src/core/sampling.cpp")
  else()
    list(REMOVE_ITEM sources "${pristine}/src/core/json_constraint.cpp" "${pristine}/src/core/json_schema_lexeme.cpp" "${pristine}/src/core/json_schema_regex.cpp")
    list(APPEND sources "${variant}/src/core/json_constraint.cpp" "${REPO}/src/grammar.c" "${REPO}/src/grammar_builder.c" "${REPO}/src/schema_transform.c" "${REPO}/src/schema_values.c" "${REPO}/src/grammar_cache.c" "${REPO}/src/ordered_cache.c" "${REPO}/src/grammar_composition.c" "${REPO}/src/binary64.c" "${REPO}/src/json_parse.c" "${REPO}/src/json_value.c" "${REPO}/src/json_store.c" "${REPO}/src/schema_memo.c" "${REPO}/src/schema_dispatch.c" "${REPO}/src/schema_visit.c" "${REPO}/src/schema_root.c" "${REPO}/src/schema_compile.c" "${REPO}/src/schema_compiler.c" "${REPO}/src/schema_arena.c" "${REPO}/src/schema_string.c" "${REPO}/src/schema_frontend.c" "${REPO}/src/schema_body.c" "${REPO}/src/schema_number.c" "${REPO}/src/schema_integer.c" "${REPO}/src/schema_format.c" "${variant}/src/core/json_schema_lexeme.cpp" "${REPO}/src/grammar_number.c" "${variant}/src/core/json_schema_regex.cpp" "${REPO}/src/grammar_regex.c" "${REPO}/src/grammar_string.c" "${REPO}/src/grammar_lexeme.c" "${REPO}/src/grammar_vocabulary.c" "${REPO}/src/grammar_regex_compile.c" "${REPO}/src/grammar_regex_parse.c" "${REPO}/src/grammar_unicode.c" "${variant}/src/core/sampling.cpp" "${REPO}/src/sampling.c" "${REPO}/src/sampling_history.c" "${REPO}/src/sampling_storage.c" "${REPO}/src/sampling_distribution.c")
  endif()
  add_library(${arm} STATIC ${sources})
  if(NOT arm STREQUAL "reference")
    target_include_directories(${arm} PUBLIC "${variant}" "${REPO}/include")
    target_include_directories(${arm} PUBLIC "${REPO}/adapters" PRIVATE "${REPO}/third_party/ryu")
  endif()
  target_include_directories(${arm} PUBLIC "${pristine}")
  if(arm STREQUAL "candidate")
    target_compile_definitions(${arm} PUBLIC LIE_C17_SAMPLING=1)
  else()
    target_compile_definitions(${arm} PUBLIC LIE_C17_SAMPLING=0)
  endif()
  if(NOT arm STREQUAL "reference")
    target_compile_definitions(${arm} PUBLIC LIE_TEST_BIAS=1)
  endif()
  target_link_libraries(${arm} PUBLIC ICU::uc ICU::i18n Threads::Threads m)
  if(NOT arm STREQUAL "reference")
    add_executable(${arm}-sampling-observer "${REPO}/tests/sampling/observer.cpp")
    target_link_libraries(${arm}-sampling-observer PRIVATE ${arm})
    add_test(NAME ${arm}-sampling-observer COMMAND ${arm}-sampling-observer)
    set_tests_properties(${arm}-sampling-observer PROPERTIES TIMEOUT 30)
  endif()
  # Test-only copy exposes the local compiler helper without editing upstream
  # or production visibility. Linking this object supplies constraint symbols;
  # the original constraint object in the static archive is not extracted.
  if(arm STREQUAL "reference")
    set(schema_source "${pristine}/src/core/json_constraint.cpp")
  else()
    set(schema_source "${variant}/src/core/json_constraint.cpp")
  endif()
  file(READ "${schema_source}" schema_text)
  set(schema_marker "private:\n  static std::uint32_t Byte")
  string(FIND "${schema_text}" "${schema_marker}" schema_marker_at)
  if(schema_marker_at LESS 0)
    message(FATAL_ERROR "Schema probe exposure marker missing")
  endif()
  string(LENGTH "${schema_marker}" schema_marker_bytes)
  math(EXPR schema_marker_after "${schema_marker_at}+${schema_marker_bytes}")
  string(SUBSTRING "${schema_text}" ${schema_marker_after} -1 schema_tail)
  string(FIND "${schema_tail}" "${schema_marker}" schema_duplicate)
  if(NOT schema_duplicate EQUAL -1)
    message(FATAL_ERROR "Schema probe exposure marker ambiguous")
  endif()
  string(REPLACE "private:\n  static std::uint32_t Byte" "public:\n  static std::uint32_t Byte" schema_text "${schema_text}")
  string(APPEND schema_text "\nnamespace gufo::sampling {\njson::Value LieSchemaConjoinProbe(const json::Value &root,const json::Value &l,const json::Value &r,unsigned depth) { return JsonConstraintCompiler(root,false).Conjoin(l,r,depth); }\nbool LieSchemaEqualProbe(const json::Value &a,const json::Value &b) { return JsonConstraintCompiler::EqualValue(a,b); }\nconst json::Value *LieSchemaReferenceProbe(const json::Value &root,const json::Value &ref) { return JsonConstraintCompiler(root,false).Reference(ref); }\nvoid LieSchemaKeysProbe(const json::Value &n) { JsonConstraintCompiler(n,false).Keys(n); }\n}\n")
  string(APPEND schema_text "\nnamespace gufo::sampling {\nstd::string LieSchemaValueProbe(const json::Value &root,const json::Value &schema,const json::Value &value,size_t depth) { auto normalized=JsonConstraintCompiler(root,false).ValueFor(schema,value,depth); return normalized ? std::string(\"MATCH \")+normalized->dump() : std::string(\"EXCLUDED\"); }\nbool LieSchemaTypeProbe(const json::Value &value,std::string_view type) { return JsonConstraintCompiler::MatchesType(value,type); }\n}\n")
  string(APPEND schema_text "\nnamespace gufo::sampling {\nstd::shared_ptr<const JsonConstraint> LieSchemaVisitProbe(const json::Value &root,const json::Value &node,const std::vector<size_t> &depths,std::vector<uint32_t> &ids) { JsonConstraintCompiler compiler(root,false); for (auto depth : depths) ids.push_back(compiler.Visit(node,depth)); return compiler.Compile(false); }\n}\n")
  string(APPEND schema_text "\nnamespace gufo::sampling {\nuint32_t LieSchemaIntegerRuleProbe(const json::Value &schema) { return JsonConstraintCompiler(schema,false).Integer(schema); }\n}\n")
  file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/${arm}-schema-constraint.cpp" "${schema_text}")
  # Compile the identical test-only exposure once per coherent arm. Its
  # consumers retain the same definitions and source; no fixture is skipped.
  add_library(${arm}-schema-exposure OBJECT "${CMAKE_CURRENT_BINARY_DIR}/${arm}-schema-constraint.cpp")
  target_link_libraries(${arm}-schema-exposure PRIVATE ${arm})
  add_executable(${arm}-integer-probe "${REPO}/tests/sampling/integer.cpp"
    $<TARGET_OBJECTS:${arm}-schema-exposure>)
  target_link_libraries(${arm}-integer-probe PRIVATE ${arm})
  add_executable(${arm}-schema-probe "${REPO}/tests/sampling/schema.cpp"
    $<TARGET_OBJECTS:${arm}-schema-exposure>)
  target_link_libraries(${arm}-schema-probe PRIVATE ${arm})
  add_executable(${arm}-values-probe "${REPO}/tests/sampling/values.cpp"
    $<TARGET_OBJECTS:${arm}-schema-exposure>)
  target_link_libraries(${arm}-values-probe PRIVATE ${arm})
  add_executable(${arm}-root-probe "${REPO}/tests/sampling/root.cpp")
  target_link_libraries(${arm}-root-probe PRIVATE ${arm})
  add_executable(${arm}-body-probe "${REPO}/tests/sampling/body.cpp")
  target_link_libraries(${arm}-body-probe PRIVATE ${arm})
  add_executable(${arm}-visit-probe "${REPO}/tests/sampling/visit.cpp"
    $<TARGET_OBJECTS:${arm}-schema-exposure>)
  target_link_libraries(${arm}-visit-probe PRIVATE ${arm})
  add_executable(${arm}-dispatch-probe "${REPO}/tests/sampling/dispatch.cpp")
  target_link_libraries(${arm}-dispatch-probe PRIVATE ${arm})
  add_executable(${arm}-memo-probe "${REPO}/tests/sampling/memo.cpp")
  target_link_libraries(${arm}-memo-probe PRIVATE ${arm})
  add_executable(${arm}-binary64-probe "${REPO}/tests/sampling/binary64.cpp")
  target_link_libraries(${arm}-binary64-probe PRIVATE ${arm})
  add_executable(${arm}-json-parser-probe "${REPO}/tests/sampling/json_parser.cpp")
  target_link_libraries(${arm}-json-parser-probe PRIVATE ${arm})
  add_executable(${arm}-json-value-probe "${REPO}/tests/sampling/json_value.cpp")
  target_link_libraries(${arm}-json-value-probe PRIVATE ${arm})
  add_executable(${arm}-json-value-readers "${REPO}/tests/sampling/json_value_threads.cpp")
  target_link_libraries(${arm}-json-value-readers PRIVATE ${arm})
  add_test(NAME ${arm}-json-value-const-readers COMMAND ${arm}-json-value-readers)
  set_tests_properties(${arm}-json-value-const-readers PROPERTIES TIMEOUT 30)
  add_executable(${arm}-composition-probe "${REPO}/tests/sampling/composition.cpp")
  target_link_libraries(${arm}-composition-probe PRIVATE ${arm})
  add_executable(${arm}-composition-cache-probe "${REPO}/tests/sampling/composition_cache.cpp")
  target_link_libraries(${arm}-composition-cache-probe PRIVATE ${arm})
  add_executable(${arm}-cache-probe "${REPO}/tests/sampling/cache.cpp")
  target_link_libraries(${arm}-cache-probe PRIVATE ${arm})
  foreach(test IN ITEMS logit grammar mtp)
    if(test STREQUAL "logit")
      set(test_source tests/cli/logit_sampler_test.cpp)
    elseif(test STREQUAL "grammar")
      set(test_source tests/core/json_constraint_test.cpp)
    else()
      set(test_source tests/models/qwen38_flash_next/mtp_sampling_test.cpp)
    endif()
    add_executable(${arm}-${test} "${pristine}/${test_source}")
    target_link_libraries(${arm}-${test} PRIVATE ${arm})
    add_test(NAME ${arm}-${test} COMMAND ${arm}-${test})
    set_tests_properties(${arm}-${test} PROPERTIES TIMEOUT 90)
  endforeach()
  add_executable(${arm}-probe "${REPO}/tests/sampling/probe.cpp")
  target_link_libraries(${arm}-probe PRIVATE ${arm})
  add_executable(${arm}-sampling-replay "${REPO}/tests/sampling/replay.cpp")
  target_link_libraries(${arm}-sampling-replay PRIVATE ${arm} OpenSSL::Crypto)
  add_executable(${arm}-history "${REPO}/tests/sampling/history.cpp")
  target_link_libraries(${arm}-history PRIVATE ${arm})
  add_executable(${arm}-grammar-vocabulary "${REPO}/tests/sampling/grammar_vocabulary.cpp")
  target_link_libraries(${arm}-grammar-vocabulary PRIVATE ${arm})
  add_executable(${arm}-unicode-probe "${REPO}/tests/sampling/unicode.cpp")
  target_link_libraries(${arm}-unicode-probe PRIVATE ${arm})
  add_executable(${arm}-compiler-probe "${REPO}/tests/sampling/compiler.cpp")
  target_link_libraries(${arm}-compiler-probe PRIVATE ${arm})
  add_executable(${arm}-snapshot-probe "${REPO}/tests/sampling/snapshot.cpp")
  target_link_libraries(${arm}-snapshot-probe PRIVATE ${arm})
  add_executable(${arm}-request-state "${REPO}/tests/sampling/request_state.cpp")
  target_link_libraries(${arm}-request-state PRIVATE ${arm})
  if(arm STREQUAL "candidate")
    add_test(NAME c17-request-state-ownership COMMAND candidate-request-state ownership)
    set_tests_properties(c17-request-state-ownership PROPERTIES TIMEOUT 30)
  endif()
  if(NOT arm STREQUAL "reference")
    add_test(NAME ${arm}-snapshot-staging-refusals COMMAND ${arm}-snapshot-probe faults)
    set_tests_properties(${arm}-snapshot-staging-refusals PROPERTIES TIMEOUT 30)
  endif()
  add_executable(${arm}-uset-probe "${REPO}/tests/sampling/uset.cpp")
  target_link_libraries(${arm}-uset-probe PRIVATE ${arm})
  add_executable(${arm}-parser-probe "${REPO}/tests/sampling/parser.cpp")
  target_link_libraries(${arm}-parser-probe PRIVATE ${arm})
  add_executable(${arm}-number-probe "${REPO}/tests/sampling/number.cpp")
  target_link_libraries(${arm}-number-probe PRIVATE ${arm})
  add_executable(${arm}-number-control-probe "${REPO}/tests/sampling/number_control.cpp")
  target_link_libraries(${arm}-number-control-probe PRIVATE ${arm})
  add_executable(${arm}-format-probe "${REPO}/tests/sampling/format.cpp"
    $<TARGET_OBJECTS:${arm}-schema-exposure>)
  target_link_libraries(${arm}-format-probe PRIVATE ${arm})
  add_executable(${arm}-grammar-probe "${REPO}/tests/sampling/grammar.cpp")
  target_link_libraries(${arm}-grammar-probe PRIVATE ${arm})
  add_executable(${arm}-distribution "${REPO}/tests/sampling/distribution.cpp")
  target_link_libraries(${arm}-distribution PRIVATE ${arm})
  add_executable(${arm}-vocabulary "${REPO}/tests/sampling/vocabulary.cpp")
  target_link_libraries(${arm}-vocabulary PRIVATE ${arm})
  if(NOT arm STREQUAL "reference")
    add_executable(${arm}-vocabulary-layout "${REPO}/tests/sampling/vocabulary_layout.cpp"
      "${REPO}/tests/sampling/vocabulary_header_view.cpp")
    target_link_libraries(${arm}-vocabulary-layout PRIVATE ${arm})
    if(arm STREQUAL "candidate")
      target_compile_definitions(${arm}-vocabulary-layout PRIVATE LIE_TEST_HEADER_VIEW=0)
    else()
      target_compile_definitions(${arm}-vocabulary-layout PRIVATE LIE_TEST_HEADER_VIEW=1)
    endif()
    add_test(NAME ${arm}-vocabulary-layout COMMAND ${arm}-vocabulary-layout)
    set_tests_properties(${arm}-vocabulary-layout PROPERTIES TIMEOUT 30)
  endif()
  if(LIE_SAMPLING_PERFORMANCE)
    add_executable(${arm}-cost "${CMAKE_CURRENT_LIST_DIR}/performance.cpp")
    target_compile_definitions(${arm}-cost PRIVATE LIE_SAMPLING_ARM="${arm}")
    target_link_libraries(${arm}-cost PRIVATE ${arm})
    add_executable(${arm}-allocation "${CMAKE_CURRENT_LIST_DIR}/performance.cpp"
      "${CMAKE_CURRENT_LIST_DIR}/allocation_counter.cpp")
    target_compile_definitions(${arm}-allocation PRIVATE
      LIE_SAMPLING_ARM="${arm}" LIE_TRACK_ALLOCATIONS=1)
    target_link_libraries(${arm}-allocation PRIVATE ${arm})
    add_test(NAME ${arm}-allocation-retirement
      COMMAND ${arm}-allocation --quick)
    set_tests_properties(${arm}-allocation-retirement PROPERTIES TIMEOUT 90)
  endif()
endforeach()
set(LIE_CAPTURE_FIXTURE "" CACHE FILEPATH "Explicit native NOT-INFERENCE capture fixture for offline replay checks")
set(LIE_CAPTURE_FILE_FIXTURE "" CACHE FILEPATH "Explicit owned capture filesystem fixture")
if(LIE_CAPTURE_FIXTURE)
  if(NOT EXISTS "${LIE_CAPTURE_FIXTURE}" OR NOT EXISTS "${LIE_CAPTURE_FILE_FIXTURE}")
    message(FATAL_ERROR "Native capture and filesystem fixture executables must exist")
  endif()
  string(RANDOM LENGTH 12 ALPHABET 0123456789abcdef replay_run)
  foreach(protocol IN ITEMS replay tools_replay mtp_replay)
    add_test(NAME ${protocol}-native-capture-contract COMMAND "${CMAKE_COMMAND}"
      "-DCAPTURE=${LIE_CAPTURE_FIXTURE}" "-DFILE_FIXTURE=${LIE_CAPTURE_FILE_FIXTURE}"
      "-DREFERENCE=$<TARGET_FILE:reference-sampling-replay>"
      "-DCANDIDATE=$<TARGET_FILE:candidate-sampling-replay>"
      "-DFALLBACK=$<TARGET_FILE:fallback-sampling-replay>"
      "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/${protocol}-capture-${replay_run}"
      -P "${CMAKE_CURRENT_LIST_DIR}/${protocol}_contract.cmake")
    set_tests_properties(${protocol}-native-capture-contract PROPERTIES TIMEOUT 180)
  endforeach()
endif()
add_executable(candidate-number-allocation
  "${REPO}/tests/sampling/number_allocation.cpp"
  "${REPO}/tests/sampling/allocation_counter.cpp")
target_link_libraries(candidate-number-allocation PRIVATE candidate)
add_test(NAME numeric-bridge-allocation-retirement COMMAND candidate-number-allocation)
set_tests_properties(numeric-bridge-allocation-retirement PROPERTIES TIMEOUT 30)
add_test(NAME schema-transform-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-schema-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-schema-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-schema-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/schema-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-transform-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-values-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-values-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-values-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-values-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/values-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-values-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-dispatch-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-dispatch-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-dispatch-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-dispatch-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/dispatch-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-dispatch-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-root-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-root-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-root-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-root-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/root-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-root-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-body-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-body-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-body-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-body-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/body-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-body-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-visit-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-visit-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-visit-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-visit-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/visit-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-visit-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-reference-memo-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-memo-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-memo-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-memo-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/memo-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-reference-memo-parity PROPERTIES TIMEOUT 120)
add_test(NAME compiled-schema-cache-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-cache-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-cache-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-cache-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/cache-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(compiled-schema-cache-reference-parity PROPERTIES TIMEOUT 120)
add_executable(candidate-controls "${REPO}/tests/test_gufo_sampling.cpp")
target_link_libraries(candidate-controls PRIVATE candidate)
add_test(NAME candidate-controls COMMAND candidate-controls)
add_executable(fallback-controls "${REPO}/tests/test_gufo_sampling.cpp")
target_link_libraries(fallback-controls PRIVATE fallback)
add_test(NAME fallback-controls COMMAND fallback-controls)
add_test(NAME complete-sampling-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/parity" -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(complete-sampling-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME complete-biased-sampling-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:fallback-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-probe>"
  "-DARGUMENT=--bias" "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/biased-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(complete-biased-sampling-parity PROPERTIES TIMEOUT 120)
add_test(NAME full-vocabulary-sampling-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-vocabulary>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-vocabulary>"
  "-DFALLBACK=$<TARGET_FILE:fallback-vocabulary>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/vocabulary-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(full-vocabulary-sampling-parity PROPERTIES TIMEOUT 120)
add_test(NAME sampling-history-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-history>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-history>"
  "-DFALLBACK=$<TARGET_FILE:fallback-history>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/history-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(sampling-history-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME compact-distribution-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-distribution>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-distribution>"
  "-DFALLBACK=$<TARGET_FILE:fallback-distribution>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/distribution-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(compact-distribution-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME byte-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-grammar-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-grammar-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-grammar-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/grammar-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(byte-grammar-reference-parity PROPERTIES TIMEOUT 120)

add_test(NAME number-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-number-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-number-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-number-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/number-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(number-grammar-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-number-control-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-number-control-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-number-control-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-number-control-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/number-control-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-number-control-reference-parity PROPERTIES TIMEOUT 120)
add_test(NAME schema-format-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-format-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-format-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-format-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/format-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-format-reference-parity PROPERTIES TIMEOUT 180)

add_test(NAME unicode-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-unicode-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-unicode-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-unicode-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/unicode-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(unicode-grammar-reference-parity PROPERTIES TIMEOUT 120)

add_test(NAME vocabulary-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-grammar-vocabulary>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-grammar-vocabulary>"
  "-DFALLBACK=$<TARGET_FILE:fallback-grammar-vocabulary>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/grammar-vocabulary-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(vocabulary-grammar-reference-parity PROPERTIES TIMEOUT 180)

add_test(NAME compiler-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-compiler-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-compiler-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-compiler-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/compiler-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(compiler-grammar-reference-parity PROPERTIES TIMEOUT 600)

add_test(NAME parser-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-parser-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-parser-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-parser-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/parser-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(parser-grammar-reference-parity PROPERTIES TIMEOUT 300)

add_test(NAME uset-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-uset-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-uset-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-uset-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/uset-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(uset-grammar-reference-parity PROPERTIES TIMEOUT 300)

add_test(NAME snapshot-grammar-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-snapshot-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-snapshot-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-snapshot-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/snapshot-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(snapshot-grammar-reference-parity PROPERTIES TIMEOUT 180)

add_test(NAME request-state-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-request-state>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-request-state>"
  "-DFALLBACK=$<TARGET_FILE:fallback-request-state>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/request-state-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(request-state-reference-parity PROPERTIES TIMEOUT 180)

add_test(NAME composition-cache-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-composition-cache-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-composition-cache-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-composition-cache-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/composition-cache-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(composition-cache-reference-parity PROPERTIES TIMEOUT 180)

add_test(NAME composition-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-composition-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-composition-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-composition-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/composition-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(composition-reference-parity PROPERTIES TIMEOUT 180)

add_test(NAME binary64-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-binary64-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-binary64-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-binary64-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/binary64-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(binary64-reference-parity PROPERTIES TIMEOUT 300)
add_test(NAME json-parser-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-json-parser-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-json-parser-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-json-parser-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/json-parser-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(json-parser-reference-parity PROPERTIES TIMEOUT 180)
find_package(PkgConfig REQUIRED)
pkg_check_modules(BINARY64_MPFR REQUIRED IMPORTED_TARGET mpfr)
add_executable(candidate-binary64-oracle "${REPO}/tests/sampling/binary64_oracle.cpp")
target_link_libraries(candidate-binary64-oracle PRIVATE candidate PkgConfig::BINARY64_MPFR)
target_link_options(candidate-binary64-oracle PRIVATE
  -Wl,--wrap=malloc -Wl,--wrap=calloc -Wl,--wrap=realloc -Wl,--wrap=free)
add_test(NAME binary64-independent-MPFR-oracle COMMAND candidate-binary64-oracle)
set_tests_properties(binary64-independent-MPFR-oracle PROPERTIES TIMEOUT 300)

add_test(NAME json-value-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-json-value-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-json-value-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-json-value-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/json-value-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(json-value-reference-parity PROPERTIES TIMEOUT 120)

add_executable(candidate-json-value-faults "${REPO}/tests/sampling/json_value_faults.cpp")
target_link_libraries(candidate-json-value-faults PRIVATE candidate)
add_test(NAME candidate-json-value-projection-refusals COMMAND candidate-json-value-faults)
set_tests_properties(candidate-json-value-projection-refusals PROPERTIES TIMEOUT 30)

# Finished C tables must not be projected into duplicate C++ containers.
add_executable(candidate-grammar-storage "${REPO}/tests/sampling/grammar_storage.cpp"
  "${REPO}/tests/sampling/allocation_counter.cpp")
target_link_libraries(candidate-grammar-storage PRIVATE candidate)
add_test(NAME candidate-grammar-storage-ownership COMMAND candidate-grammar-storage)
set_tests_properties(candidate-grammar-storage-ownership PROPERTIES TIMEOUT 60)

# C17 per-compilation and transformer root lifetimes, exact ownership transfer.
add_executable(candidate-schema-store "${REPO}/tests/sampling/schema_store.cpp")
target_link_libraries(candidate-schema-store PRIVATE candidate)
add_test(NAME candidate-schema-store-ownership COMMAND candidate-schema-store)
set_tests_properties(candidate-schema-store-ownership PROPERTIES TIMEOUT 60)
add_executable(candidate-json-store-core "${REPO}/tests/test_json_store.c")
target_link_libraries(candidate-json-store-core PRIVATE candidate)
add_test(NAME candidate-json-store-core-ownership COMMAND candidate-json-store-core)
set_tests_properties(candidate-json-store-core-ownership PROPERTIES TIMEOUT 60)

# Native publication/refusals and typed prompt sharing; no model forward.
add_executable(candidate-schema-compile-core "${REPO}/tests/test_schema_compile.c")
add_test(NAME schema-integer-reference-parity COMMAND "${CMAKE_COMMAND}"
  "-DREFERENCE=$<TARGET_FILE:reference-integer-probe>"
  "-DCANDIDATE=$<TARGET_FILE:candidate-integer-probe>"
  "-DFALLBACK=$<TARGET_FILE:fallback-integer-probe>"
  "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/integer-parity"
  -P "${CMAKE_CURRENT_LIST_DIR}/compare.cmake")
set_tests_properties(schema-integer-reference-parity PROPERTIES TIMEOUT 180)
add_executable(candidate-schema-integer-core "${REPO}/tests/test_schema_integer.c")
target_link_libraries(candidate-schema-integer-core PRIVATE candidate)
add_test(NAME candidate-schema-integer-core-contract COMMAND candidate-schema-integer-core)
set_tests_properties(candidate-schema-integer-core-contract PROPERTIES TIMEOUT 60)
target_link_libraries(candidate-schema-compile-core PRIVATE candidate)
add_test(NAME candidate-schema-compile-core-publication COMMAND candidate-schema-compile-core)
set_tests_properties(candidate-schema-compile-core-publication PROPERTIES TIMEOUT 60)
add_executable(candidate-schema-compiler-core "${REPO}/tests/test_schema_compiler.c")
target_link_libraries(candidate-schema-compiler-core PRIVATE candidate)
add_test(NAME candidate-schema-compiler-core-lifecycle COMMAND candidate-schema-compiler-core)
set_tests_properties(candidate-schema-compiler-core-lifecycle PROPERTIES TIMEOUT 60)
add_executable(candidate-schema-arena-core "${REPO}/tests/test_schema_arena.c")
add_executable(candidate-schema-string-core "${REPO}/tests/test_schema_string.c")
add_executable(candidate-schema-frontend-core "${REPO}/tests/test_schema_frontend.c")
target_link_libraries(candidate-schema-frontend-core PRIVATE candidate)
add_test(NAME candidate-schema-native-frontend COMMAND candidate-schema-frontend-core)
set_tests_properties(candidate-schema-native-frontend PROPERTIES TIMEOUT 180)
add_executable(candidate-schema-frontend "${REPO}/tests/sampling/schema_frontend.cpp"
  $<TARGET_OBJECTS:candidate-schema-exposure>)
target_link_libraries(candidate-schema-frontend PRIVATE candidate)
add_test(NAME candidate-schema-native-frontend-projections COMMAND candidate-schema-frontend)
add_executable(candidate-sampling-storage-core "${REPO}/tests/test_sampling_storage.c")
target_link_libraries(candidate-sampling-storage-core PRIVATE candidate)
add_test(NAME candidate-sampling-storage-ownership COMMAND candidate-sampling-storage-core)
set_tests_properties(candidate-sampling-storage-ownership PROPERTIES TIMEOUT 30)
add_executable(candidate-sampling-storage "${REPO}/tests/sampling/sampling_storage.cpp"
  "${REPO}/tests/sampling/allocation_counter.cpp")
target_link_libraries(candidate-sampling-storage PRIVATE candidate)
add_test(NAME candidate-sampling-storage-projections COMMAND candidate-sampling-storage)
set_tests_properties(candidate-sampling-storage-projections PROPERTIES TIMEOUT 30)
set_tests_properties(candidate-schema-native-frontend-projections PROPERTIES TIMEOUT 180)
target_link_libraries(candidate-schema-string-core PRIVATE candidate)
add_test(NAME candidate-schema-string-core-construction COMMAND candidate-schema-string-core)
set_tests_properties(candidate-schema-string-core-construction PROPERTIES TIMEOUT 120)
add_executable(candidate-schema-string "${REPO}/tests/sampling/schema_string.cpp")
target_link_libraries(candidate-schema-string PRIVATE candidate)
add_test(NAME candidate-schema-string-typed-projections COMMAND candidate-schema-string)
set_tests_properties(candidate-schema-string-typed-projections PROPERTIES TIMEOUT 120)
target_link_libraries(candidate-schema-arena-core PRIVATE candidate)
add_test(NAME candidate-schema-arena-core-construction COMMAND candidate-schema-arena-core)
set_tests_properties(candidate-schema-arena-core-construction PROPERTIES TIMEOUT 60)
add_executable(candidate-schema-arena "${REPO}/tests/sampling/schema_arena.cpp")
target_link_libraries(candidate-schema-arena PRIVATE candidate)
add_test(NAME candidate-schema-arena-typed-projections COMMAND candidate-schema-arena)
set_tests_properties(candidate-schema-arena-typed-projections PROPERTIES TIMEOUT 60)
add_executable(candidate-schema-compile "${REPO}/tests/sampling/schema_compile.cpp")
target_link_libraries(candidate-schema-compile PRIVATE candidate)
add_test(NAME candidate-schema-compile-prompt-ownership COMMAND candidate-schema-compile)
set_tests_properties(candidate-schema-compile-prompt-ownership PROPERTIES TIMEOUT 60)
