/* SPDX-License-Identifier: MIT */
#include "lie/chat.h"
#include "lie/responses.h"
#include "lie/wire.h"
#include <assert.h>
#include <json-c/json.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void rejects(const char *body) {
    lie_chat_request r; char error[256];
    assert(!lie_chat_parse(body,strlen(body),"m",&r,error));
    assert(error[0] && !r.count);
}
static void sampling_filters(void) {
    const char *prefixes[] = {
        "{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}]}",
        "{\"model\":\"m\",\"input\":\"x\"}"
    };
    const char *invalid[] = {
        ",\"top_k\":-1", ",\"top_k\":2147483648", ",\"top_k\":18446744073709551615",
        ",\"top_k\":1.0", ",\"top_k\":true", ",\"top_k\":null", ",\"top_k\":\"5\"",
        ",\"min_p\":-0.01", ",\"min_p\":1.01", ",\"min_p\":1e999",
        ",\"min_p\":NaN", ",\"min_p\":true", ",\"min_p\":null", ",\"min_p\":\"0.05\""
    };
    const char *valid[] = {"", ",\"top_k\":5,\"min_p\":0.05",
                           ",\"top_k\":2147483647,\"min_p\":1"};
    const int32_t expected_k[] = {0, 5, INT32_MAX};
    const double expected_p[] = {0, .05, 1};
    for (size_t api = 0; api < 2; ++api) {
        bool (*parse)(const char *,size_t,const char *,lie_chat_request *,char *) =
            api ? lie_responses_parse : lie_chat_parse;
        for (size_t i = 0; i < sizeof(valid)/sizeof(*valid); ++i) {
            char body[512], error[256]; lie_chat_request r;
            snprintf(body,sizeof(body),"%.*s%s}",(int)strlen(prefixes[api])-1,prefixes[api],valid[i]);
            assert(parse(body,strlen(body),"m",&r,error));
            assert(r.generation.top_k==expected_k[i] && r.generation.min_p==expected_p[i]);
            assert(r.generation.abi_version==LIE_GENERATION_ABI);
            lie_chat_free(&r);
        }
        for (size_t i = 0; i < sizeof(invalid)/sizeof(*invalid); ++i) {
            char body[512], error[256]; lie_chat_request r;
            snprintf(body,sizeof(body),"%.*s%s}",(int)strlen(prefixes[api])-1,prefixes[api],invalid[i]);
            assert(!parse(body,strlen(body),"m",&r,error));
            assert(error[0] && !r.count);
        }
    }
}
int main(void) {
    sampling_filters();
    lie_chat_request r; char error[256];
    const char *sampling="{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"temperature\":0.7,\"top_p\":0.8,\"frequency_penalty\":-1,\"presence_penalty\":1.5,\"seed\":42}";
    lie_chat_request controls; char controls_error[256];
    assert(lie_chat_parse(sampling,strlen(sampling),"m",&controls,controls_error));
    assert(controls.generation.temperature==0.7 && controls.generation.top_p==0.8 && controls.generation.seed==42);
    assert(controls.generation.frequency_penalty==-1 && controls.generation.presence_penalty==1.5);
    lie_chat_free(&controls);
    const char *valid="{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"hello €\"}],\"temperature\":0,\"seed\":3,\"stream\":true,\"stream_options\":{\"include_usage\":true},\"chat_template_kwargs\":{\"enable_thinking\":false}}";
    assert(lie_chat_parse(valid,strlen(valid),"m",&r,error));
    assert(r.count==1 && r.max_tokens==128 && r.stream && r.include_usage);
    assert(r.messages[0].bytes==strlen("hello €") && !strcmp(r.messages[0].content,"hello €")); lie_chat_free(&r);
    rejects("{}"); rejects("{\"model\":\"m\",\"messages\":[]}"); rejects("[]"); rejects("null");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"tool\",\"content\":\"x\"}]}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"\\u0000\"}]}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":[]}]}");
    const char *empty_tools="{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"tools\":[]}";
    assert(lie_chat_parse(empty_tools,strlen(empty_tools),"m",&r,error)); lie_chat_free(&r);
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"temperature\":2.1}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"stream\":1}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"max_tokens\":4097}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"max_tokens\":0}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}]}{} ");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"\xff\"}]}");
    assert(!lie_utf8_valid("\xc0\x80",2,true)); assert(!lie_utf8_valid("\xed\xa0\x80",3,true));
    assert(!lie_utf8_valid("\xf4\x90\x80\x80",4,true)); assert(!lie_utf8_valid("x\0y",3,false));
    assert(lie_utf8_valid("x\0y",3,true)); assert(lie_utf8_valid("€🙂",7,true));
    const char raw[]="A\xf0\x9f\x99\x82\xffZ\xe2";
    const char expected[]="A🙂�Z�";
    for (size_t split=0;split<sizeof(raw);++split) {
        lie_utf8_decoder d={0}; char out[128]; size_t a=0,b=0;
        assert(lie_utf8_feed(&d,raw,split,false,out,sizeof(out),&a));
        assert(lie_utf8_feed(&d,raw+split,sizeof(raw)-1-split,true,out+a,sizeof(out)-a,&b));
        assert(a+b==strlen(expected) && !memcmp(out,expected,a+b));
    }
    lie_job_info info={.prompt_tokens=9,.output_tokens=8,.finish=LIE_FINISH_STOP,
        .timing_valid=true,.prefill_tokens=9,.prefill_calls=2,.decode_calls=9,
        .prefill_ns=2000000,.decode_ns=4000000};
    char *wire=lie_wire_completion("id","m",12,"\"\n€",5,&info);
    assert(wire); json_object *j=json_tokener_parse(wire), *v, *u;
    assert(j && json_object_object_get_ex(j,"usage",&u));
    assert(json_object_object_get_ex(u,"total_tokens",&v) && json_object_get_int(v)==17);
    assert(json_object_object_get_ex(j,"lie_timings",&u));
    assert(json_object_object_get_ex(u,"prefill_ms",&v) && json_object_get_double(v)==2.0);
    assert(json_object_object_get_ex(u,"decode_ms",&v) && json_object_get_double(v)==4.0);
    assert(json_object_object_get_ex(u,"prefill_tokens_per_second",&v) && json_object_get_double(v)==4500.0);
    assert(json_object_object_get_ex(u,"decode_tokens_per_second",&v) && json_object_get_double(v)==2000.0);
    json_object_put(j); free(wire);
    for (unsigned with_usage=0;with_usage<2;++with_usage) {
        wire=lie_wire_end("id","m",12,&info,with_usage); assert(wire);
        assert((strstr(wire,"\"choices\":[]")!=NULL)==(with_usage!=0));
        const char *timing=strstr(wire,"\"lie_timings\"");
        assert(timing && !strstr(timing+1,"\"lie_timings\"") && strstr(wire,"data: [DONE]\n\n")); free(wire);
    }
    wire=lie_wire_chunk("id","m",12,"x",1,false); assert(wire && !strstr(wire,"lie_timings")); free(wire);
    info.finish=LIE_FINISH_NONE;
    assert(!lie_wire_completion("id","m",12,"",0,&info));
    wire=lie_wire_end("id","m",12,&info,true);
    assert(wire && strstr(wire,"\"error\"") && !strstr(wire,"finish_reason") && !strstr(wire,"\"usage\"") && !strstr(wire,"lie_timings")); free(wire);
    info.finish=LIE_FINISH_BACKEND; strcpy(info.error,"test failure");
    wire=lie_wire_end("id","m",12,&info,false);
    assert(wire && strstr(wire,"test failure") && !strstr(wire,"finish_reason") && !strstr(wire,"lie_timings")); free(wire);
    info.finish=LIE_FINISH_CANCEL;
    assert(!lie_wire_completion("id","m",12,"",0,&info));
    wire=lie_wire_end("id","m",12,&info,true);
    assert(wire && strstr(wire,"cancelled") && !strstr(wire,"lie_timings") && !strstr(wire,"\"usage\"")); free(wire);
    puts("chat parser, UTF-8 boundaries and wire fixtures: PASS (not inference)"); return 0;
}
