"""Compile actual production functions with GPIO/USB mocked on the host.
Run from a checkout: python3 tests/check_upstream_fixes.py (C compiler required).
This checks state and register intent, not electrical timing on a Gotek.
"""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
work = root / 'out/upstream-tests'
work.mkdir(parents=True, exist_ok=True)

def function(path, name):
    source = (root / path).read_text()
    match = re.search(r'^(?:static )?[^\n;]+\b'+name+r'\([^;]*?\)\n\{', source, re.M)
    assert match, name
    start = match.start(); end = match.end(); depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}'); end += 1
    return source[start:end]+'\n'

common = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef char bool_t;
#define TRUE 1
#define FALSE 0
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define m(n) (1u<<(n))
'''
def run(name, code, flags=()):
    path = work/(name+'.c'); path.write_text(common+code)
    exe = work/name
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-sign-compare', '-Wno-unused-parameter',
                    '-Wno-old-style-declaration', '-funsigned-char',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-g', *flags, str(path), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

# Execute the entire sorted-entry branch including its selected-file update.
main = (root/'src/main.c').read_text()
start = main.index('    if (cfg.sorted) {', main.index('/* Populate current slot. */'))
branch = main[start:main.index('\n    } else {', start)]+'\n    }\n'
prefix = r'''
#define AM_DIR 16
struct native_dirent {char name[256];unsigned int dir_sect,dir_off;};
struct slot {char name[256];};
static struct {unsigned int slot_nr;struct native_dirent **sorted;struct slot slot;} cfg;
static struct {char win[512];} fatfs;
static struct {struct {char fname[256];unsigned int fattrib;} fp;
    struct {struct {void *fs;unsigned int attr;} obj;unsigned int dir_sect;void *dir_ptr;} file;} storage,*fs=&storage;
static unsigned int attr;
static void flashfloppy_fill_fileinfo(void *p){assert(p==&fs->file);fs->file.obj.attr=attr;}
static void fatfs_to_slot(struct slot *s,void *file,const char *name){assert(file==&fs->file);snprintf(s->name,sizeof(s->name),"%s",name);}
static void select_sorted(void){unsigned int i=0;
'''
suffix = r'''
    return;
is_dir:
    snprintf(cfg.slot.name,sizeof(cfg.slot.name),"[%s]",fs->fp.fname);
}
int main(void){
    const char *names[]={"A%B 100%.dsk","D%x 50%","%s"};
    struct native_dirent ent={.dir_sect=73,.dir_off=8},*items[]={&ent};cfg.sorted=items;
    for(unsigned int i=0;i<ARRAY_SIZE(names);i++)for(attr=0;attr<=16;attr+=16){
        strcpy(ent.name,names[i]);select_sorted();assert(!strcmp(fs->fp.fname,names[i]));
        assert(fs->file.dir_sect==73 && fs->file.dir_ptr==fatfs.win+8);
        if(!attr)assert(!strcmp(cfg.slot.name,names[i]));
        else {assert(cfg.slot.name[0]=='[');assert(strstr(cfg.slot.name,names[i])==cfg.slot.name+1);}
    }
    puts("Sorted navigation: literal percent filenames/folders and selected file metadata passed");
}
'''
run('filename', prefix+branch+suffix, ('-Wno-format-truncation',))

# Real SELA patcher: use low-address SRAM substitute, exercise the full branch range.
prefix = r'''
#include <sys/mman.h>
static uintptr_t entry_addr,normal_addr,amiga_addr;
#define IRQ_SELA_changed entry_addr
#define _IRQ_SELA_changed normal_addr
#define Amiga_HD_ID amiga_addr
#define unlikely(n) (n)
static unsigned int synced;
#define cpu_sync() (synced++)
'''
suffix = r'''
int main(void){
    void *p=mmap(NULL,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT,-1,0);
    assert(p!=MAP_FAILED);entry_addr=(uintptr_t)p+4096;
    for(int offset=-2048;offset<=2046;offset+=2){
        normal_addr=(entry_addr+12+offset)|1;amiga_addr=normal_addr;
        *(uint16_t *)(entry_addr+8)=0;update_SELA_irq(FALSE);
        uint16_t op=*(uint16_t *)(entry_addr+8);assert((op&0xf800)==0xe000);
        int actual=(op&0x7ff)*2;if(actual&0x800)actual-=4096;
        assert(actual==offset);unsigned int n=synced;update_SELA_irq(TRUE);assert(synced==n);
    }
    munmap(p,8192);puts("SELA: signed Thumb offsets, opcode mask and patch synchronization passed");
}
'''
run('sela', prefix+function('src/gotek/floppy.c','update_SELA_irq')+suffix,
    ('-Wno-int-to-pointer-cast',))

prefix = r'''
struct drive {uint8_t cyl;bool_t trk0;} drive;
#define outp_trk0 3
static unsigned int irq_disabled,calls;
static void IRQ_global_disable(void){irq_disabled=1;}
static void drive_change_output(struct drive *d,unsigned int pin,bool_t on){
    assert(irq_disabled && d==&drive && pin==outp_trk0 && on==(d->cyl==0));
    d->trk0=on;calls++;irq_disabled=0;
}
'''
suffix = r'''
int main(void){
    for(unsigned int i=0;i<256;i++){floppy_set_cyl(0,i);assert(drive.cyl==i && drive.trk0==(i==0) && !irq_disabled);}
    floppy_set_cyl(0,0);assert(drive.trk0 && calls==257);
    floppy_set_cyl(1,77);assert(drive.cyl==0 && calls==257);
    puts("Direct Access: cylinder/TRK0 zero and nonzero are updated with IRQs disabled");
}
'''
run('trk0',prefix+function('src/floppy.c','floppy_set_cyl')+suffix)

# Full HFE open routine; mock only storage/cache and the subsequent track seek.
hfe = (root/'src/image/hfe.c').read_text()
header = hfe[hfe.index('struct disk_header {'):hfe.index('/* interface_mode */')]
prefix = r'''
#undef le16toh
#define le16toh(x) (x)
#define sampleclk_us(x) (x)
#define SYNC_none 0
#define ASSERT assert
static unsigned int apple,reads,seeks;
static struct {unsigned int hfe_step;} ff_cfg;
static bool_t emulation_is_apple2(void){return apple;}
struct image {unsigned int fp,nr_cyls,nr_sides,step,write_bc_ticks,ticks_per_cell,sync;
    struct {unsigned int is_v3,double_step,tlut_base;} hfe;
    struct {struct {char *p;unsigned int len;} read_data;} bufs;};
static unsigned char disk[512];
static void F_read(void *f,void *p,unsigned int len,void *n){(void)f;(void)n;memcpy(p,disk,len);reads++;}
static void volume_cache_init(void *a,void *b){assert((char*)b-(char*)a>=0);}
static void volume_cache_metadata_only(void *p){(void)p;}
static void hfe_seek_track(struct image *im,unsigned int track){assert(track==0);seeks++;}
'''
suffix = r'''
int main(void){
    char buffer[8192];
    for(apple=0;apple<=1;apple++)for(unsigned int version=0;version<2;version++)
    for(unsigned int encoding=0;encoding<256;encoding++){
        struct image im={.bufs.read_data={buffer,sizeof(buffer)}};
        struct disk_header *h=(void*)disk;memset(disk,0,sizeof(disk));
        memcpy(h->sig,version?"HXCHFEV3":"HXCPICFE",8);
        h->nr_tracks=80;h->nr_sides=2;h->bitrate=250;h->single_step=1;h->track_encoding=encoding;
        unsigned int valid=apple?(encoding==255 || encoding==6 || encoding==7):(encoding!=6 && encoding!=7);
        seeks=0;assert(hfe_open(&im)==valid);assert(seeks==valid);
        if(valid)assert(im.nr_cyls==80 && im.nr_sides==2 && im.step==1);
    }
    puts("HFE: actual open accepts/rejects all encoding bytes in both modes, HFEv1/v3");
}
'''
run('hfe',prefix+header+function('src/image/hfe.c','hfe_open')+suffix)

# Production rotary paths, with host atomic compare/exchange and IRQ delivery.
for backend in ['floppy','quickdisk']:
    prefix = r'''
static struct {uint32_t pr;} regs;
#define exti (&regs)
#define pin_wgate 1
#define pin_motor 15
#define pin_chgrst 14
#define MOTOR_CHGRST_IRQ 40
#define rotary_irq 40
#define MOTOR_ignore 0
#define FDD_CFG(n) 1
#define barrier() __asm__ volatile("" ::: "memory")
#define cmpxchg(p,o,n) __sync_val_compare_and_swap(p,o,n)
static uint32_t board_rotary_exti_mask=m(6);
static unsigned int wgates,decodes,pend,motors,changes;
static struct drive {struct {bool_t changed;} motor;} drive;
static void IRQ_WGATE(void){wgates++;}
static void IRQ_rotary(void){decodes++;}
static void IRQx_set_pending(unsigned int irq){assert(irq==40);pend++;}
static void IRQ_MOTOR(struct drive *d){assert(d==&drive);motors++;}
static void IRQ_CHGRST(struct drive *d){assert(d==&drive);changes++;}
static volatile bool_t rotary_changed;
struct exti_irq {uint8_t irq,pri;uint16_t pr_mask;};
#define TARGET_shugart 4
#define TARGET_apple2 5
#define TIMER_IRQ_PRI 4
#define FLOPPY_IRQ_WGATE_PRI 2
#define FLOPPY_IRQ_SEL_PRI 1
#define FLOPPY_IRQ_STEP_PRI 3
'''
    prefix += '#define TARGET '+('4' if backend=='floppy' else '6')+'\n'
    board = (root/('src/gotek/'+backend+'.c')).read_text()
    prefix += re.search(r'static const struct exti_irq exti_irqs\[\] = \{.*?\n\};',board,re.S).group(0)+'\n'
    decode = ('IRQ_MOTOR_CHGRST_rotary' if backend=='floppy' else 'IRQ_rotary_changed')
    suffix = r'''
int main(void){
    unsigned int checked=0;
    for(unsigned int i=0;i<ARRAY_SIZE(exti_irqs);i++){
        if(exti_irqs[i].irq==40){assert(exti_irqs[i].pri==TIMER_IRQ_PRI);checked++;}
        if(exti_irqs[i].irq==7 || exti_irqs[i].irq==23){assert(exti_irqs[i].pri<TIMER_IRQ_PRI);checked++;}
    }
    assert(checked==3);
    for(unsigned int i=0;i<1000;i++){
        regs.pr=m(pin_wgate)|m(6);IRQ_WGATE_rotary();assert(wgates==i+1 && decodes==i && pend==i+1);
        regs.pr=0;DECODE();assert(decodes==i+1);
    }
    unsigned int n=decodes;regs.pr=0;DECODE();CHECK_IDLE;
    puts("BACKEND rotary: WGATE preserved, decode deferred to IRQ40, repeated edges and idle passed");
}
'''.replace('DECODE', decode).replace('BACKEND', backend)
    suffix = suffix.replace('CHECK_IDLE','assert(decodes==n)' if backend=='floppy' else 'assert(decodes==n+1)')
    run('rotary_'+backend,prefix+function('src/gotek/'+backend+'.c','IRQ_WGATE_rotary')+
        function('src/gotek/'+backend+'.c',decode)+suffix, ('-Wno-unused-function','-Wno-unused-variable'))

for mcu in ['stm32f105','at32f435']:
    prefix = r'''
#define DORD_default 0xffff
#define DORD_shift 4
#define DORD_row 7
#define DM_normal 0
#define OSD_read 1
#define OSD_write 2
#define OSD_BACKLIGHT 0x00
#define OSD_DATA 0x02
#define OSD_ROWS 0x10
#define OSD_HEIGHTS 0x20
#define OSD_BUTTONS 0x30
#define OSD_COLUMNS 0x40
#define I2C_CR2_LAST 1
#define I2C_CR2_ITEVTEN 2
#define I2C_CR1_ACK 1
#define I2C_CR1_START 2
static struct {unsigned int cr1,cr2;} regs,*i2c=&regs;
struct i2c_osd_info {unsigned char bytes[8];};
static struct {uint16_t osd_display_order;} ff_cfg;
static unsigned char buffer[256];
static char text[4][22];
static unsigned int menu_mode,display_mode,in_osd,lcd_columns,_bl=1,osd_buttons_tx=4,i2c_addr,refresh_count;
'''
    suffix = r'''
int main(void){
    for(unsigned int i=0;i<4;i++)memset(text[i],'A'+i,sizeof(text[i]));
    for(lcd_columns=16;lcd_columns<=21;lcd_columns+=5)
    for(unsigned int order=0;order<65536;order++){
        ff_cfg.osd_display_order=order;in_osd=OSD_read;memset(buffer,0xcc,sizeof(buffer));
        unsigned int len=osd_prep_buffer(),effective=order==DORD_default?0x7183:order;
        unsigned int rows=3;while(rows && ((effective>>((rows-1)*4))&7)==7)rows--;
        assert(len==6+rows*lcd_columns && buffer[2]==(OSD_ROWS|rows));
        for(unsigned int row=0;row<rows;row++)for(unsigned int col=0;col<lcd_columns;col++){
            unsigned int idx=(effective>>(row*4))&7;
            assert(buffer[6+row*lcd_columns+col]==(idx<4?'A'+idx:' '));
        }
        assert(buffer[len]==0xcc);
    }
    puts("OSD MCU: all row-order values at 16/21 columns, max 3 rows and blank padding passed");
}
'''.replace('MCU',mcu)
    run('osd_'+mcu,prefix+function('src/display/lcd_'+mcu+'.c','osd_prep_buffer')+suffix,
        ('-Wno-unused-variable',))

floppy_main = function('src/main.c', 'floppy_main')
assert re.search(r'FRESULT\s+fres\s*=\s*FR_OK\s*;', floppy_main)
assert floppy_main.index('if (cfg.ejected)') < floppy_main.index('if (fres)')
print('Ejected startup: result initialized before either ejected or run_floppy path')

prefix=r'''
#define DT_LED_7SEG 1
#define LED_TRACK 1
#define LED_TRACK_QUIESCENT 2
#define LED_NORMAL 3
struct track_info {unsigned int cyl,side,writing,qd_reading,sel,in_da_mode;};
static struct track_info track;
static unsigned int display_type=DT_LED_7SEG,qd,inject;
static uint8_t display_state;
static char shown[8];
static void floppy_get_track(struct track_info *ti){*ti=track;}
static void display_write_slot(bool_t b){(void)b;}
static bool_t emulation_is_qd(void){return qd;}
static void led_7seg_write_string(const char *s){snprintf(shown,sizeof(shown),"%s",s);}
static unsigned int atomic_state(uint8_t *p,unsigned int old,unsigned int new){
    if(inject){*p=LED_NORMAL;inject=0;}
    return __sync_val_compare_and_swap(p,old,new);
}
#define cmpxchg atomic_state
'''
suffix=r'''
int main(void){
    led_7seg_update_track(TRUE);
    for(unsigned int i=0;i<200;i++)led_7seg_update_track(FALSE);
    assert(display_state==LED_TRACK_QUIESCENT);
    led_7seg_update_track(TRUE);inject=1;
    for(unsigned int i=0;i<200;i++)led_7seg_update_track(FALSE);
    assert(display_state==LED_NORMAL && !inject);
    qd=1;track.qd_reading=1;led_7seg_update_track(TRUE);assert(!strcmp(shown,"rd"));
    track.writing=1;led_7seg_update_track(TRUE);assert(!strcmp(shown,"wrt"));
    track.qd_reading=track.writing=0;led_7seg_update_track(TRUE);assert(!strcmp(shown,"qd"));
    puts("7-seg: actual track updater preserves concurrent button state and QD rd/wrt/idle");
}
'''
run('led-state',prefix+function('src/main.c','led_7seg_update_track')+suffix)

for kind in ['img','dsk']:
    prefix=r'''
#define CHUNK_SIZE 1024
#define SYNC_fm 1
#define MFM_DAM_CRC 0xe295
#define FM_DAM_CRC 0xbf84
struct raw_sec {unsigned int n;};
struct raw_trk {unsigned int nr_sectors;};
struct sib {unsigned int len;};
struct tib {unsigned int nr_secs;struct sib sib[1];};
struct image {uint32_t cur_bc,tracklen_bc;unsigned int sync;
    struct {uint16_t crc;unsigned int idx_sz,idam_sz,dam_sz_pre,dam_sz_post,trk_pos,rd_sec_pos,decode_data_pos,decode_pos;} dsk;
    struct {uint16_t crc;unsigned int idx_sz,idam_sz,dam_sz_pre,dam_sz_post,trk_sec,rd_sec_pos,decode_data_pos,decode_pos,track_delay_bc;
        struct raw_trk *trk;struct raw_sec *sec_info;uint8_t *sec_map;} img;};
static struct tib tib={.nr_secs=1,.sib={{512}}};
static struct tib *tib_p(struct image *im){(void)im;return &tib;}
static unsigned int data_sz(struct sib *s){return s->len;}
static bool_t is_gaps_sector(struct sib *s){(void)s;return FALSE;}
static unsigned int sec_sz(unsigned int n){return 128u<<n;}
static unsigned int enc_sec_sz(struct image *im,struct raw_sec *s){return im->img.idam_sz+im->img.dam_sz_pre+sec_sz(s->n)+im->img.dam_sz_post;}
'''
    suffix=r'''
int main(void){
    unsigned char data[512],mfm[]={0xa1,0xa1,0xa1,0xfb},fm[]={0xfb};
    struct raw_trk trk={1};struct raw_sec sec={2};uint8_t map[]={0};
    for(unsigned int i=0;i<512;i++)data[i]=i;
    for(unsigned int mode=0;mode<2;mode++)for(unsigned int offset=0;offset<512;offset++){
        struct image im={.cur_bc=(64+20+30+offset)*16,.sync=mode,
            .img={.idx_sz=64,.idam_sz=20,.dam_sz_pre=30,.dam_sz_post=5,.trk=&trk,.sec_info=&sec,.sec_map=map},
            .dsk={.idx_sz=64,.idam_sz=20,.dam_sz_pre=30,.dam_sz_post=5}};
        uint16_t seed=CRC_SEED;
        assert(calc_start_pos(&im)==offset && im.KIND.decode_data_pos==0 && im.KIND.decode_pos==3);
        assert(im.KIND.crc==seed);
        uint16_t actual=crc16_ccitt(data,sizeof(data),im.KIND.crc);
        uint16_t expected=crc16_ccitt(data,sizeof(data),crc16_ccitt(MARK,MARK_SIZE,0xffff));
        assert(actual==expected);
    }
    puts("KIND: actual seek into first data chunk initializes CRC for all 512 offsets");
}
'''.replace('CRC_SEED','((mode==SYNC_fm)?FM_DAM_CRC:MFM_DAM_CRC)' if kind=='img' else 'MFM_DAM_CRC')
    suffix=suffix.replace('MARK_SIZE','((mode==SYNC_fm)?sizeof(fm):sizeof(mfm))' if kind=='img' else 'sizeof(mfm)')
    suffix=suffix.replace('MARK','((mode==SYNC_fm)?fm:mfm)' if kind=='img' else 'mfm').replace('KIND',kind)
    run('crc-'+kind,prefix+(root/'src/crc.c').read_text()+function('src/image/'+kind+'.c','calc_start_pos')+suffix,
        ('-Wno-unused-function','-Wno-unused-variable'))

# The real timeout block must suspend folder autoload once after an empty exit.
start=floppy_main.index('            wait_ms = (cfg.slot.attributes & AM_DIR)')
end=floppy_main.index('            if (wait_ms &&',start)
timeout=floppy_main[start:end]
prefix=r'''
#define AM_DIR 16
static struct {struct {unsigned int attributes;} slot;} cfg;
static struct {unsigned int autoselect_file_secs,autoselect_folder_secs;} ff_cfg;
static bool_t exited_empty_folder;
static unsigned int timeout(void){unsigned int wait_ms;
'''
suffix=r'''
return wait_ms;}
int main(void){
    cfg.slot.attributes=AM_DIR;ff_cfg.autoselect_folder_secs=2;ff_cfg.autoselect_file_secs=3;
    assert(timeout()==2000);exited_empty_folder=TRUE;assert(timeout()==0 && !exited_empty_folder);
    assert(timeout()==2000);ff_cfg.autoselect_folder_secs=0;assert(timeout()==0);
    cfg.slot.attributes=0;assert(timeout()==3000);
    puts("Autoselect: actual empty-folder timeout guard and manual-folder/image timeouts passed");
}
'''
run('empty-folder',prefix+timeout+suffix)
