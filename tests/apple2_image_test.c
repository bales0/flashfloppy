/* Actual native Apple codecs and dispatcher, against files held in RAM.
 * Independent expected streams/CRCs come from the adapted upstream vectors.
 * This does not model FAT fragmentation or electrical interrupt timing.
 */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
#include <ctype.h>
#include <endian.h>
#include <sys/types.h>
typedef unsigned int bool_t;
typedef unsigned int UINT;
typedef uint8_t BYTE;
typedef uint32_t DWORD;
typedef uint32_t FSIZE_t;
typedef int FRESULT;
typedef struct {uint8_t *data;uint32_t size,pos;void *dir_ptr;DWORD *cltbl;} FIL;
typedef struct {char fname[256];uint32_t fsize;uint8_t fattrib;} FILINFO;
struct slot {char name[256],type[7];uint8_t attributes;uint32_t size,firstCluster;};
struct da_status_sector {uint8_t bytes[512];};
#include "../inc/build_enums.h"
#ifndef TEST_TARGET
#define TEST_TARGET TARGET_apple2
#endif
#define TARGET TEST_TARGET
#define STK_MHZ 9
#define DA_FIRST_CYL 254
#define stk_ms(x) ((x)*1000*STK_MHZ)
#define TRUE 1
#define FALSE 0
#define AM_DIR 16
#define AM_ARC 32
#define AM_RDO 1
#define FA_READ 1
#define FA_WRITE 2
#define FA_OPEN_EXISTING 0
#define FR_OK 0
#define FR_BAD_IMAGE 1
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define max_t(t,a,b) ((t)(a)>(t)(b)?(t)(a):(t)(b))
#define ASSERT assert
#define barrier() ((void)0)
#define log(...) printk(__VA_ARGS__)
#define f_size(fp) ((fp)->size)
#define HOST_acorn 4
#define HOST_tandy_coco 13
static struct {unsigned int fdd_host;} ff_cfg;
static unsigned int mode=2;
#undef EMULATION_APPLE2
#define EMULATION_APPLE2 2
#define always_inline __inline__ __attribute__((always_inline))
static bool_t emulation_is_qd(void){return mode==1;}
static bool_t emulation_is_apple2(void){return mode==2;}
#include "../inc/floppy.h"

static struct image image,*im=&image;
static struct slot mounted;
static uint8_t staging[10*1024],cells[32*1024];
static struct {char name[32];uint8_t *data;uint32_t size;} files[64];
static unsigned int nr_files,apple_attempts;
static char console[8192];
static jmp_buf fail_env;
extern const struct image_handler apple2_image_handler;
static void ft_fail(const char *file,unsigned int line,const char *fmt,...)
{va_list ap;fprintf(stderr,"%s:%u: ",file,line);va_start(ap,fmt);vfprintf(stderr,fmt,ap);va_end(ap);fputc('\n',stderr);abort();}
static void printk(const char *fmt,...)
{size_t n=strlen(console);if(n+1<sizeof(console)){va_list ap;va_start(ap,fmt);vsnprintf(console+n,sizeof(console)-n,fmt,ap);va_end(ap);}}
static void ft_fw_log_clear(void){console[0]=0;}
static bool_t log_has(const char *s){return strstr(console,s)!=NULL;}
static void F_die(FRESULT code){longjmp(fail_env,code);}
static void F_lseek(FIL *f,uint32_t pos){assert(pos<=f->size);f->pos=pos;}
static void F_read(FIL *f,void *buf,UINT n,UINT *done)
{assert(f->pos+n<=f->size);memcpy(buf,f->data+f->pos,n);f->pos+=n;if(done)*done=n;}
static void F_write(FIL *f,const void *buf,UINT n,UINT *done)
{assert(f->pos+n<=f->size);memcpy(f->data+f->pos,buf,n);f->pos+=n;if(done)*done=n;}
static void volume_cache_init(void *start,void *end){assert((uint8_t*)end>=(uint8_t*)start);memset(start,0xa5,(uint8_t*)end-(uint8_t*)start);}
static void volume_cache_metadata_only(FIL *f){(void)f;}
static uint32_t udiv64(uint64_t a,uint32_t b){assert(b);return a/b;}
static void fatfs_from_slot(FIL *f,const struct slot *s,BYTE flags)
{(void)flags;assert(s->firstCluster<nr_files);unsigned int i=s->firstCluster;*f=(FIL){.data=files[i].data,.size=files[i].size};if(im->disk_handler==&apple2_image_handler)apple_attempts++;}
static void filename_extension(const char *name,char *ext,unsigned int len)
{const char *p=strrchr(name,'.');unsigned int i=0;if(p)while(*++p && i+1<len)ext[i++]=tolower((unsigned char)*p);ext[i]=0;}
static bool_t unsupported_open(struct image *image){(void)image;return FALSE;}
#include "apple_stubs_under_test.c"
#include "apple_dispatch_under_test.c"
#include "../src/image/mfm.c"
#include "../src/image/apple2.c"
bool_t image_read_track(struct image *image){return image->track_handler->read_track(image);}

static void drive_reset(void)
{for(unsigned int i=0;i<nr_files;i++)free(files[i].data);nr_files=0;mode=2;apple_attempts=0;memset(im,0,sizeof(*im));console[0]=0;}
static void drive_add(const char *name,const void *data,uint32_t len)
{assert(nr_files<ARRAY_SIZE(files));unsigned int n=nr_files++;snprintf(files[n].name,sizeof(files[n].name),"%s",name);files[n].size=len;files[n].data=calloc(1,len?len:1);assert(files[n].data);if(data)memcpy(files[n].data,data,len);}
static uint32_t drive_get(const char *name,void *buf,uint32_t max)
{for(unsigned int n=0;n<nr_files;n++)if(!strcmp(files[n].name,name)){assert(files[n].size<=max);memcpy(buf,files[n].data,files[n].size);return files[n].size;}assert(0);return 0;}
static FRESULT image_mount(const char *name)
{unsigned int n;for(n=0;n<nr_files;n++)if(!strcmp(name,files[n].name))break;assert(n<nr_files);
 memset(&mounted,0,sizeof(mounted));snprintf(mounted.name,sizeof(mounted.name),"%s",name);filename_extension(name,mounted.type,sizeof(mounted.type));mounted.size=files[n].size;mounted.firstCluster=n;
 memset(im,0,sizeof(*im));memset(staging,0xcc,sizeof(staging));memset(cells,0,sizeof(cells));
 im->bufs.read_data=(struct image_buf){staging,sizeof(staging),0,0};im->bufs.write_data=im->bufs.read_data;
 im->bufs.write_bc=(struct image_buf){cells,sizeof(cells),0,0};im->bufs.read_bc=(struct image_buf){cells+sizeof(cells)/2,sizeof(cells)/2,0,0};
 int result=setjmp(fail_env);if(result)return result;image_open(im,&mounted,NULL);return FR_OK;}
static unsigned int bit_get(const uint8_t *p,uint32_t bit){return (p[bit/8]>>(7-(bit&7)))&1;}
static void bits_rotate(uint8_t *out,const uint8_t *in,uint32_t nr,uint32_t start)
{memset(out,0,(nr+7)/8);for(uint32_t i=0;i<nr;i++)out[i/8]|=bit_get(in,(start+i)%nr)<<(7-(i&7));}
static uint32_t crc32(const void *buf,uint32_t len)
{const uint8_t *p=buf;uint32_t crc=~0u;while(len--){crc^=*p++;for(unsigned int i=0;i<8;i++)crc=(crc>>1)^(0xedb88320u&-(crc&1));}return ~crc;}
static uint32_t image_stream_from(unsigned int track,uint32_t start,void *out,uint32_t nr)
{uint32_t ticks=start*im->write_bc_ticks;im->track_handler->setup_track(im,track,&ticks);uint32_t actual=im->cur_bc;uint8_t *dst=out;memset(dst,0,(nr+7)/8);
 for(uint32_t i=0;i<nr;i++){struct image_buf *bc=&im->bufs.read_bc;if(bc->prod==bc->cons)assert(image_read_track(im));assert(bc->prod>bc->cons);unsigned int bit=bit_get(bc->p,bc->cons%(bc->len*8));dst[i/8]|=bit<<(7-(i&7));bc->cons++;}
 return actual;}
static unsigned int image_stream(unsigned int track,void *out,unsigned int max)
{unsigned int n=(im->tracklen_bc+7)/8;assert(n<=max);image_stream_from(track,0,out,im->tracklen_bc);return n;}
static void image_write(unsigned int track,uint32_t start,const void *bits,uint32_t nr)
{assert(nr<=im->bufs.write_bc.len*8);im->wr_cons=im->wr_bc=0;im->write[0].start=start*im->write_bc_ticks;im->track_handler->setup_track(im,track,NULL);
 struct image_buf *wr=&im->bufs.write_bc;memcpy(wr->p,bits,(nr+7)/8);wr->cons=0;wr->prod=nr;im->write[0].bc_end=nr;im->wr_bc=1;
 assert(im->track_handler->write_track(im));assert(wr->cons==nr);}
static void image_sync(void){}

static struct test {const char *name;void (*run)(void);} tests[64];
static unsigned int nr_tests;
#define TEST(name) static void name(void);static void __attribute__((constructor)) reg_##name(void){tests[nr_tests++]=(struct test){#name,name};}static void name(void)
#define REQUIRE(x) do{if(!(x))ft_fail(__FILE__,__LINE__,"REQUIRE %s",#x);}while(0)
#define CHECK REQUIRE
#define CHECK_EQ(a,b) do{unsigned long long x=(a),y=(b);if(x!=y)ft_fail(__FILE__,__LINE__,"%s=%llu != %s=%llu",#a,x,#b,y);}while(0)
static bool_t check_mem(const void *a,const void *b,size_t n,const char *file,unsigned int line)
{if(memcmp(a,b,n))ft_fail(file,line,"memory mismatch, %zu bytes",n);return TRUE;}
#define CHECK_MEM(a,b,n) check_mem(a,b,n,__FILE__,__LINE__)
#include "apple2_vectors.c"
int main(void)
{for(unsigned int i=0;i<nr_tests;i++){printf("%s\n",tests[i].name);fflush(stdout);tests[i].run();}
#if TARGET == TARGET_dual
 drive_reset();uint8_t zero[35*4096]={0};drive_add("DOS.DSK",zero,sizeof(zero));mode=0;assert(image_mount("DOS.DSK")==FR_BAD_IMAGE && apple_attempts==0);mode=2;assert(image_mount("DOS.DSK")==FR_OK && apple_attempts==1);
#endif
 drive_reset();printf("%u upstream native Apple vector cases passed; target %u\n",nr_tests,TARGET);return 0;}
