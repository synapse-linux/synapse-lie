/* SPDX-License-Identifier: MIT */
/* Link only into the dedicated CPU HTTP fixture. Never production or GPU code. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

ssize_t __real_pread(int,void *,size_t,off_t);
ssize_t __wrap_pread(int fd,void *out,size_t bytes,off_t offset) {
    const char *directory=getenv("LIE_TEST_SSD_READ_GATE");
    if(directory) {
        char hold[4096],entered[4096];
        int a=snprintf(hold,sizeof(hold),"%s/hold",directory);
        int b=snprintf(entered,sizeof(entered),"%s/entered",directory);
        assert(a>0&&(size_t)a<sizeof(hold)&&b>0&&(size_t)b<sizeof(entered));
        if(!access(hold,F_OK)) {
            int marker=open(entered,O_WRONLY|O_CREAT|O_CLOEXEC,0600);assert(marker>=0);assert(!close(marker));
            /* The outer test releases the gate on every cleanup path. A finite
             * fallback keeps a failed fixture from holding an owned child forever. */
            unsigned waits=0;
            while(!access(hold,F_OK)) {
                if(++waits>10000){errno=ETIMEDOUT;return -1;}
                struct timespec delay={0,1000000};nanosleep(&delay,NULL);
            }
        }
    }
    return __real_pread(fd,out,bytes,offset);
}
