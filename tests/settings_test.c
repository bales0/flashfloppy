/* Actual flash configuration and Settings menu, with simulated Flash/UI. */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>
typedef char bool_t;
typedef struct { const char *text; unsigned int pos; } FIL;
#define packed __attribute__((packed))
#define TRUE 1
#define FALSE 0
#define TARGET 7
#define TARGET_apple2 5
#define MCU 0
#define MCU_stm32f105 1
#define MCU_at32f435 4
#define FLASH_PAGE_SIZE 2048
#define SLOT_BASE ((union cfg_slot *)flash_memory)
#define BUILD_BUG_ON(x) _Static_assert(!(x), #x)
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define min(a,b) ((a)<(b)?(a):(b))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define FINTF_JC 255
static unsigned char flash_memory[FLASH_PAGE_SIZE];
static unsigned int writes, erases;
static unsigned int flash_page_size = FLASH_PAGE_SIZE;
static void printk(const char *fmt, ...) { (void)fmt; }
static uint16_t htobe16(uint16_t x) { return (x<<8)|(x>>8); }
static void fpec_init(void) {}
/* Test runner replaces hardware address casts with uintptr_t. */
static void fpec_write(const void *data, size_t len, uintptr_t address)
{ assert(address >= (uintptr_t)flash_memory && address+len <= (uintptr_t)flash_memory+sizeof(flash_memory)); memcpy((void *)address,data,len); writes++; }
static void fpec_page_erase(uintptr_t address)
{ assert(address == (uintptr_t)flash_memory); memset(flash_memory,0xff,sizeof(flash_memory)); erases++; }
#include "../inc/config.h"
static void F_read(FIL *fp,void *buf,unsigned int len,void *unused)
{ (void)unused; assert(len==1); *(char *)buf=fp->text[fp->pos]; if (fp->text[fp->pos]) fp->pos++; }
#include "../src/config.c"
#include "ready_parser_under_test.c"
#include "../src/crc.c"
#include "flash_cfg_under_test.c"

#define B_LEFT 1
#define B_RIGHT 2
#define B_SELECT 4
static const uint8_t *button_reads;
static unsigned int button_count, button_pos;
static uint8_t next_buttons(void) {
    if (!button_reads) return 0;
    assert(button_pos<button_count);
    return button_reads[button_pos++];
}
#define buttons next_buttons()
#define DT_LCD_OLED 1
#define DM_menu 1
#define DM_normal 0
static unsigned int display_type=DT_LCD_OLED,display_mode;
static unsigned int service_calls[4];
static uint8_t wait_twobutton_press(uint8_t b) { return b; }
static bool_t main_menu_confirm(const char *s) { (void)s;return TRUE; }
static void mcu_info(void) { service_calls[0]++; }
static void factory_reset(void) { service_calls[1]++; }
static void update_firmware(void) { service_calls[2]++; }
static void ff_osd_configure(void) { service_calls[3]++; }
static bool_t qd_mode;
static unsigned int hum_refresh, interface_changes, displayed;
static char last_value[17];
static void delay_ms(unsigned int n) { (void)n; }
static void lcd_write(int col,int row,int width,const char *s)
{ (void)col;(void)width; assert(strlen(s)<=16); displayed++;
  if(row==1) snprintf(last_value,sizeof(last_value),"%s",s); }
static void lcd_on(void) {}
static bool_t emulation_is_qd(void) { return qd_mode; }
static bool_t emulation_is_apple2(void) { return FALSE; }
static void speaker_motor_refresh(void) { hum_refresh++; }
static void floppy_set_fintf_mode(void) { interface_changes++; }
#include "settings_menu_under_test.c"
static struct {struct {unsigned int size;} clipboard;bool_t hxc_mode;} cfg;
#include "eject_list_under_test.c"

static void play(const uint8_t *sequence,unsigned int nr, bool_t whole, unsigned int item)
{
    uint8_t reads[128];
    unsigned int i,count=0;
    if (whole) main_menu(); else {
        for (i=0;i<nr;i++) {
            reads[count++]=0;reads[count++]=sequence[i];
            if (sequence[i]==B_SELECT) reads[count++]=0;
        }
        button_reads=reads;button_count=count;button_pos=0;
        settings_edit(item);
        assert(button_pos==button_count);
        button_reads=NULL;
    }
}
#define PLAY(seq,whole,item) play(seq,ARRAY_SIZE(seq),whole,item)

int main(void)
{
    unsigned char scratch[128];
    uint8_t before[SET_nr];
    unsigned int i,n;
    {
        const char names[]="qd-ready\0";
        char arg[32];
        const char *values[]={"standard","motor-off","jc"};
        for (i=0;i<3;i++) {
            char text[128];
            FIL file={.text=text};
            struct opts opts={.file=&file,.opts=names,.nr=1,.arg=arg,.argmax=sizeof(arg)};
            snprintf(text,sizeof(text),"qd-jc = yes\nqd-ready = %s\n",values[i]);
            assert(get_next_opt(&opts)==0);
            ready_parser(&opts);
            assert(ff_cfg.qd_ready==i);
            assert(get_next_opt(&opts)==OPT_eof);
        }
    }
    memset(flash_memory,0xff,sizeof(flash_memory));
    flash_ff_cfg_read();
    assert(ff_cfg.qd_ready == QD_READY_AUTO);
    assert(sizeof(ff_cfg)==82);
    flash_ff_cfg_update(scratch);
    n=writes;
    for (i=0;i<SET_nr;i++) {
        before[i]=*runtime_setting(i);
        runtime_setting_set(i,before[i]^1);
    }
    flash_ff_cfg_update(scratch);
    assert(writes==n && erases==0); /* Overrides alone never cause persistence. */
    ff_cfg.boot_emulation=2; /* Apple II shares the existing persistent byte. */
    flash_ff_cfg_update(scratch); /* Unrelated persistent setting. */
    assert(writes>n);
    flash_ff_cfg_read();
    assert(ff_cfg.boot_emulation==2);
    for (i=0;i<SET_nr;i++) {
        assert(!runtime_setting_active(i));
        assert(*runtime_setting(i)==before[i]);
    }
    /* Reload FF.CFG while overrides exist: new base persists, RAM override stays. */
    runtime_setting_set(SET_step,20);
    runtime_settings_base();
    ff_cfg.step_volume=7;
    runtime_settings_apply();
    assert(ff_cfg.step_volume==20);
    flash_ff_cfg_update(scratch);
    flash_ff_cfg_read();
    assert(ff_cfg.step_volume==7);

    /* Older saved numeric values/padding never become a new READY mode. */
    for (i=0;i<3;i++) {
        memset(flash_memory,0xff,sizeof(flash_memory));
        ff_cfg=dfl_ff_cfg;
        ff_cfg.size=80;
        ff_cfg.qd_ready_layout=i;
        ff_cfg.qd_ready=QD_READY_STANDARD;
        flash_ff_cfg_update(scratch);
        flash_ff_cfg_read();
        assert(ff_cfg.qd_ready==QD_READY_AUTO && ff_cfg.qd_ready_layout==255);
    }
    n=writes;
    /* Actual flat Main Menu: edit all seven values, then all service items. */
    for (qd_mode=0;qd_mode<=1;qd_mode++) {
        uint8_t nav[128],edit[SET_nr*2];
        unsigned int count=0,j;
        for (j=0;j<SET_nr;j++) {
            nav[count++]=0;nav[count++]=B_SELECT;nav[count++]=0;
            nav[count++]=0;nav[count++]=B_RIGHT;
            nav[count++]=0;nav[count++]=B_SELECT;nav[count++]=0;
            edit[j*2]=B_RIGHT;edit[j*2+1]=B_SELECT;
            nav[count++]=0;nav[count++]=B_RIGHT;
            before[j]=*runtime_setting(j);
        }
        for (j=0;j<4;j++) {
            nav[count++]=0;nav[count++]=B_SELECT;nav[count++]=0;
            nav[count++]=0;nav[count++]=B_RIGHT;
        }
        nav[count++]=0;nav[count++]=B_SELECT;nav[count++]=0;
        button_reads=nav;button_count=count;button_pos=0;
        PLAY(edit,TRUE,0);
        assert(button_pos==button_count && display_mode==DM_normal);
        button_reads=NULL;
        for (j=0;j<SET_nr;j++) assert(*runtime_setting(j)!=before[j]);
    }
    for (i=0;i<4;i++) assert(service_calls[i]==2);
    hum_refresh=interface_changes=0;
    qd_mode=0;
    {
        const uint8_t adjust[]={B_RIGHT,B_SELECT};
        ff_cfg.notify_volume=NOTIFY_slotnr|3;
        PLAY(adjust,FALSE,SET_notify);
        assert(ff_cfg.notify_volume==(NOTIFY_slotnr|4));
        ff_cfg.qd_motor_volume=0;
        PLAY(adjust,FALSE,SET_motor);
        assert(ff_cfg.qd_motor_volume==1 && hum_refresh==1);
        ff_cfg.fdd_interface=FINTF_JC;
        PLAY(adjust,FALSE,SET_interface);
        assert(ff_cfg.fdd_interface==0 && interface_changes);
        qd_mode=1;
        i=interface_changes;
        PLAY(adjust,FALSE,SET_interface);
        assert(interface_changes==i);
    }
    /* Bounds and special values remain reachable with the shared editor. */
    {
        const uint8_t left[]={B_LEFT,B_SELECT},right[]={B_RIGHT,B_SELECT};
        for (i=SET_step;i<=SET_motor;i++) {
            *runtime_setting(i)=0;PLAY(left,FALSE,i);assert(*runtime_setting(i)==20);
            PLAY(right,FALSE,i);assert(*runtime_setting(i)==0);
        }
        ff_cfg.notify_volume=NOTIFY_slotnr;PLAY(left,FALSE,SET_notify);
        assert(ff_cfg.notify_volume==(NOTIFY_slotnr|NOTIFY_volume_mask));
        ff_cfg.oled_contrast=0;PLAY(left,FALSE,SET_contrast);assert(ff_cfg.oled_contrast==255);
        PLAY(right,FALSE,SET_contrast);assert(ff_cfg.oled_contrast==0);
        ff_cfg.display_off_secs=0;PLAY(left,FALSE,SET_timeout);assert(ff_cfg.display_off_secs==255);
        PLAY(left,FALSE,SET_timeout);assert(ff_cfg.display_off_secs==254);
        ff_cfg.fdd_interface=0;PLAY(left,FALSE,SET_interface);assert(ff_cfg.fdd_interface==FINTF_JC);
        ff_cfg.qd_ready=0;PLAY(left,FALSE,SET_ready);assert(ff_cfg.qd_ready==QD_READY_AUTO);
        PLAY(right,FALSE,SET_ready);assert(ff_cfg.qd_ready==0);
    }
    /* Interface labels match actual on-wire enum values, not presentation order. */
    {
        const uint8_t accept[]={B_SELECT};
        const char *names[]={"Shugart","IBM PC","IBM PC + HD","Japanese PC+HD","Amiga","Japanese PC"};
        for(i=0;i<6;i++) {
            ff_cfg.fdd_interface=i;PLAY(accept,FALSE,SET_interface);
            assert(!strcmp(last_value,names[i]));
        }
    }
    /* Common FDD/Apple STEP and QD motor controls never overwrite each other. */
    {
        const uint8_t right[]={B_RIGHT,B_SELECT};
        ff_cfg.step_volume=3;ff_cfg.qd_motor_volume=11;
        PLAY(right,FALSE,SET_step);
        assert(ff_cfg.step_volume==4 && ff_cfg.qd_motor_volume==11);
        PLAY(right,FALSE,SET_motor);
        assert(ff_cfg.step_volume==4 && ff_cfg.qd_motor_volume==12);
    }
    /* Existing Eject Menu filtering, including HxC and clipboard states. */
    for (i=0;i<2;i++) for (unsigned int clip=0;clip<2;clip++) {
        uint8_t menu[EJM_nr];unsigned int count,j=0;
        cfg.hxc_mode=i;cfg.clipboard.size=clip;count=construct_eject_menu(menu)+1;
        assert(menu[j++]==EJM_header && menu[j++]==EJM_wrprot);
        if (!i) {
            assert(menu[j++]==EJM_copy);
            if (clip) assert(menu[j++]==EJM_paste);
            assert(menu[j++]==EJM_delete);
        }
        assert(menu[j++]==EJM_exit_to_selector && menu[j++]==EJM_exit_reinsert);
        assert(j==count);
    }
    display_type=0;main_menu();assert(display_mode==DM_normal);
    assert(writes==n && displayed>0);
    puts("Settings: flat Main Menu, service actions, notify flag, Flash isolation, reload/reset and old-layout checks passed");
}
