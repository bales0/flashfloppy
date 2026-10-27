"""Differential golden test of all FF.CFG keys and valid/invalid value conversions.
The digest was captured from ca2f27d before parser optimizations. This compiles
the current production parser and read_ff_cfg, not a second implementation.
"""
from pathlib import Path
import hashlib, re, subprocess
root=Path(__file__).resolve().parents[1]
work=root/'out/config-semantics';work.mkdir(parents=True,exist_ok=True)
def function(name):
    source=(root/'src/main.c').read_text()
    match=re.search(r'^(?:static )?[^\n;]+\b'+name+r'\([^;]*?\)\n\{',source,re.M)
    start=match.start();end=match.end();depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'
subprocess.run(['python3',str(root/'scripts/mk_config.py'),str(root/'examples/FF.CFG'),str(work/'ff_cfg_defaults.h')],check=True)
prefix=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
typedef char bool_t;
typedef int FRESULT;
typedef struct {const char *text;unsigned int pos;} FIL;
#define packed __attribute__((packed))
#define TRUE 1
#define FALSE 0
#define TARGET 7
#define TARGET_dual 7
#define TARGET_apple2 5
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define FINTF_SHUGART 0
#define FINTF_IBMPC 1
#define FINTF_IBMPC_HDOUT 2
#define FINTF_JPPC_HDOUT 3
#define FINTF_AMIGA 4
#define FINTF_JPPC 5
#define FA_READ 1
#define outp_dskchg 0
#define outp_rdy 4
#define outp_hden 5
#define outp_unused 6
#define outp_nr 6
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
'''
prefix+='#include "'+str(root/'inc/config.h')+'"\n'
prefix+=r'''
struct ff_cfg ff_cfg;
const struct ff_cfg dfl_ff_cfg={.version=FFCFG_VERSION,.size=sizeof(struct ff_cfg),.qd_ready_layout=255,
#define x(n,o,v) .o=v,
#include "ff_cfg_defaults.h"
#undef x
};
static struct {unsigned int cdir;} fatfs;
static struct {unsigned int cfg_cdir;bool_t ffcfg_has_display_off_secs,ffcfg_has_display_scroll_rate,ffcfg_has_step_volume;} cfg;
static struct {FIL file;char buf[512];} storage,*fs=&storage;
static const char *input;
static int F_try_open(FIL *f,const char *name,unsigned int mode){assert(!strcmp(name,"FF.CFG") && mode==FA_READ);f->text=input;f->pos=0;return 0;}
static void F_close(FIL *f){(void)f;}
static void F_read(FIL *f,void *buf,unsigned int len,void *n){assert(len==1);(void)n;*(char*)buf=f->text[f->pos];if(f->text[f->pos])f->pos++;}
'''
prefix+='#include "'+str(root/'src/config.c')+'"\n'
helpers=''.join(function(name) for name in ['parse_pin_str','parse_display_order'])
if 'static char *next_item(' in (root/'src/main.c').read_text():helpers+=function('next_item')
suffix=r'''
int main(void){
    char line[2048];
    while(fgets(line,sizeof(line),stdin)){
        input=line;ff_cfg=dfl_ff_cfg;memset(&cfg,0,sizeof(cfg));memset(&storage,0,sizeof(storage));
        assert(read_ff_cfg());
        for(unsigned int i=0;i<sizeof(ff_cfg);i++)printf("%02x",((unsigned char*)&ff_cfg)[i]);
        printf("%u%u%u\n",cfg.ffcfg_has_display_off_secs,cfg.ffcfg_has_display_scroll_rate,cfg.ffcfg_has_step_volume);
    }
}
'''
(work/'parser.c').write_text(prefix+helpers+function('read_ff_cfg')+suffix)
exe=work/'parser'
subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-old-style-declaration','-Wno-sign-compare','-Wno-format-truncation',
                '-funsigned-char','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(work),str(work/'parser.c'),'-o',str(exe)],check=True)
names=re.findall(r'^x\(([^,]+),', (work/'ff_cfg_defaults.h').read_text(), re.M)
values=['yes','no','auto','invalid','', '0','1','2','3','7','10','20','21','127','255','256','-1',
        'shugart','ibmpc','ibmpc-hdout','jppc','jppc-hdout','akai-s950','amiga','jc',
        'acorn','akai','casio','dec','ensoniq','fluke','gem','ibm-3174','memotech','msx','nascom','pc98','pc-dos','tandy-coco','ti99','uknc',
        'sharp','roland','generic','standard','motor-off','ignore','delay-3','pa14','step',
        'low','high','c','rdy','dens','chg','nrdy','ndens','nchg','realtime','instant','eot',
        'static','last','init','always','never','small','none','files','folders','native','indexed',
        'rotary','rotary-fast','eject','htu','zero','reverse','rotary,reverse','reverse,rotary',
        'quarter','half','trackball','buttons','full','v2','reverse,v2,half','half,none',
        'lcd-20x4','oled-128x64-rotate-inverse-narrow-slow-hflip','6x13','8x16','default','0,1,2','0d,1,7',
        'slotnr','slotnr,5','5,slotnr','sel','"A%B name"']
cases=[f'{key}={value}\n' for key in names for value in values]
cases += [f'{key}=yes\n' for key in ['interface','host','pin02','pin34','max-cyl','motor-delay','chgrst','unknown-key','QD-HOST']]
output=subprocess.check_output([str(exe)],input=''.join(cases).encode())
assert len(output.splitlines())==len(cases)
digest=hashlib.sha256(output).hexdigest()
expected='915b0b409309e4d3de64d75438dbbb7447f41dbeffc4bae8d9f84dfc687ad3f4'
assert digest==expected,(digest,expected)
print(f'Actual FF.CFG parser: {len(names)} keys, {len(cases)} valid/invalid cases, digest {digest}')

# The shared parser must also preserve IMG.CFG option indices and sections.
img=(root/'src/image/img.c').read_text()
start=img.index('    enum {',img.index('static bool_t tag_open('))
table=img[start:img.index('    int match,',start)]
nr='.nr=IMGCFG_nr,' if 'unsigned int nr;' in (root/'inc/config.h').read_text() else ''
img_main=r'''
int main(void){
    const char *names[]={"tracks","cyls","heads","step","secs","bps","img_bps","id","h","mode","interleave","cskew","hskew","rpm","gap2","gap3","gap4a","iam","rate","file-layout"};
    char line[128],arg[64];
    for(unsigned int i=0;i<ARRAY_SIZE(names);i++){
        snprintf(line,sizeof(line),"%s = \"quoted value\"\r\n",names[i]);
        FIL file={line,0};struct opts opts={.file=&file,.opts=img_cfg_opts,NR.arg=arg,.argmax=sizeof(arg)};
        assert(get_next_opt(&opts)==(int)i && !strcmp(arg,"quoted value"));assert(get_next_opt(&opts)==OPT_eof);
    }
    FIL file={"unknown=yes\n[Tag::1024]\ntracks=80\nTRACKS=99\nrate=250\n",0};
    struct opts opts={.file=&file,.opts=img_cfg_opts,NR.arg=arg,.argmax=sizeof(arg)};
    assert(get_next_opt(&opts)==OPT_section && !strcmp(arg,"Tag::1024"));
    assert(get_next_opt(&opts)==IMGCFG_tracks && !strcmp(arg,"80"));
    assert(get_next_opt(&opts)==IMGCFG_rate && !strcmp(arg,"250"));
    assert(get_next_opt(&opts)==OPT_eof);
    puts("Actual IMG.CFG table/parser: all 20 indices, quoting, CRLF, sections, unknown and case handling passed");
}
'''.replace('NR',nr)
# Reuse only types/defines and the real low-level parser, without FF.CFG helpers.
img_prefix=prefix[:prefix.index('struct ff_cfg ff_cfg;')]
img_prefix+=r'''
static void F_read(FIL *f,void *buf,unsigned int len,void *n){assert(len==1);(void)n;*(char*)buf=f->text[f->pos];if(f->text[f->pos])f->pos++;}
'''
img_prefix+='#include "'+str(root/'src/config.c')+'"\n'
(work/'img-parser.c').write_text(img_prefix+table+img_main)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-old-style-declaration','-Wno-sign-compare','-funsigned-char',
                '-fsanitize=address,undefined','-fno-sanitize-recover=all',str(work/'img-parser.c'),'-o',str(work/'img-parser')],check=True)
subprocess.run([str(work/'img-parser')],check=True)
