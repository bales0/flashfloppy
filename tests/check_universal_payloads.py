"""Verify built BIN/HEX/DFU and temporary update catalogs, without a release.

Usage: python3 tests/check_universal_payloads.py BUILD_ROOT AUDIT_DIRECTORY
Uses the firmware build dependencies and creates only temporary test outputs.
"""
from pathlib import Path
import hashlib,json,re,struct,subprocess,sys,zlib
import crcmod.predefined
from intelhex import IntelHex

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
from mk_update import Catalog

build=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
version=re.search(r'^VER := (.+)$',(root/'Makefile').read_text(),re.M).group(1)

def symbols(elf):
    return {f[2]:int(f[0],16) for line in subprocess.check_output(
        ['arm-none-eabi-nm','-n',str(elf)],text=True).splitlines()
        if len(f:=line.split())==3}

def verify(directory):
    syms=symbols(directory/'target.elf');data=(directory/'target.bin').read_bytes()
    image=IntelHex(str(directory/'target.hex'))
    assert image.tobinstr(start=syms['_stext'],size=len(data))==data,directory
    if 'fw_ver' in syms:
        offset=syms['fw_ver']-syms['_stext']
        assert data[offset:offset+len(version)+1]==version.encode()+b'\0',directory
    elif directory.name=='dual':
        raise AssertionError('Universal is missing its version string')
    if directory.name not in ['bootloader','apple2-bootloader']:
        boot=IntelHex(str(directory.parent/'bootloader/target.hex'))
        assert all(image[a]==boot[a] for a in boot.addresses()),directory
    if directory.name=='bl_update':
        first=syms['update_start']-syms['_stext']
        last=syms['update_end']-syms['_stext']
        assert data[first:last]==(directory.parent/'bootloader/target.bin').read_bytes(),directory
    dfu=(directory/'target.dfu').read_bytes()
    assert dfu[:6]==b'DfuSe\1' and dfu[-8:-5]==b'UFD',directory
    assert struct.unpack_from('<I',dfu,len(dfu)-4)[0]==(zlib.crc32(dfu[:-4])^0xffffffff),directory
    assert struct.unpack_from('<I',dfu,6)[0]==len(dfu)-16,directory
    pos=11
    for _ in range(dfu[10]):
        signature,alt,named,name,length,nr=struct.unpack_from('<6sBI255s2I',dfu,pos)
        assert signature==b'Target';pos+=274;end=pos+length
        for _ in range(nr):
            address,size=struct.unpack_from('<2I',dfu,pos);pos+=8
            assert dfu[pos:pos+size]==image.tobinstr(start=address,size=size),directory
            pos+=size
        assert pos==end
    assert pos==len(dfu)-16
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

results={}
for mcu in ['stm32f105','at32f435']:
    for level in ['prod','debug','logfile']:
        for target in ['bootloader','shugart','apple2','quickdisk','dual','bl_update','io_test']:
            if mcu=='stm32f105' and target=='dual' and level!='prod':continue
            if level=='logfile' and target in ['bl_update','io_test']:continue
            directory=build/mcu/level/target
            results[str(directory.relative_to(build))]=verify(directory)
special=build/'stm32f105/prod/apple2-bootloader'
results[str(special.relative_to(build))]=verify(special)
assert len(results)==37

# These catalogs are validation fixtures in AUDIT_DIRECTORY, not release files.
for target in ['dual','bl_update','shugart','quickdisk','apple2','io_test']:
    modern=out/(target+'.upd')
    if modern.exists():modern.unlink()
    for mcu in ['stm32f105','at32f435']:
        subprocess.run([sys.executable,str(root/'scripts/mk_update.py'),'new',str(modern),
                        str(build/mcu/'prod'/target/'target.bin'),mcu],check=True)
    with modern.open('rb') as f:catalog=Catalog(f)
    assert {fw.model for fw in catalog.catalog}=={1,4}
    for fw in catalog.catalog:
        mcu='stm32f105' if fw.model==1 else 'at32f435'
        assert fw.binary[:-4]==(build/mcu/'prod'/target/'target.bin').read_bytes()
    legacy=out/(target+'-legacy.upd')
    data=build/'stm32f105/prod'/target/'target.bin'
    subprocess.run([sys.executable,str(root/'scripts/mk_update.py'),'old',str(legacy),str(data)],check=True)
    crc=crcmod.predefined.Crc('crc-ccitt-false');crc.update(legacy.read_bytes())
    assert crc.crcValue==0 and legacy.read_bytes()[:-4]==data.read_bytes()
(out/'result.json').write_text(json.dumps(results,indent=2)+'\n')
print('37 variants: BIN/HEX/DFU, boot payloads, versions, modern/legacy updates and CRCs passed; no release created')
