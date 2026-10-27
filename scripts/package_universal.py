"""Package an already built Universal matrix; validate HEX/DFU/UPD payloads.

Usage: python3 scripts/package_universal.py BUILD_ROOT OUTPUT_DIRECTORY [--audit DIR]
BUILD_ROOT contains stm32f105/ and at32f435/, as in make's O=.../out.
No build, download, Git operation or device access is performed.
"""
from pathlib import Path
import argparse
import hashlib
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib

import crcmod.predefined
from intelhex import IntelHex
from mk_update import Catalog

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('build_root', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--audit', type=Path, help='include measured logs/reports, excluding build objects')
args = parser.parse_args()
build = args.build_root.resolve()
package = args.output.resolve()
version = re.search(r'^VER := (.+)$', (root/'Makefile').read_text(), re.M).group(1)
package.mkdir(parents=True, exist_ok=True)

def symbols(elf):
    result = {}
    for line in subprocess.check_output(['arm-none-eabi-nm', '-n', str(elf)], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3:
            result[fields[2]] = int(fields[0], 16)
    return result

def verify_dfu(path, image):
    data = path.read_bytes()
    assert data[:6] == b'DfuSe\1' and data[-8:-5] == b'UFD', path
    assert struct.unpack_from('<I', data, len(data)-4)[0] == (zlib.crc32(data[:-4]) ^ 0xffffffff), path
    assert struct.unpack_from('<I', data, 6)[0] == len(data)-16, path
    pos = 11
    for _ in range(data[10]):
        signature, alt, named, name, length, nr = struct.unpack_from('<6sBI255s2I', data, pos)
        assert signature == b'Target', path
        pos += 274
        end = pos+length
        for _ in range(nr):
            address, size = struct.unpack_from('<2I', data, pos); pos += 8
            assert data[pos:pos+size] == image.tobinstr(start=address, size=size), path
            pos += size
        assert pos == end, path
    assert pos == len(data)-16, path

count = 0
for mcu in ['stm32f105', 'at32f435']:
    for level in ['prod', 'debug', 'logfile']:
        for target in ['bootloader', 'shugart', 'apple2', 'quickdisk', 'dual', 'bl_update', 'io_test']:
            if mcu == 'stm32f105' and target == 'dual' and level != 'prod': continue
            if level == 'logfile' and target in ['bl_update', 'io_test']: continue
            directory = build/mcu/level/target
            syms = symbols(directory/'target.elf')
            binary = (directory/'target.bin').read_bytes()
            image = IntelHex(str(directory/'target.hex'))
            assert image.tobinstr(start=syms['_stext'], size=len(binary)) == binary, directory
            if 'fw_ver' in syms:
                off = syms['fw_ver']-syms['_stext']
                assert binary[off:off+len(version)+1] == version.encode()+b'\0', directory
            if target != 'bootloader':
                boot = IntelHex(str(build/mcu/level/'bootloader/target.hex'))
                assert all(image[a] == boot[a] for a in boot.addresses()), directory
            verify_dfu(directory/'target.dfu', image)
            dest = package/'variants'/mcu/level/target
            dest.mkdir(parents=True, exist_ok=True)
            for ext in ['bin', 'hex', 'dfu']:
                shutil.copyfile(directory/('target.'+ext), dest/('target.'+ext))
            count += 1
special = build/'stm32f105/prod/apple2-bootloader'
special_image = IntelHex(str(special/'target.hex'))
special_syms = symbols(special/'target.elf')
special_bin = (special/'target.bin').read_bytes()
assert special_image.tobinstr(start=special_syms['_stext'], size=len(special_bin)) == special_bin
verify_dfu(special/'target.dfu', special_image)
dest = package/'variants/stm32f105/prod/apple2-bootloader'; dest.mkdir(parents=True, exist_ok=True)
for ext in ['bin', 'hex', 'dfu']: shutil.copyfile(special/('target.'+ext), dest/('target.'+ext))
count += 1

for kind, target in [('dual', 'dual'), ('bootloader', 'bl_update'), ('fdd', 'shugart'),
                     ('quickdisk', 'quickdisk'), ('apple2', 'apple2'), ('io-test', 'io_test')]:
    dest = package/'alt'/kind; dest.mkdir(parents=True, exist_ok=True)
    modern = dest/f'flashfloppy-{kind}-{version}.upd'
    if modern.exists(): modern.unlink()
    for mcu in ['stm32f105', 'at32f435']:
        subprocess.run([sys.executable, str(root/'scripts/mk_update.py'), 'new', str(modern),
                        str(build/mcu/'prod'/target/'target.bin'), mcu], check=True)
    with modern.open('rb') as stream: catalog = Catalog(stream)
    assert {fw.model for fw in catalog.catalog} == {1, 4}
    for fw in catalog.catalog:
        mcu = 'stm32f105' if fw.model == 1 else 'at32f435'
        assert fw.binary[:-4] == (build/mcu/'prod'/target/'target.bin').read_bytes()
    legacy = dest/f'FF_Gotek-{kind}-{version}.upd'
    binary = build/'stm32f105/prod'/target/'target.bin'
    subprocess.run([sys.executable, str(root/'scripts/mk_update.py'), 'old', str(legacy), str(binary)], check=True)
    crc = crcmod.predefined.Crc('crc-ccitt-false'); crc.update(legacy.read_bytes())
    assert crc.crcValue == 0 and legacy.read_bytes()[:-4] == binary.read_bytes()

shutil.copytree(root/'examples', package/'examples', dirs_exist_ok=True)
cfg = (root/'examples/FF.CFG').read_text().replace('fdd-interface = jc', 'fdd-interface = shugart')
(package/'FF.CFG').write_text('# Sharp MZ-800 Universal preset.\n'+cfg)
for name in ['dual-firmware.md', 'universal-upstream-fixes-optimization-2026-10.md', 'universal-flash-audit-2026-10.md']:
    shutil.copyfile(root/'docs'/name, package/name)
shutil.copyfile(root/'COPYING', package/'COPYING')
(package/'README.txt').write_text(f'''FlashFloppy {version} Universal: FDD / QuickDisk / Apple II / Update FW.
Use alt/dual for the Universal application; alt/bootloader contains its updater.
STM32F105: FF_Gotek-*.upd. Modern flashfloppy-*.upd catalogs include both MCUs.
Put only the chosen update file on USB; install bootloader updater first if needed,
then replace it with the Universal application update. Combined HEX/DFU include both.
Standalone alternatives are kept in their own alt/ folders and variants/.
Version remains {version}; this package includes the October 27 upstream fixes.
Logical QD/MZQ/QDF remain read-only, physical QD remains read/write.
Apple II supports HFE only; encoder SELECT at power-on opens the boot menu.
Autoload: files 2 seconds, folders disabled. Runtime Main Menu settings are RAM-only.
Read both current audit reports before hardware testing. Electrical timing remains
UNVERIFIED ON HARDWARE; host tests and successful builds do not replace it.
''')
if args.audit:
    audit = args.audit.resolve()
    evidence = package/'audit'; evidence.mkdir(exist_ok=True)
    for path in audit.iterdir():
        if path.is_file() and path.suffix in ['.log', '.json', '.txt', '.diff']:
            shutil.copyfile(path, evidence/path.name)
    for folder in ['final-stm32f105', 'final-at32f435', 'steps']:
        for path in (audit/folder).rglob('*'):
            if (path.is_file() and path.suffix in ['.json', '.txt', '.log', '.diff']
                    and path.name != 'source.diff'):
                dest = evidence/path.relative_to(audit)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
files = sorted(p for p in package.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
(package/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(package))+'\n' for p in files))
shutil.make_archive(str(package), 'zip', root_dir=package.parent, base_dir=package.name)
with zipfile.ZipFile(str(package)+'.zip') as archive:
    assert archive.testzip() is None
    for p in package.rglob('*'):
        if p.is_file(): assert archive.read(str(p.relative_to(package.parent))) == p.read_bytes(), p
print(f'{count} variants, all BIN/HEX/DFU payloads, update catalogs, CRCs, versions and ZIP verified: {package}.zip')
