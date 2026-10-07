/* SPDX-License-Identifier: MIT */
/* Native benchmark corpus: tokenize once, then use exact token-array prefixes.
 * Behavioral reference: antirez/ds4 ds4_bench.c; independently implemented
 * against LIE's owned executor ABI. No DS4 project code is imported. */
static bool exact_corpus(lie_model *model, const struct config *c,
                         unsigned needed, struct prompt *corpus,
                         FILE *out, lie_error *e) {
    FILE *input = fopen(c->prompt_file, "rb");
    if (!input) {
        snprintf(e->message, sizeof(e->message), "Cannot open prompt file: %s", strerror(errno));
        return false;
    }
    char *text = NULL;
    bool ok = false;
    size_t bytes = 0, count = 0;
    if (fseek(input, 0, SEEK_END) || ftell(input) <= 0 ||
        ftell(input) > LIE_CHAT_BODY_BYTES || fseek(input, 0, SEEK_SET)) {
        snprintf(e->message, sizeof(e->message), "Prompt file must contain 1..%u bytes", LIE_CHAT_BODY_BYTES);
        goto done;
    }
    text = malloc(LIE_CHAT_BODY_BYTES + 1u);
    if (!text) goto done;
    bytes = fread(text, 1, LIE_CHAT_BODY_BYTES + 1u, input);
    if (ferror(input) || !bytes || bytes > LIE_CHAT_BODY_BYTES ||
        memchr(text, 0, bytes)) {
        snprintf(e->message, sizeof(e->message), "Invalid or oversized prompt file");
        goto done;
    }
    /* A sizing pass is required by the caller-owned-buffer ABI. Neither
     * pass creates a sequence, runs a model forward or changes the text. */
    lie_status status = lie_model_tokenize(model, text, bytes, NULL, 0, &count, e);
    if (status != LIE_BUFFER_SMALL || count < needed || count > LIE_CHAT_BODY_BYTES) {
        if (status == LIE_BUFFER_SMALL || status == LIE_OK)
            snprintf(e->message, sizeof(e->message), "Prompt has %zu tokens; need at least %u", count, needed);
        goto done;
    }
    corpus->ids = malloc(count * sizeof(*corpus->ids));
    if (!corpus->ids) goto done;
    size_t actual = 0;
    status = lie_model_tokenize(model, text, bytes, corpus->ids, count, &actual, e);
    if (status != LIE_OK || actual != count) {
        if (status == LIE_OK)
            snprintf(e->message, sizeof(e->message), "Tokenizer count changed between passes");
        goto done;
    }
    corpus->n = count;
    char digest[65], ids_digest[65];
    if (!hash(text, bytes, digest) || !hash(corpus->ids, count * sizeof(*corpus->ids), ids_digest))
        goto done;
    json_object *record = event("corpus");
    str(record, "path", c->prompt_file);
    str(record, "text_sha256", digest);
    str(record, "physical_ids_sha256", ids_digest);
    str(record, "tokenization", "raw-text; exact prefix of one tokenized corpus; no chat template");
    num(record, "bytes", (int64_t)bytes);
    num(record, "tokens", (int64_t)count);
    num(record, "required_tokens", needed);
    ok = emit(out, record);
done:
    if (fclose(input)) ok = false;
    free(text);
    if (!ok) {
        free(corpus->ids);
        *corpus = (struct prompt){0};
        if (!e->message[0]) snprintf(e->message, sizeof(e->message), "Prompt preparation failed");
    }
    return ok;
}

static bool exact_grid(struct config *c) {
    if (!c->chunk) c->chunk = c->pp;
    if (c->chunk != 2048 && c->chunk != 4096 && c->chunk != 8192) return false;
    if (strcmp(c->suite, "fresh") && c->pp % c->chunk) return false;
    if (!strcmp(c->suite, "loading")) return true;
    if (!c->prompt_file || !*c->prompt_file) return false;
    if (!c->sizes_set) {
        c->size_count = 0;
        for (unsigned n = c->chunk; n <= 131072; n *= 2)
            c->sizes[c->size_count++] = n;
    }
    if (!c->depths_set) {
        c->depth_count = 0;
        for (unsigned n = c->pp; n <= 131072; n *= 2)
            c->depths[c->depth_count++] = n - c->pp;
    }
    for (unsigned i = 0; !strcmp(c->suite, "fresh") && i < c->size_count; ++i)
        if (c->sizes[i] % c->chunk || !c->sizes[i] ||
            (i && c->sizes[i] <= c->sizes[i-1])) return false;
    for (unsigned i = 0; !strcmp(c->suite, "single") && i < c->depth_count; ++i)
        if (c->depths[i] % c->chunk ||
            (i && c->depths[i] <= c->depths[i-1])) return false;
    return true;
}
