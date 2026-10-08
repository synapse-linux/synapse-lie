/* SPDX-License-Identifier: MIT */
/* Reproduce tests/q2_model.cpp SizedPrompt with the owned tokenizer ABI.
 * Only exact counts are admitted; all preparation is outside GPU timers. */
static bool exact_counting(lie_model *model, unsigned target,
                           struct prompt *prompt, FILE *out, lie_error *e) {
    static const char prefix[] = "Ignore this padding data:\n";
    static const char suffix[] =
        "\nCount from 1 to 200, separated by commas. Output only the numbers.";
    size_t lo = 0, hi = (size_t)target * 2;
    size_t capacity = sizeof(prefix)-1 + hi*2 + sizeof(suffix);
    char *text = malloc(capacity);
    int32_t *ids = NULL;
    bool ok = false;
    if (!text) goto done;
    while (lo <= hi) {
        size_t repeats = lo + (hi-lo)/2;
        size_t bytes = sizeof(prefix)-1 + repeats*2 + sizeof(suffix)-1;
        memcpy(text, prefix, sizeof(prefix)-1);
        for (size_t i=0; i<repeats; ++i) {
            text[sizeof(prefix)-1+i*2] = 'x';
            text[sizeof(prefix)+i*2] = ' ';
        }
        memcpy(text+sizeof(prefix)-1+repeats*2, suffix, sizeof(suffix));
        lie_chat_message message = {LIE_CHAT_USER, text, bytes};
        size_t count = 0;
        lie_status status = lie_model_chat_tokens(model, &message, 1, NULL, 0, &count, e);
        if (status != LIE_BUFFER_SMALL) goto done;
        if (count == target) {
            ids = malloc(count*sizeof(*ids));
            if (!ids) goto done;
            size_t actual = 0;
            status = lie_model_chat_tokens(model, &message, 1, ids, count, &actual, e);
            if (status != LIE_OK || actual != target) goto done;
            char text_digest[65], ids_digest[65];
            if (!hash(text, bytes, text_digest) || !hash(ids, count*sizeof(*ids), ids_digest)) goto done;
            if (target == 2048 && !lie_backend_is_synthetic() &&
                strcmp(ids_digest, "75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35")) {
                snprintf(e->message, sizeof(e->message), "Counting input differs from the retained 2048-token reference");
                goto done;
            }
            json_object *record = event("prompt_source");
            str(record, "preset", "q2-counting");
            str(record, "text_sha256", text_digest);
            str(record, "physical_ids_sha256", ids_digest);
            num(record, "tokens", target);
            num(record, "padding_repetitions", (int64_t)repeats);
            str(record, "tokenization", "original counting text; model chat template; thinking disabled; exact count required");
            if (!emit(out, record)) goto done;
            free(prompt->ids);
            *prompt = (struct prompt){ids, count};
            ids = NULL;
            ok = true;
            break;
        }
        if (count < target) lo = repeats+1;
        else {
            if (!repeats) break;
            hi = repeats-1;
        }
    }
done:
    free(ids);
    free(text);
    if (!ok && !e->message[0])
        snprintf(e->message, sizeof(e->message), "Cannot construct exact counting prompt");
    return ok;
}
