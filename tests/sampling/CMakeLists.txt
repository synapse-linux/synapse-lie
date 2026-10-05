# SPDX-License-Identifier: MIT
# Host-only, independently pinned controls. No HIP discovery or model forward.
cmake_minimum_required(VERSION 3.21)
project(lie_sampling_host_checks LANGUAGES C CXX)
get_filename_component(REPO "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
include("${REPO}/cmake/provider/Source.cmake")
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
include(CTest)
foreach(arm IN ITEMS reference candidate fallback)
  set(sources "${pristine}/src/core/json_constraint.cpp"
    "${pristine}/src/core/json_schema_lexeme.cpp" "${pristine}/src/core/json_schema_regex.cpp")
  if(arm STREQUAL "reference")
    list(APPEND sources "${pristine}/src/core/sampling.cpp")
  else()
    list(REMOVE_ITEM sources "${pristine}/src/core/json_constraint.cpp" "${pristine}/src/core/json_schema_lexeme.cpp" "${pristine}/src/core/json_schema_regex.cpp")
    list(APPEND sources "${variant}/src/core/json_constraint.cpp" "${REPO}/src/grammar.c" "${REPO}/src/grammar_builder.c" "${REPO}/src/schema_transform.c" "${REPO}/src/schema_values.c" "${REPO}/src/grammar_cache.c" "${REPO}/src/schema_memo.c" "${REPO}/src/schema_dispatch.c" "${REPO}/src/schema_visit.c" "${variant}/src/core/json_schema_lexeme.cpp" "${REPO}/src/grammar_number.c" "${variant}/src/core/json_schema_regex.cpp" "${REPO}/src/grammar_regex.c" "${REPO}/src/grammar_string.c" "${REPO}/src/grammar_vocabulary.c" "${REPO}/src/grammar_regex_compile.c" "${REPO}/src/grammar_regex_parse.c" "${REPO}/src/grammar_unicode.c" "${variant}/src/core/sampling.cpp" "${REPO}/src/sampling.c" "${REPO}/src/sampling_history.c" "${REPO}/src/sampling_distribution.c")
  endif()
  add_library(${arm} STATIC ${sources})
  if(NOT arm STREQUAL "reference")
    target_include_directories(${arm} PUBLIC "${variant}" "${REPO}/include")
    target_include_directories(${arm} PUBLIC "${REPO}/adapters")
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
  file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/${arm}-schema-constraint.cpp" "${schema_text}")
  add_executable(${arm}-schema-probe "${REPO}/tests/sampling/schema.cpp"
    "${CMAKE_CURRENT_BINARY_DIR}/${arm}-schema-constraint.cpp")
  target_link_libraries(${arm}-schema-probe PRIVATE ${arm})
  add_executable(${arm}-values-probe "${REPO}/tests/sampling/values.cpp"
    "${CMAKE_CURRENT_BINARY_DIR}/${arm}-schema-constraint.cpp")
  target_link_libraries(${arm}-values-probe PRIVATE ${arm})
  add_executable(${arm}-visit-probe "${REPO}/tests/sampling/visit.cpp"
    "${CMAKE_CURRENT_BINARY_DIR}/${arm}-schema-constraint.cpp")
  target_link_libraries(${arm}-visit-probe PRIVATE ${arm})
  add_executable(${arm}-dispatch-probe "${REPO}/tests/sampling/dispatch.cpp")
  target_link_libraries(${arm}-dispatch-probe PRIVATE ${arm})
  add_executable(${arm}-memo-probe "${REPO}/tests/sampling/memo.cpp")
  target_link_libraries(${arm}-memo-probe PRIVATE ${arm})
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
  add_executable(${arm}-grammar-probe "${REPO}/tests/sampling/grammar.cpp")
  target_link_libraries(${arm}-grammar-probe PRIVATE ${arm})
  add_executable(${arm}-distribution "${REPO}/tests/sampling/distribution.cpp")
  target_link_libraries(${arm}-distribution PRIVATE ${arm})
  add_executable(${arm}-vocabulary "${REPO}/tests/sampling/vocabulary.cpp")
  target_link_libraries(${arm}-vocabulary PRIVATE ${arm})
  if(NOT arm STREQUAL "reference")
    add_executable(${arm}-vocabulary-layout "${REPO}/tests/sampling/vocabulary_layout.cpp")
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
