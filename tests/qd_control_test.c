/* Real QD control functions with simulated GPIO/DMA/clock. */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define index qd_index
typedef char bool_t;
#define TRUE 1
#define FALSE 0
#define TARGET 6
#define TARGET_quickdisk 6
#define TARGET_shugart 4
#define TARGET_apple2 5
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define max_t(t,a,b) ((t)(a)>(t)(b)?(t)(a):(t)(b))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define m(x) (1u<<(x))
#define stk_ms(x) (x)
#define SAMPLECLK_MHZ 8
#define STK_MHZ 1
#define stk_sampleclk(x) ((x)/8)
#define time_t uint32_t
#define time_diff(a,b) ((int32_t)((b)-(a)))
#define time_since(x) time_diff(x,time_now())
static uint32_t now;
static uint32_t time_now(void) { return now; }
#define FLOPPY_IRQ_WGATE_PRI 2
static uint32_t IRQ_save(unsigned int p) { assert(p==2);return p; }
static void IRQ_restore(unsigned int p) { assert(p==2); }
#define IRQx_set_pending(x) ((void)(x))
enum { DMA_inactive,DMA_starting,DMA_active,DMA_stopping };
enum { WDRAIN_instant,WDRAIN_realtime,WDRAIN_eot };
enum { QD_READY_STANDARD,QD_READY_MOTOR_OFF,QD_READY_JC,QD_READY_AUTO };
#define QD_HOST_ROLAND 1
struct { uint8_t qd_ready,qd_host,fdd_interface,write_drain; } ff_cfg;
static bool_t jc;
static bool_t board_jc_strapped(void) { return jc; }
struct write { uint32_t start,dma_end; uint16_t track; };
struct image { uint32_t stk_per_rev; struct { uint32_t win_start,win_end; } qd;
    struct write write[4]; uint32_t wr_prod,wr_cons; } disk,*image=&disk;
struct dma { uint8_t state; uint16_t buf[16]; } rd,wr,*dma_rd=&rd,*dma_wr=&wr;
struct drive { struct image *image; bool_t index_suppressed;
    uint32_t restart_pos; struct { uint8_t state; } step; } drive={.image=&disk};
static struct { uint32_t prev_time; } index;
static struct { bool_t on; uint32_t timer; } motor;
static struct { bool_t paused; uint32_t pause_pos; unsigned int state; } window;
#define WIN_rdata_off 4
static struct { uint32_t ccer,cr1,egr,sr; } tim_reg;
#define tim_wdata (&tim_reg)
static struct { uint32_t cndtr; } dma_wdata={.cndtr=16};
static struct { uint32_t idr; } gpio_reg;
#define gpiob (&gpio_reg)
#define pin_wgate 1
#define pin_motor 0
#define pin_reset 1
#define HIGH 1
#define LOW 0
#define time_ms(x) (x)
static void timer_set(uint32_t *p,uint32_t t) { *p=t; }
static void timer_cancel(uint32_t *p) { *p=0; }
static void speaker_motor(bool_t on) { (void)on; }
static struct { bool_t wrprot,ready,media; } pins;
#define read_pin(x) pins.x
#define write_pin(x,v) (pins.x=(v))
#define TIM_EGR_UG 1
#define TIM_CCER_CC1E 1
#define TIM_CCER_CC1P 2
#define TIM_CR1_CEN 1
#define dma_wdata_irq 5
#define cmpxchg(p,a,b) ((void)((*(p)==(a))?(*(p)=(b)):0))
#define STEP_settling 2
static void printk(const char *s,...) { (void)s; }
static struct write *get_write(struct image *im,unsigned int n) { return &im->write[n%4]; }
static uint16_t drive_calc_track(struct drive *d) { (void)d;return 0; }
static void rdata_stop(void) { dma_rd->state=DMA_stopping; }
struct track_info { uint8_t cyl,side; bool_t sel,writing,in_da_mode,qd_reading; };
static bool_t write_active;
#include "qd_control_under_test.c"

int main(void)
{
    struct track_info ti;
    unsigned int mode,iface,drain,host;
    for (host=0;host<4;host++) for (mode=0;mode<4;mode++) for (jc=0;jc<=1;jc++) for (iface=0;iface<7;iface++) {
        ff_cfg.qd_host=host;
        ff_cfg.qd_ready=mode;ff_cfg.fdd_interface=iface;
        assert(qd_ready_off_on_motor_off()==(mode==1 || (mode==2 && jc) || (mode==3 && host<=1)));
        pins.ready=FALSE;
        _IRQ_MOTOR_RESET_changed(m(pin_reset)|m(pin_motor));
        assert(pins.ready==(mode==1 || (mode==2 && jc) || (mode==3 && host<=1)));
        pins.ready=FALSE;
        _IRQ_MOTOR_RESET_changed(0);
        assert(pins.ready);
        _IRQ_MOTOR_RESET_changed(m(pin_reset));
        assert(motor.timer==now+1000);
    }
    disk.stk_per_rev=10000;disk.qd.win_start=1000;disk.qd.win_end=9000;motor.on=TRUE;
    for (drain=0;drain<3;drain++) {
        write_active=FALSE;
        disk.wr_prod=disk.wr_cons=0;window.paused=FALSE;window.state=3;
        rd.state=DMA_active;wr.state=DMA_inactive;ff_cfg.write_drain=drain;
        pins.ready=FALSE;pins.wrprot=FALSE;gpio_reg.idr=m(pin_wgate);
        index.prev_time=100;now=2100;
        IRQ_WGATE();
        assert(write_active && disk.write[0].start==16000);
        now=5100;index.prev_time=5000; /* Disturb index: WRITE must ignore it. */
        floppy_get_track(&ti);
        assert(ti.writing && !ti.qd_reading);
        now=6100;gpio_reg.idr=0;index.prev_time=100;
        IRQ_WGATE();
        assert(!write_active);
        assert(window.paused==(drain!=WDRAIN_realtime));
        if (drain==WDRAIN_instant) assert(window.pause_pos==6000);
        if (drain==WDRAIN_eot) assert(window.pause_pos==9980);
        IRQ_WGATE(); /* Repeat OFF while drain is pending. */
        assert(drive.index_suppressed==(drain!=WDRAIN_realtime));
        now=9000;
        floppy_get_track(&ti);
        assert(!ti.writing && !ti.qd_reading);
        wr.state=DMA_inactive;rd.state=DMA_active;window.paused=FALSE;
        index.prev_time=100;
        floppy_get_track(&ti);
        assert(!ti.writing && ti.qd_reading);
        pins.ready=TRUE;floppy_get_track(&ti);assert(!ti.qd_reading);
        pins.ready=FALSE;window.paused=TRUE;
        floppy_get_track(&ti);assert(!ti.qd_reading);
        window.paused=FALSE;motor.on=FALSE;
        floppy_get_track(&ti);assert(!ti.qd_reading);
        motor.on=TRUE;pins.wrprot=TRUE;gpio_reg.idr=m(pin_wgate);
        IRQ_WGATE();assert(!write_active);
        floppy_get_track(&ti);assert(ti.qd_reading && !ti.writing);
    }
    puts("QD: READY independence, WGATE/USB flush, drain modes, read activity and write protection passed");
}
