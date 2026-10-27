"""Run upstream native Apple vectors against the actual codecs and dispatcher.

RAM-backed files exercise byte streams, not FAT or electrical IRQ timing.
"""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
work = root / 'out/apple-native-tests'
work.mkdir(parents=True, exist_ok=True)
(work/'harness.h').write_text('/* Harness supplied by apple2_image_test.c. */\n')
source = (root/'src/image/image.c').read_text()
source = source[:source.index('\nvoid image_extend(')]
(work/'apple_dispatch_under_test.c').write_text(source)
names = sorted(set(re.findall(r'extern const struct image_handler (\w+);', source))
               | {'qd_logical_image_handler'})
(work/'apple_stubs_under_test.c').write_text('\n'.join(
    'const struct image_handler '+name+'={.open=unsupported_open};'
    for name in names if name != 'apple2_image_handler'))
for target in (5, 7):
    exe = work/f'apple-images-{target}'
    subprocess.run([
        'cc', '-g', '-Wall', '-Wextra', '-Werror', '-funsigned-char',
        '-Wno-sign-compare', '-Wno-unused-parameter', '-Wno-unused-function',
        '-Wno-unused-variable', '-Wno-old-style-declaration', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', f'-DTEST_TARGET={target}', '-I'+str(work),
        str(root/'tests/apple2_image_test.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
