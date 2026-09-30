/* SPDX-License-Identifier: MIT */
#include "lie/chat.h"
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
int main(void) {
    lie_chat_request r; char error[256];
    const char *valid="{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"hello €\"}],\"temperature\":0,\"seed\":3,\"stream\":true,\"stream_options\":{\"include_usage\":true},\"chat_template_kwargs\":{\"enable_thinking\":false}}";
    assert(lie_chat_parse(valid,strlen(valid),"m",&r,error));
    assert(r.count==1 && r.max_tokens==128 && r.stream && r.include_usage);
    assert(r.messages[0].bytes==strlen("hello €") && !strcmp(r.messages[0].content,"hello €")); lie_chat_free(&r);
    rejects("{}"); rejects("{\"model\":\"m\",\"messages\":[]}"); rejects("[]"); rejects("null");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"tool\",\"content\":\"x\"}]}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"\\u0000\"}]}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":[]}]}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"tools\":[]}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"temperature\":0.1}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"stream\":1}");
    rejects("{\"model\":\"m\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"max_tokens\":513}");
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
