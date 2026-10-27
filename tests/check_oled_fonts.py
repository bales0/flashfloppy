"""Compare every packed glyph and the real renderer to the original bitmaps.
The legacy BDF converter remains an independent reference; its original hashes
also pin the expected pixels. No display hardware is simulated as verified.
"""
from pathlib import Path
import hashlib,re,subprocess
root=Path(__file__).resolve().parents[1];work=root/'out/oled-font-tests'
work.mkdir(parents=True,exist_ok=True)
golden={'6x13':'212056c6c08a55b0defcd382569fd33cd63ad09d0ebabc07e9b7edc4083db5c1',
        '8x16':'2a6c4cf6cea02abcc0aa30f4c5da708eecd6edca77c62cda656e13a8c188f728'}
for font in golden:
    name='reference_'+font
    subprocess.run(['python3',str(root/'scripts/mk_font.py'),str(root/'fonts'/(font+'.bdf')),name],cwd=work,check=True)
    data=bytes(int(n,16) for n in re.findall(r'0x([0-9a-fA-F]{2})',(work/(name+'.c')).read_text()))
    assert hashlib.sha256(data).hexdigest()==golden[font],font
subprocess.run(['python3',str(root/'scripts/mk_font.py'),'--packed',str(root/'fonts/6x13.bdf'),str(root/'fonts/8x16.bdf'),'oled_fonts'],cwd=work,check=True)
def function(path,name):
    source=path.read_text();m=re.search(r'^static void '+name+r'\([^;]*?\)\n\{',source,re.M)
    end=m.end();depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[m.start():end]+'\n'
prefix=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define aligned(x) __attribute__((aligned(x)))
#define FONT_8x16 8
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#include "reference_6x13.c"
#include "reference_8x16.c"
#include "oled_fonts.c"
static unsigned int lcd_columns,oled_font;
static struct {uint8_t before[16],pixels[256],after[16];} memory;
#define buffer memory.pixels
'''
suffix=r'''
int main(void){
    for(unsigned int which=0;which<NR_FONTS;which++){
        const uint8_t *expected_font=which?reference_8x16:reference_6x13;
        const uint8_t *indices=oled_font_6x13;
#ifdef font_extra
        if(which)indices=oled_font_8x16;
#endif
        unsigned int width=which?8:6;
        for(unsigned int ch=0;ch<95;ch++)for(unsigned int x=0;x<width;x++){
            assert(indices[ch*width+x]<ARRAY_SIZE(oled_font_columns));
            unsigned int col=oled_font_columns[indices[ch*width+x]];
            assert((col&255)==expected_font[ch*width*2+x]);
            assert((col>>8)==expected_font[ch*width*2+width+x]);
        }
        for(lcd_columns=16;lcd_columns<=21;lcd_columns+=lcd_columns==16?2:3){
            if(which && lcd_columns!=16)continue;
            for(unsigned int ch=0;ch<256;ch++){
                char text[22];uint8_t want[256];
                memset(&memory,0xa5,sizeof(memory));memset(want,0xa5,sizeof(want));
                memset(text,ch,sizeof(text));oled_font=which?FONT_8x16:7;
                unsigned int glyph=ch>=0x20 && ch<=0x7e?ch-0x20:'.'-0x20;
                unsigned int pos=width==6?1:0;
                if(width==6)want[0]=want[128]=0;
                for(unsigned int i=0;i<lcd_columns;i++,pos+=width){
                    memcpy(want+pos,expected_font+glyph*width*2,width);
                    memcpy(want+pos+128,expected_font+glyph*width*2+width,width);
                }
                if(width==6){memset(want+pos,0,128-pos);memset(want+pos+128,0,128-pos);}
                oled_convert_text_row(text);
                assert(!memcmp(want,buffer,sizeof(want)));
                for(unsigned int i=0;i<16;i++)assert(memory.before[i]==0xa5 && memory.after[i]==0xa5);
            }
        }
    }
    puts("MCU fonts EXTRA: all original glyphs, all byte inputs, narrow widths, padding and buffer guards passed");
}
'''
for mcu in ['stm32f105','at32f435']:
    for extra in [False,True]:
        code=prefix+function(root/('src/display/lcd_'+mcu+'.c'),'oled_convert_text_row')
        code+=suffix.replace('NR_FONTS','2' if extra else '1').replace('MCU',mcu).replace('EXTRA','full' if extra else 'boot')
        cfile=work/(mcu+str(extra)+'.c');cfile.write_text(code)
        exe=cfile.with_suffix('')
        subprocess.run(['cc','-Wall','-Wextra','-Werror','-funsigned-char',
                        '-fsanitize=address,undefined','-fno-sanitize-recover=all',
                        *(['-Dfont_extra=1'] if extra else []),str(cfile),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
