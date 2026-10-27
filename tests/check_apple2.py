"""Host checks of actual Apple phase frontend, capture ISR and boot menu.
Electrical read/write timing still requires a connected Apple II.
"""
from pathlib import Path
import re, subprocess
root = Path(__file__).resolve().parents[1]
work = root / 'out/apple2-tests'
work.mkdir(exist_ok=True)
def function(path, name):
    text = (root/path).read_text()
    match = re.search(r'^(?:static )?[^\n;]+\b'+name+r'\([^;]*?\)\n\{',text,re.M)
    start = match.start(); end = match.end(); depth = 1
    while depth:
        depth += (text[end]=='{') - (text[end]=='}'); end += 1
    return text[start:end]+'\n'
frontend = function('src/gotek/floppy.c','POLL_step') + function('src/gotek/floppy.c','IRQ_wdata_capture')
prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define TRUE 1
#define FALSE 0
#define m(n) (1u<<(n))
#define pin_sel0 0
#define pin_pha0 10
#define pin_pha1 9
#define pin_pha2 0
#define pin_pha3 1
#define STEP_active 2
#define STEP_started 1
#define FLOPPY_SOFTIRQ 43
#define TIM_CCER_CC1P 2
#define FDD_CFG(n) 84
static const struct {unsigned int fdd_max_cyl;} dfl_ff_cfg={84};
#define time_ms(n) (n)
static struct {uint16_t idr;} a,b;
#define gpioa (&a)
#define gpiob (&b)
static struct {volatile uint32_t ccr1,ccer;} capture;
#define tim_wdata (&capture)
static struct drive {unsigned int cyl;struct {unsigned int state,inward,start;} step;} drive;
static struct timer {unsigned int deadline;} step_timer;
static void *dma_rd,*dma_wr;
static unsigned int rd_stop,wr_stop,pending;
static void rdata_stop(void){rd_stop++;}
static void wdata_stop(void){wr_stop++;}
static unsigned int time_now(void){return 123;}
static void IRQx_set_pending(unsigned int irq){assert(irq==43);pending++;}
static void timer_set(struct timer *t,unsigned int deadline){assert(deadline==t->deadline+1);t->deadline=deadline;}
'''
suffix = r'''
static void phase(unsigned int n){a.idr=((n&1)<<10)|((n&2)<<8)|((n&8)>>2);b.idr=(n&4)>>2;}
static void reset_phase(void){a.idr=m(pin_sel0);POLL_step(0);drive.step.state=0;rd_stop=wr_stop=pending=0;}
static void expect(unsigned int cyl,unsigned int n,unsigned int step,unsigned int inward){
    reset_phase();drive.cyl=cyl;phase(n);POLL_step(0);assert(!pending);
    POLL_step(0);assert(pending==step && rd_stop==step && wr_stop==step);
    if(step){assert(drive.step.inward==inward && drive.step.state==STEP_started && drive.step.start==123);}
}
int main(void){
    dma_rd=dma_wr=&drive;
    for(unsigned int cyl=0;cyl<=84;cyl++){
        expect(cyl,m((cyl+1)&3),cyl<84,1);
        expect(cyl,m((cyl+3)&3),cyl>0,0);
        expect(cyl,m(cyl&3),0,0);
        expect(cyl,m((cyl+2)&3),0,0);
        expect(cyl,15,0,0);
    }
    reset_phase();drive.cyl=1;phase(4);drive.step.state=STEP_active;
    POLL_step(0);POLL_step(0);assert(!pending);
    reset_phase();drive.cyl=1;phase(4);POLL_step(0);phase(1);POLL_step(0);assert(!pending);
    capture.ccer=0x101;capture.ccr1=42;IRQ_wdata_capture();assert(capture.ccer==0x103);
    IRQ_wdata_capture();assert(capture.ccer==0x101 && capture.ccr1==42);
    puts("Apple II: phase debounce, both directions, boundaries, DMA stop and capture polarity passed");
}
'''
(work/'frontend.c').write_text(prefix+frontend+suffix)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(work/'frontend.c'),'-o',str(work/'frontend')],check=True)
subprocess.run([str(work/'frontend')],check=True)

menu_prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#define EMULATION_FDD 0
#define EMULATION_QD 1
#define EMULATION_APPLE2 2
#define B_LEFT 1
#define B_RIGHT 2
#define B_SELECT 4
#define DM_menu 1
#define DM_normal 0
#define DT_LED_7SEG 1
#define DT_LCD_OLED 2
#define LED_NORMAL 1
#define BACKLIGHT_ON 2
static unsigned int mode,display_mode,display_type,display_state,writes,updates;
static struct {unsigned int boot_emulation;} ff_cfg;
static uint8_t queue[32];static unsigned int pos;
static jmp_buf update_env;
static uint8_t next_button(void){assert(pos<32);return queue[pos++];}
#define buttons next_button()
static unsigned int board_get_buttons(void){return 0;}
static unsigned int emulation_is_qd(void){return mode==1;}
static unsigned int emulation_is_apple2(void){return mode==2;}
static void emulation_select(unsigned int n){mode=n;}
static void lcd_on(void){}
static void lcd_write(int x,int y,int z,const char*s){(void)x;(void)y;(void)z;assert(strlen(s)<=16);}
static void led_7seg_write_string(const char*s){assert(strlen(s)<=3);}
static void delay_ms(unsigned int n){(void)n;}
static void arena_init(void){}
static void *arena_alloc(unsigned int n){assert(n==128);return queue;}
static void flash_ff_cfg_update(void*p){assert(p==queue);writes++;}
static void update_firmware(void){updates++;longjmp(update_env,1);}
'''
menu_suffix = r'''
int main(void){
    unsigned int modes[]={1,0,2};
    for(display_type=1;display_type<=2;display_type++)
    for(unsigned int start=0;start<3;start++)
    for(unsigned int direction=1;direction<=2;direction++)
    for(unsigned int moves=0;moves<4;moves++){
        unsigned int length=0;pos=writes=updates=0;mode=modes[start];
        for(unsigned int i=0;i<moves;i++){queue[length++]=0;queue[length++]=direction;queue[length++]=0;}
        queue[length++]=0;queue[length++]=B_SELECT;queue[length++]=0;
        unsigned int dest=(start+(direction==B_LEFT?3:1)*moves)%4;
        if(!setjmp(update_env)){boot_emulation_menu();assert(dest!=3);}
        if(dest==3)assert(updates==1 && writes==0);
        else assert(!updates && writes==1 && mode==modes[dest] && ff_cfg.boot_emulation==mode && display_mode==DM_normal);
        assert(pos==length);
    }
    puts("Apple II: boot menu all modes, both directions/wrap, OLED/LED, persistence request and update passed");
}
'''
(work/'menu.c').write_text(menu_prefix+function('src/main.c','boot_emulation_menu')+menu_suffix)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(work/'menu.c'),'-o',str(work/'menu')],check=True)
subprocess.run([str(work/'menu')],check=True)

# Actual mode-specific image catalog and selector filter, with only handlers mocked.
image = (root/'src/image/image.c').read_text()
tables = image[image.index('const struct image_type image_type[]'):image.index('#elif TARGET == TARGET_apple2')]
handlers = sorted(set(re.findall(r'&(\w+_image_handler)', tables)))
image_prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include <stdio.h>
typedef unsigned int bool_t;
#define TARGET 7
#define TARGET_dual 7
#define TARGET_shugart 4
#define TRUE 1
#define FALSE 0
#define AM_DIR 16
#define HOST_acorn 1
static struct {unsigned int fdd_host;} ff_cfg;
static unsigned int mode;
static bool_t emulation_is_qd(void){return mode==1;}
static bool_t emulation_is_apple2(void){return mode==2;}
struct image_handler {unsigned int dummy;};
/* IMAGE_TYPE_FROM_HEADER */
typedef struct {const char *fname;unsigned int fsize,fattrib;} FILINFO;
static void filename_extension(const char *name,char *ext,unsigned int n){
    const char *p=strrchr(name,'.');unsigned int i=0;
    if(p)while(*++p && i+1<n)ext[i++]=tolower((unsigned char)*p);
    ext[i]=0;
}
'''
image_prefix = image_prefix.replace('/* IMAGE_TYPE_FROM_HEADER */',
    re.search(r'struct image_type \{.*?\}', (root/'inc/floppy.h').read_text(), re.S).group(0)+';')
image_suffix = r'''
int main(void){
    const char *names[]={"disk.HFE","disk.dsk","disk.qd","disk.mzq","disk.qdf","disk.do","disk.po","disk.adf","disk.v9t9","disk.V9T9"};
    for(mode=0;mode<3;mode++)for(unsigned int i=0;i<10;i++){
        FILINFO f={names[i],11264,0};
        unsigned int expected=mode==2?i==0:mode==1?(i>=2 && i<=4):(i==0 || i==1 || i>=7);
        assert(image_valid(&f)==expected);
        f.fsize=0;assert(!image_valid(&f));f.fsize=11264;f.fattrib=AM_DIR;assert(!image_valid(&f));
    }
    puts("Apple II: HFE-only catalog; FDD/QD filters and v9t9/V9T9 with actual ext[8] passed");
}
'''
(work/'images.c').write_text(image_prefix+'\n'.join('const struct image_handler '+name+'={0};' for name in handlers)+'\n'+tables+function('src/image/image.c','image_valid')+image_suffix)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(work/'images.c'),'-o',str(work/'images')],check=True)
subprocess.run([str(work/'images')],check=True)

irq_prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define DUAL_FDD 1
#define MCU 1
#define MCU_stm32f105 1
#define DMA1_CH2_IRQ 12
#define DMA1_CH3_IRQ 13
#define SOFTIRQ_0 43
static unsigned int apple;
static unsigned int emulation_is_apple2(void){return apple;}
static const struct exti_irq {uint8_t irq,pri;uint16_t pr_mask;} exti_irqs[]={
    {27,1,0},{6,1,1},{7,2,2},{23,3,32},{28,4,0},{40,4,128}};
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
static struct {unsigned int pr;} reg;
#define exti (&reg)
static unsigned int enabled[64],priorities[64],pending[64];
static void IRQx_set_prio(unsigned int i,unsigned int p){priorities[i]=p;}
static void IRQx_clear_pending(unsigned int i){pending[i]=0;}
static void IRQx_set_pending(unsigned int i){pending[i]=1;}
static void IRQx_enable(unsigned int i){enabled[i]++;}
'''
irq_suffix = r'''
int main(void){
    for(apple=0;apple<=1;apple++){
        for(unsigned int i=0;i<64;i++)enabled[i]=priorities[i]=pending[i]=0;
        uint32_t v[84]={0};backend_bind_irqs(v);floppy_init_irqs();
        assert(v[16+27]==(apple?1027:0));assert(v[16+28]==1028);
        assert(enabled[27]==apple && pending[27]==apple);
        assert(enabled[28]==!apple && pending[28]==!apple);
        assert(enabled[6]==1 && enabled[7]==1 && enabled[23]==1 && enabled[40]==1);
    }
    puts("Apple II: actual vector binding/IRQ init isolates capture IRQ27 and Shugart STEP IRQ28");
}
'''
irq_defines = '\n'.join(f'#define IRQ_{i} {1000+i}' for i in [6,7,10,12,13,23,27,28,40,43,57,58,85])
(work/'irqs.c').write_text(irq_prefix+irq_defines+'\n'+function('src/emulation_backend.c','backend_bind_irqs')+function('src/floppy_generic.c','floppy_init_irqs')+irq_suffix)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(work/'irqs.c'),'-o',str(work/'irqs')],check=True)
subprocess.run([str(work/'irqs')],check=True)

board_prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define TARGET 7
#define TARGET_dual 7
#define TARGET_bootloader 1
#define TARGET_apple2 5
#define LEVEL 1
#define LEVEL_debug 2
#define MCU_QFN32 1
#define MCU_LQFP64 2
#define BRDREV_Gotek_standard 0
static unsigned int apple,mcu_package,board_id,has_kc30_header,kc30_sel_pin=6;
static struct gpio {unsigned int idr;} a,b,c,kc;
#define gpioa (&a)
#define gpiob (&b)
#define gpioc (&c)
static struct gpio *kc30_sel_gpio=&kc;
static unsigned int configured;
static unsigned int emulation_is_apple2(void){return apple;}
static unsigned int _rbit32(unsigned int n){unsigned int r=0;for(unsigned int i=0;i<32;i++){r=(r<<1)|(n&1);n>>=1;}return r;}
static void gpio_configure_pin(struct gpio*g,unsigned int p,unsigned int mode){
    assert((g==gpioa && p==9)||(g==gpiob && p==1));assert(mode==123);configured++;
}
'''
board_suffix = r'''
int main(void){
    for(apple=0;apple<=1;apple++)for(mcu_package=1;mcu_package<=2;mcu_package++){
        a.idr=b.idr=c.idr=kc.idr=~0u;has_kc30_header=2;configured=0;
        assert(board_get_buttons()==0);
        a.idr&=~(1u<<10);assert(board_get_buttons()==(mcu_package==1 && !apple?4u:0u));
        a.idr&=~(1u<<5);assert(board_get_buttons()==4);
        board_jc_set_mode(123);assert(configured==!(apple && mcu_package==1));
    }
    puts("Apple II: QFN32 PA10 phase ignored as SELECT, PA5 works, PA9 JC is protected");
}
'''
(work/'board.c').write_text(board_prefix+function('src/gotek/board.c','board_get_buttons')+function('src/gotek/board.c','board_jc_set_mode')+board_suffix)
subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-sign-compare','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(work/'board.c'),'-o',str(work/'board')],check=True)
subprocess.run([str(work/'board')],check=True)
