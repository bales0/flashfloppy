"""Actual USB/delay/UI/logfile code with deterministic host fault injection.

No USB hardware, ARM interrupt latency or electrical timing is verified here.
Generated host/ARM checks stay under out/; no upstream harness is required.
"""
from pathlib import Path
import os,re,subprocess

root=Path(__file__).resolve().parents[1]
work=root/'out/audit-347-upstream/tests';work.mkdir(parents=True,exist_ok=True)

def function(path,name):
    source=(root/path).read_text()
    m=re.search(r'^(?:static )?[^\n;]+\b'+name+r'\s*\([^;]*?\)\n\{',source,re.M)
    assert m,name
    end=m.end();depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[m.start():end]+'\n'

common=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
#include <setjmp.h>
typedef char bool_t;
typedef int FRESULT;
#define TRUE 1
#define FALSE 0
#define FR_OK 0
#define FR_DISK_ERR 1
#define FR_BAD_IMAGE 31
#define FR_DISK_FULL 32
#define ASSERT assert
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define barrier() asm volatile ("" ::: "memory")
'''

def run(name,source,extra=()):
    path=work/(name+'.c');path.write_text(common+source)
    exe=work/name
    subprocess.run(['cc','-std=gnu11','-g','-Wall','-Wextra','-Werror',
                    '-Wno-unused-parameter','-Wno-sign-compare',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all',
                    *extra,str(path),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

# Real register declarations; all bitfield combinations including channel 15.
header=(root/'src/usb/stm32_usbh_msc/inc/usb_regs.h').read_text()
unions='\n'.join(re.search(r'typedef union _'+name+r'\b.*?} '+name+r'\s*;',header,re.S).group(0)
                 for name in ['USB_OTG_HNPTXSTS_TypeDef','USB_OTG_HPTXSTS_TypeDef','USB_OTG_GINTMSK_TypeDef'])
usb=unions+r'''
_Static_assert(sizeof(USB_OTG_HNPTXSTS_TypeDef)==4,"HNPTXSTS must be 32 bits");
_Static_assert(sizeof(USB_OTG_HPTXSTS_TypeDef)==4,"HPTXSTS must be 32 bits");
typedef struct {
    struct {struct {uint32_t HNPTXSTS,GINTMSK;} *GREGS;
            struct {uint32_t HPTXSTS;} *HREGS;} regs;
    struct {struct {uint32_t xfer_len,xfer_count;uint8_t *xfer_buff;} hc[16];} host;
} USB_OTG_CORE_HANDLE;
#define USB_OTG_READ_REG32(p) (*(p))
#define USB_OTG_MODIFY_REG32(p,clear,set) (*(p)=(*(p)&~(clear))|(set))
static unsigned int written,written_channel;
static uint8_t *written_buffer;
static void USB_OTG_WritePacket(USB_OTG_CORE_HANDLE *p,uint8_t *buf,unsigned int ch,unsigned int len)
{written+=len;written_channel=ch;written_buffer=buf;p->regs.GREGS->HNPTXSTS&=~0xffffu;p->regs.HREGS->HPTXSTS&=~0xffffu;}
'''
for name in ['nptxfempty','ptxfempty']:
    usb+=function('src/usb/stm32_usbh_msc/usb_hcd_int.c','USB_OTG_USBH_handle_'+name+'_ISR')
usb+=r'''
int main(void){
 for(unsigned int ch=0;ch<16;ch++)for(unsigned int token=0;token<4;token++)
 for(unsigned int term=0;term<2;term++)for(unsigned int odd=0;odd<2;odd++){
    uint32_t word=0x3456u|(0xabu<<16)|(term<<24)|(token<<25)|(ch<<27)|(odd<<31);
    USB_OTG_HNPTXSTS_TypeDef n={.d32=word};USB_OTG_HPTXSTS_TypeDef p={.d32=word};
    assert(n.b.nptxfspcavail==0x3456 && n.b.nptxqspcavail==0xab);
    assert(n.b.nptxqtop_terminate==term && n.b.nptxqtop_token==token && n.b.nptxqtop_chnum==ch && n.b.Reserved==odd);
    assert(p.b.ptxfspcavail==0x3456 && p.b.ptxqspcavail==0xab);
    assert(p.b.ptxqtop_terminate==term && p.b.ptxqtop_token==token && p.b.ptxqtop_chnum==ch && p.b.ptxqtop_odd_even==odd);
    n.d32=p.d32=0;n.b.nptxqtop_chnum=p.b.ptxqtop_chnum=ch;
    assert(n.d32==(ch<<27) && p.d32==(ch<<27));
 }
 for(unsigned int periodic=0;periodic<2;periodic++)for(unsigned int ch=0;ch<16;ch++){
    USB_OTG_CORE_HANDLE dev={0};uint8_t data[8]={0};
    typeof(*dev.regs.GREGS) g={.HNPTXSTS=10|(ch<<27),.GINTMSK=~0u};
    typeof(*dev.regs.HREGS) h={.HPTXSTS=10|(ch<<27)};
    dev.regs.GREGS=&g;dev.regs.HREGS=&h;
    dev.host.hc[ch].xfer_len=7;dev.host.hc[ch].xfer_buff=data;written=0;
    unsigned int result=periodic?USB_OTG_USBH_handle_ptxfempty_ISR(&dev):USB_OTG_USBH_handle_nptxfempty_ISR(&dev);
    assert(result==1 && written==7 && written_channel==ch && written_buffer==data);
    assert(dev.host.hc[ch].xfer_count==7 && dev.host.hc[ch].xfer_len==0 && dev.host.hc[ch].xfer_buff==data+7);
    USB_OTG_GINTMSK_TypeDef mask={.d32=g.GINTMSK};assert(periodic?!mask.b.ptxfempty:!mask.b.nptxfempty);
 }
 puts("USB: 32-bit layouts, all channel/token/flag fields and actual FIFO handlers passed");
}
'''
run('usb-layout',usb)
assert not re.search(r'\.(?:np|p)txqtop\.',(root/'src/usb/stm32_usbh_msc/usb_hcd_int.c').read_text())

# Compile the same actual register definitions with both ARM MCU configurations.
for cpu in ['cortex-m3','cortex-m4']:
    arm=work/('usb-layout-'+cpu+'.c');arm.write_text('#include <stdint.h>\n'+unions+'''
_Static_assert(sizeof(USB_OTG_HNPTXSTS_TypeDef)==4,"nonperiodic size");
_Static_assert(sizeof(USB_OTG_HPTXSTS_TypeDef)==4,"periodic size");
unsigned int channel(uint32_t value){USB_OTG_HNPTXSTS_TypeDef r={.d32=value};return r.b.nptxqtop_chnum;}
''')
    subprocess.run(['arm-none-eabi-gcc','-Os','-mthumb','-mcpu='+cpu,'-S',str(arm),'-o',str(arm.with_suffix('.s'))],check=True)
    assert re.search(r'ubfx\s+r0, r0, #27, #4',arm.with_suffix('.s').read_text())

if os.environ.get('FF347_CHECK_THROUGH')=='usb':
    raise SystemExit(0)

relax=re.search(r'^#define cpu_relax\(\).*$',(root/'inc/intrinsics.h').read_text(),re.M).group(0)
assert '""' in relax and '"memory"' in relax and 'nop' not in relax
delays=''.join(function('src/cortex.c',name) for name in ['delay_ticks','delay_ns','delay_us','delay_ms'])
assert 'cpu_relax();' in delays
for mhz in [9,18]:
    source=relax+f'\n#define STK_MHZ {mhz}\n'+r'''
#define STK_MASK ((1u<<24)-1)
static struct {uint32_t val;} counter;
static uint32_t current,increment,reads;
static typeof(counter) *sample(void){counter.val=current;current=(current-increment)&STK_MASK;reads++;assert(reads<100000);return &counter;}
#define stk sample()
'''+delays+r'''
static void check(unsigned int ticks,unsigned int start,unsigned int step){
 current=start;increment=step;reads=0;delay_ticks(ticks);
 assert(reads>=2 && (uint64_t)(reads-1)*step>=ticks);
 assert(ticks==0 || (uint64_t)(reads-2)*step<ticks);
}
int main(void){
 for(unsigned int start=0;start<30;start+=3)for(unsigned int step=1;step<12;step+=2)
 for(unsigned int ticks=0;ticks<200;ticks++)check(ticks,start,step);
 check(STK_MASK+100,4,1000);
 current=10;increment=1;reads=0;delay_ns(2000);assert(reads-1==2*STK_MHZ);
 current=10;increment=1;reads=0;delay_us(3);assert(reads-1==3*STK_MHZ);
 current=10;increment=1000;reads=0;delay_ms(2);assert(reads-1==2*STK_MHZ);
 puts("Delay: actual SysTick loops, wrap, zero and ns/us/ms conversions passed");
}
'''
    run('delay-'+str(mhz),source)

if os.environ.get('FF347_CHECK_THROUGH')=='delay':
    raise SystemExit(0)

# Actual nested FatFS cancellation wrapper, with setjmp replacing only ARM stack switching.
cancellation=r'''
struct cancellation {jmp_buf env;bool_t active;};
static int call_cancellable_fn(struct cancellation *c,int (*fn)(void *),void *arg)
{c->active=TRUE;if(!setjmp(c->env))fn(arg);c->active=FALSE;return 0;}
static bool_t cancellation_is_active(struct cancellation *c){return c->active;}
static void cancel_call(struct cancellation *c){assert(c->active);longjmp(c->env,1);}
static struct cancellation fs_cancellation[2];
static struct cancellation *next_cancellation=fs_cancellation;
static FRESULT fs_fresult;
'''+''.join(function('src/fs.c',name) for name in ['F_call_cancellable','handle_fr','F_die'])

logfile=cancellation+r'''
typedef struct {unsigned int unused;} FIL;
#define FA_OPEN_APPEND 1
#define FA_WRITE 2
#define IRQ_global_disable() ((void)0)
#define IRQ_global_enable() ((void)0)
static char output[8192];
static unsigned int output_len,operation,fail_operation;
static FRESULT injected_error;
static void io(void){if(++operation==fail_operation)F_die(injected_error);}
static void F_open(FIL *f,const char *path,unsigned int mode){assert(!strcmp(path,"FFLOG.TXT"));io();}
static void F_write(FIL *f,const void *data,unsigned int n,void *done)
{io();assert(output_len+n<sizeof(output));memcpy(output+output_len,data,n);output_len+=n;output[output_len]=0;}
static void F_close(FIL *f){io();}
#define printk lf_printk
#define vprintk lf_vprintk
'''+(root/'src/logfile.c').read_text()+r'''
#undef printk
#undef vprintk
static FIL file;
static int outer(void *unused){logfile_flush(&file);return 0;}
static void reset(void){cons=prod=0;quiesce=FALSE;output_len=operation=fail_operation=0;output[0]=0;}
int main(void){
 reset();lf_printk("one %u\n",1);assert(F_call_cancellable(outer,NULL)==FR_OK);
 lf_printk("two\n");assert(F_call_cancellable(outer,NULL)==FR_OK);assert(!strcmp(output,"one 1\r\ntwo\r\n"));
 for(unsigned int op=1;op<=3;op++)for(unsigned int error=1;error<=32;error+=31){
    reset();lf_printk("lost\n");fail_operation=op;injected_error=error;
    assert(F_call_cancellable(outer,NULL)==error && !quiesce && next_cancellation==fs_cancellation);
    unsigned int before=prod;lf_printk("x");assert(prod==before+1);
    fail_operation=0;assert(F_call_cancellable(outer,NULL)==FR_OK && !quiesce);
 }
 reset();for(unsigned int i=0;i<2200;i++)lf_printk("a");assert(F_call_cancellable(outer,NULL)==FR_OK);
 assert(strstr(output,"[lost 152]") && !quiesce);
 puts("Logfile: actual nested cancellation, append, overflow, open/write/close errors and recovery passed");
}
'''
run('logfile-errors',logfile)

# Execute the common run_floppy() and caller cleanup; backend and GPIO are mocked.
main=(root/'src/main.c').read_text();floppy=function('src/main.c','floppy_main')
decl=re.search(r'    uint8_t b = 0;',floppy);assert decl,'button result must start at zero'
assert 'FRESULT fres = FR_OK;' in floppy
start=floppy.index('            floppy_arena_teardown();')
cleanup=floppy[start:floppy.index('            floppy_arena_setup();',start)]
assert 'display_state = LED_NORMAL;' not in function('src/main.c','run_floppy')
ui=cancellation+r'''
typedef uint32_t time_t;
#define time_ms(x) (x)
#define DM_normal 0
#define DT_LED_7SEG 1
#define DT_LCD_OLED 2
#define LED_NORMAL 0
#define LED_TRACK 1
#define LED_BUTTON_HELD 3
#define LED_BUTTON_RELEASED 4
#define BUTTON_SCAN_HZ 500
#define B_SELECT 4
#define wp_column 7
static unsigned int display_type,display_state,scenario,button_reads,updates,marks,cancelled;
static unsigned int display_ticks;
static struct {unsigned int slot_nr,slot;} cfg;
static struct {int ticks;} lcd_scroll;
static uint32_t now;
static uint8_t read_buttons(void){return scenario==0||scenario==3?(button_reads++?B_SELECT:0):0;}
#define buttons read_buttons()
static void floppy_insert(unsigned int unit,void *slot){if(scenario==1)F_die(FR_BAD_IMAGE);}
static void led_7seg_update_track(bool_t force){if(display_type==DT_LED_7SEG)display_state=LED_TRACK;updates++;}
static void lcd_write_track_info(bool_t force){}
static time_t time_now(void){now+=20;return now;}
static time_t time_diff(time_t a,time_t b){return b-a;}
static bool_t floppy_handle(void){if(scenario==4)F_die(FR_DISK_ERR);return scenario==5;}
static void lcd_scroll_name(void){}
static void canary_check(void){}
static void assert_volume_connected(void){if(scenario==2)F_die(FR_DISK_ERR);}
static void floppy_arena_teardown(void){}
static void speaker_notify_insert(unsigned int nr){}
static void floppy_cancel(void){cancelled++;}
static void speaker_notify_eject(void){}
static void lcd_write(unsigned int x,unsigned int y,int n,const char *s){assert(!strcmp(s,"-"));marks++;}
static void lcd_on(void){}
'''+function('src/main.c','run_floppy')+function('src/main.c','led_handle_display')+'''
static FRESULT result;
static uint8_t saved_button;
static int caller(void *unused){
    FRESULT fres = FR_OK;
'''+decl.group(0)+'\n'+cleanup+r'''
    result=fres;saved_button=b;return 0;
}
int main(void){
 for(display_type=1;display_type<=2;display_type++)
 for(scenario=0;scenario<6;scenario++){
    display_state=LED_TRACK;button_reads=updates=marks=cancelled=0;now=0;saved_button=0xff;
    FRESULT outer=F_call_cancellable(caller,NULL);
    assert(cancelled==1 && (display_type!=DT_LED_7SEG || display_state==LED_NORMAL));
    if(display_type==DT_LED_7SEG)assert(led_handle_display(B_SELECT)==B_SELECT);
    if(scenario==2){assert(outer==FR_DISK_ERR);continue;}
    assert(outer==FR_OK);
    assert(result==(scenario==1?FR_BAD_IMAGE:scenario==4?FR_DISK_ERR:FR_OK));
    assert(saved_button==((scenario==0||scenario==3)?B_SELECT:0));
    assert(marks==((scenario==0||scenario==3)&&display_type==DT_LCD_OLED));
    if(scenario==0)assert(updates>=2);
 }
 puts("UI: actual run/caller cleanup, mount failure, USB loss, backend abort and button indication passed");
}
'''
# The host libc already declares time_t; use a private name for the firmware typedef.
ui=ui.replace('time_t','fw_time_t')
run('display-cancellation',ui)
print('Universal 3.47 fault-injection checks passed (HW unverified)')
