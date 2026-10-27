#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef char bool_t;
#define TRUE 1
#define FALSE 0
#define ASSERT assert
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define AM_RDO 1
#define DT_LCD_OLED 1
#define DISPON_no 0
#define DISPON_sel 1
static int display_type=DT_LCD_OLED,lcd_columns=16,wp_column;
static struct {struct {unsigned int attributes;} slot;} cfg;
static struct {int display_on_activity;} ff_cfg;
struct track_info {uint8_t cyl,side;bool_t sel,writing,in_da_mode,qd_reading;};
static struct track_info state;
static void floppy_get_track(struct track_info *p){*p=state;}
static bool_t emulation_is_qd(void){return TRUE;}
static char shown[17];
static void lcd_write(int c,int r,int n,const char *s){(void)c;(void)r;(void)n;snprintf(shown,sizeof(shown),"%s",s);}
static void lcd_on(void){}
#include "qd_ui_under_test.c"
int main(void){
    cfg.slot.attributes=AM_RDO;lcd_write_track_info(TRUE);assert(!strcmp(shown,"*  QD"));
    state.qd_reading=TRUE;lcd_write_track_info(FALSE);assert(!strcmp(shown,"*R QD"));
    state.qd_reading=FALSE;lcd_write_track_info(FALSE);assert(!strcmp(shown,"*  QD"));
    cfg.slot.attributes=0;state.writing=TRUE;lcd_write_track_info(FALSE);assert(!strcmp(shown," W QD"));
    state.writing=FALSE;lcd_write_track_info(FALSE);assert(!strcmp(shown,"   QD"));
    puts("QD UI: read-only on mount, simultaneous */R, WRITE and idle labels passed");
}
