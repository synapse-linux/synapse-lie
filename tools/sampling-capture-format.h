/* SPDX-License-Identifier: MIT */
/* Frozen diagnostic workload/data format; not an engine API or tool callback. */
#ifndef LIE_SAMPLING_CAPTURE_FORMAT_H
#define LIE_SAMPLING_CAPTURE_FORMAT_H
#define LIE_CAPTURE_TOOL_NAME "describe_stack"
#define LIE_CAPTURE_TOOL_PARAMETERS \
    "{\"type\":\"object\",\"properties\":{\"order\":{\"type\":\"string\",\"enum\":[\"LIFO\",\"FIFO\"]}," \
    "\"size\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":9}}," \
    "\"required\":[\"order\",\"size\"],\"additionalProperties\":false}"
#define LIE_CAPTURE_TOOL_DEFINITION \
    "{\"type\":\"function\",\"function\":{\"name\":\"describe_stack\",\"strict\":true," \
    "\"parameters\":" LIE_CAPTURE_TOOL_PARAMETERS "}}"
#define LIE_CAPTURE_TOOL_PROMPT \
    "Call describe_stack once with order LIFO and size 3. Return the function call only."
#define LIE_CAPTURE_VOCAB_MAGIC "LIEVOC01"
#define LIE_CAPTURE_VOCAB_FILE "vocabulary.bin"
#define LIE_CAPTURE_VOCAB_BYTES_MAX (64u * 1024u * 1024u)
#define LIE_CAPTURE_PIECE_BYTES_MAX 32768u
#define LIE_CAPTURE_OUTPUT_BYTES_MAX 32768u
#endif
