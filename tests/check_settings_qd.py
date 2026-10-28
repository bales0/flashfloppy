from pathlib import Path
import re, subprocess

root=Path(__file__).resolve().parents[1]
work=root/'out/settings-tests'
work.mkdir(exist_ok=True)
def function(path,name):
    text=(root/path).read_text()
    match=re.search(r'^(?:static )?[^\n;]+\b'+name+r'\([^;]*?\)\n\{',text,re.M)
    assert match,name
    start=match.start(); i=match.end(); depth=1
    while depth:
        if text[i]=='{': depth+=1
        elif text[i]=='}': depth-=1
        i+=1
    return text[start:i]+'\n'

# Compile the actual Flash implementation; widen only host pointer casts.
(work/'flash_cfg_under_test.c').write_text((root/'src/flash_cfg.c').read_text().replace('(uint32_t)', '(uintptr_t)'))
(work/'ff_cfg_defaults.h').write_text('''x(step-volume,step_volume,10)
x(qd-motor-volume,qd_motor_volume,10)
x(notify-volume,notify_volume,3)
x(oled-contrast,oled_contrast,OLED_CONTRAST(6))
x(display-off-secs,display_off_secs,30)
x(fdd-interface,fdd_interface,FINTF_JC)
x(qd-ready,qd_ready,QD_READY_AUTO)
x(qd-host,qd_host,QD_HOST_SHARP)
''')
main=(root/'src/main.c').read_text()
case=re.search(r'case FFCFG_qd_ready:(.*?break;(?:\n        \})?)',main,re.S).group(1).replace('break;','')
(work/'ready_parser_under_test.c').write_text('static void ready_parser(struct opts *input) {\nstruct opts opts=*input;\n'+case+'}\n')
a=main.index('/* Runtime editing is available');b=main.index('static void noinline banner',a)
(work/'settings_menu_under_test.c').write_text(main[a:b])
ejm=main[main.index('enum {\n    EJM_header'):main.index('static uint8_t noinline eject_menu')]
(work/'eject_list_under_test.c').write_text(ejm)
control=''.join(function('src/floppy_generic.c',n) for n in ['drive_set_restart_pos','wdata_stop','wdata_start'])
control+=function('src/gotek/quickdisk.c','qd_ready_off_on_motor_off')
control+=function('src/gotek/quickdisk.c','_IRQ_MOTOR_RESET_changed')
control+=function('src/gotek/quickdisk.c','IRQ_WGATE')
control+=function('src/quickdisk.c','floppy_get_track')
(work/'qd_control_under_test.c').write_text(control)
(work/'qd_ui_under_test.c').write_text(function('src/main.c','lcd_write_track_info'))
for name in ['settings','qd_control','qd_ui']:
    exe=work/name
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-sign-compare',
                    '-Wno-old-style-declaration','-funsigned-char',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all',
                    '-g','-I'+str(work),str(root/'tests'/f'{name}_test.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

# Contract checks of the actual integration, not only the individual functions.
cfg=(root/'src/flash_cfg.c').read_text()
assert 'flash_ff_cfg_update' not in main[a:b]
assert main.index('floppy_cancel();',main.index('static int floppy_main')) < main.index('b = eject_menu(b);')
assert 'runtime_settings_base();\n    have_ff_cfg = read_ff_cfg();\n    runtime_settings_apply();' in main
assert 'runtime_setting_active(SET_step)' in main and 'runtime_setting_active(SET_timeout)' in main
assert re.search(r'#define\s+pin_motor\s+0\b', (root/'src/gotek/quickdisk.c').read_text())
for folder in ['src','inc','scripts','examples','docs']:
    for path in (root/folder).rglob('*'):
        if path.is_file() and path.suffix.lower() in ['.c','.h','.py','.cfg','.md']:
            assert not re.search(r'qd-jc|qd_jc|QD_JC|qd_roland',path.read_text()),path
assert 'settings_menu(' not in main and 'EJM_settings' not in main
assert 'switch (sel - SET_nr)' in main[a:b]
assert 'menu_wait_button' not in main[a:b]
assert 'assert_volume_connected' not in main[a:b]
print('Integration: single Main Menu, eject path, RAM-only settings and PA0 checked')

assert 'qd_progress' not in main and 'qd_active' not in main
assert not (root/'inc/qd_position.h').exists()

assert 'check_buttons();' in main[main.index('while ((f_mount'):]

# Compile actual option conversion, interface selection and config-application paths.
subprocess.run(['python3',str(root/'scripts/mk_config.py'),str(root/'examples/FF.CFG'),str(work/'backend_defaults.h')],check=True)
backend_cases=''.join(re.search(r'        case FFCFG_'+name+r':.*?break;(?:\n        \})?',main,re.S).group(0)+'\n' for name in ['fdd_interface','fdd_host','fdd_pin02','fdd_pin34','fdd_max_cyl','fdd_side_select_glitch_filter','fdd_head_settle_ms','fdd_motor_delay','fdd_chgrst','qd_host','qd_ready'])
(work/'backend_parser.c').write_text(function('src/main.c','parse_pin_str')+'static void parse_backend(FIL *file) {\nenum {\n#define x(n,o,v) FFCFG_##o,\n#include "backend_defaults.h"\n#undef x\nFFCFG_nr};\nstatic const char names[]=\n#define x(n,o,v) #n "\\0"\n#include "backend_defaults.h"\n#undef x\n;\nchar arg[64];struct opts opts={.file=file,.opts=names,.nr=FFCFG_nr,.arg=arg,.argmax=sizeof(arg)};int option;\nwhile ((option=get_next_opt(&opts))!=-1) switch(option) {\n'+backend_cases+'}\n}\n')
floppy=(root/'src/floppy.c').read_text()
start=floppy.index('static uint8_t pin02,')
end=floppy.index('static always_inline void drive_change_pin',start)
(work/'fdd_interface.c').write_text(floppy[start:end]+function('src/floppy.c','floppy_set_fintf_mode'))
(work/'backend_apply.c').write_text(function('src/main.c','process_ff_cfg_opts'))
for target in [4,5,7]:
    exe=work/f'backend_{target}'
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-sign-compare','-Wno-old-style-declaration','-funsigned-char','-fsanitize=address,undefined','-fno-sanitize-recover=all','-g',f'-DTARGET={target}','-I'+str(work),str(root/'tests/backend_config_test.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
