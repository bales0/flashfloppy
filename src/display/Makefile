OBJS += display.o
OBJS += lcd_$(mcu).o
OBJS += oled_fonts.o
OBJS += led_7seg.o

ifneq ($(target),bootloader)
lcd_$(mcu).o: CFLAGS += -Dfont_extra=1
oled_fonts.o: CFLAGS += -Dfont_extra=1
endif

oled_fonts.c: $(ROOT)/fonts/6x13.bdf $(ROOT)/fonts/8x16.bdf $(ROOT)/scripts/mk_font.py
	$(PYTHON) $(ROOT)/scripts/mk_font.py --packed $(ROOT)/fonts/6x13.bdf $(ROOT)/fonts/8x16.bdf oled_fonts
