/* Real backend parser/interface/apply functions with GPIO mocked. */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
typedef char bool_t;
typedef struct {const char *text;unsigned int pos;} FIL;
#define packed __attribute__((packed))
#define TRUE 1
#define FALSE 0
#define TARGET_apple2 5
#define TARGET_dual 7
static bool_t apple;
static bool_t emulation_is_apple2(void){return TARGET==TARGET_apple2 || apple;}
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define ASSERT assert
#define m(x) (1u<<(x))
#define O_FALSE 1
#define O_TRUE 0
#define FINTF_SHUGART 0
#define FINTF_IBMPC 1
#define FINTF_IBMPC_HDOUT 2
#define FINTF_JPPC_HDOUT 3
#define FINTF_AMIGA 4
#define FINTF_JPPC 5
#define outp_dskchg 0
#define outp_rdy 4
#define outp_hden 5
#define outp_nr 6
#define outp_unused outp_nr
#include "../inc/config.h"
struct ff_cfg ff_cfg;
#if TARGET == TARGET_dual
const struct ff_cfg *fdd_cfg;
#endif
const struct ff_cfg dfl_ff_cfg={.version=FFCFG_VERSION,.size=sizeof(struct ff_cfg),
#define x(n,o,v) .o=v,
#include "backend_defaults.h"
#undef x
};
static void F_read(FIL *fp,void *buf,unsigned int len,void *unused)
{(void)unused;assert(len==1);*(char *)buf=fp->text[fp->pos];if(fp->text[fp->pos])fp->pos++;}
#include "../src/config.c"
#include "backend_parser.c"
static bool_t jc,qd;
static bool_t board_jc_strapped(void){return jc;}
static bool_t emulation_is_qd(void){return qd;}
static void IRQ_global_disable(void){}
static void IRQ_global_enable(void){}
static void printk(const char *s,...){(void)s;}
static void gpio_write_pins(int port,unsigned int pins,unsigned int value){(void)port;(void)pins;(void)value;}
#define gpioa 0
#define gpiob 1
#define pin_02 7
#define pin_34 3
static uint32_t gpio_out_active,motor_chgrst_exti_mask;
static struct {uint32_t imr;} exti_reg,*exti=&exti_reg;
struct drive {uint8_t outp;bool_t sel;} drive;
static unsigned int iface_calls,motor_calls,max_calls,rotary_calls;
static void update_SELA_irq(bool_t b){(void)b;iface_calls++;}
static void update_amiga_id(struct drive *d,bool_t b){(void)d;(void)b;}
#include "fdd_interface.c"
static void motor_chgrst_setup_exti(void){motor_calls++;}
static void floppy_set_max_cyl(void){max_calls++;}
static void set_rotary_exti(void){rotary_calls++;}
static void system_reset(void){assert(0);}
static struct {bool_t ejected;} cfg;
#include "backend_apply.c"
static void parse(const char *s){FIL file={s,0};parse_backend(&file);}
static void check_backend(void){
    struct ff_cfg before;
#if TARGET == TARGET_dual
    fdd_cfg=emulation_is_apple2()?&dfl_ff_cfg:&ff_cfg;
#endif
    ff_cfg=dfl_ff_cfg;
    parse("fdd-interface=ibmpc\nfdd-host=msx\nfdd-pin02=low\nfdd-pin34=rdy\nfdd-max-cyl=99\nfdd-side-select-glitch-filter=7\nfdd-head-settle-ms=11\nfdd-motor-delay=123\nfdd-chgrst=delay-3\nqd-host=roland\nqd-ready=auto\n");
    assert(ff_cfg.fdd_interface==FINTF_IBMPC && ff_cfg.fdd_host==HOST_msx);
    assert(ff_cfg.fdd_pin02==PIN_low && ff_cfg.fdd_pin34==PIN_rdy);
    assert(ff_cfg.fdd_max_cyl==99 && ff_cfg.fdd_side_select_glitch_filter==7);
    assert(ff_cfg.fdd_head_settle_ms==11 && ff_cfg.fdd_motor_delay==13 && ff_cfg.fdd_chgrst==3);
    assert(ff_cfg.qd_host==QD_HOST_ROLAND && ff_cfg.qd_ready==QD_READY_AUTO);
    before=ff_cfg;
    parse("interface=shugart\nhost=akai\npin02=high\npin34=low\nmax-cyl=1\nside-select-glitch-filter=0\nhead-settle-ms=0\nmotor-delay=ignore\nchgrst=step\n");
    assert(!memcmp(&before,&ff_cfg,sizeof(ff_cfg)));
    parse("qd-host=invalid\nqd-ready=invalid\n");
    assert(ff_cfg.qd_host==QD_HOST_SHARP && ff_cfg.qd_ready==QD_READY_AUTO);
    ff_cfg=dfl_ff_cfg;
    for(jc=0;jc<=1;jc++){
        ff_cfg.fdd_interface=FINTF_JC;floppy_set_fintf_mode();
        assert(fintf_mode==(emulation_is_apple2()?FINTF_SHUGART:jc?FINTF_IBMPC:FINTF_SHUGART));
        for(unsigned int mode=0;mode<=255;mode++){
            ff_cfg.fdd_interface=mode;floppy_set_fintf_mode();
            assert(fintf_mode==(emulation_is_apple2()?FINTF_SHUGART:
                               mode<ARRAY_SIZE(fintfs)?mode:
                               jc?FINTF_IBMPC:FINTF_SHUGART));
        }
    }
    if(!emulation_is_apple2()){
        ff_cfg.fdd_pin02=PIN_low;ff_cfg.fdd_pin34=PIN_rdy;
        floppy_set_fintf_mode();
        assert(pin02==outp_nr && pin02_inverted && pin34==outp_rdy && !pin34_inverted);
    }
    if(emulation_is_apple2()){
        ff_cfg.fdd_pin02=PIN_low;ff_cfg.fdd_pin34=PIN_high;
        ff_cfg.fdd_motor_delay=0;ff_cfg.fdd_chgrst=CHGRST_pa14;
        floppy_set_fintf_mode();
        assert(pin02==outp_dskchg && pin34==outp_rdy);
        assert(FDD_CFG(motor_delay)==MOTOR_ignore && FDD_CFG(chgrst)==CHGRST_step);
    }
    for(qd=0;qd<=1;qd++){
        ff_cfg=dfl_ff_cfg;before=ff_cfg;
        ff_cfg.fdd_interface=FINTF_IBMPC;ff_cfg.fdd_motor_delay=1;ff_cfg.fdd_max_cyl=1;
        iface_calls=motor_calls=max_calls=rotary_calls=0;
        process_ff_cfg_opts(&before);
        assert(rotary_calls==1);
        assert(iface_calls==(!qd && !emulation_is_apple2()));
        assert(motor_calls==iface_calls && max_calls==iface_calls);
        before=ff_cfg;ff_cfg.qd_host=QD_HOST_AKAI;ff_cfg.qd_ready=QD_READY_STANDARD;
        iface_calls=motor_calls=max_calls=rotary_calls=0;
        process_ff_cfg_opts(&before);
        assert(!iface_calls && !motor_calls && !max_calls);
    }
    puts(TARGET==TARGET_apple2?"Apple II: FDD settings ignored, fixed pins/timing and service config isolation passed":"FDD: real parser, legacy names ignored, JC/explicit interfaces and QD isolation passed");
}
int main(void){
    check_backend();
    if(TARGET==TARGET_dual){apple=1;check_backend();}
    return 0;
}
