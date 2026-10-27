"""Check linked dual images, including the original FDD SELECT ISR bytes.

Run after `make all`: python3 tests/check_dual_artifacts.py
Uses the same intelhex dependency and ARM tools as the firmware build.
"""
from pathlib import Path
import struct
import subprocess
import sys
import os

from intelhex import IntelHex

BUILD_ROOT = Path(os.environ.get('FF_BUILD_ROOT', 'out'))


def symbols(elf):
    result = {}
    output = subprocess.check_output(
        ["arm-none-eabi-nm", "-n", str(elf)], text=True)
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 3:
            result[fields[2]] = int(fields[0], 16)
    return result


def check(mcu, level):
    directory = BUILD_ROOT / mcu / level
    dual = directory / "dual"
    syms = symbols(dual / "target.elf")
    data = (dual / "target.bin").read_bytes()
    base = syms["_stext"]

    def word(address):
        return struct.unpack_from("<I", data, address - base)[0]

    def ram_code(blob, table, name, size):
        offset = table["_ldat"] - table["_stext"]
        offset += table[name] - table["_sdat"]
        return blob[offset:offset + size]

    budget = (94 if mcu == "stm32f105" else 206) * 1024
    assert len(data) <= budget, (dual, "flash overflow")
    assert word(base + 7*4) == 0x46464451, "missing boot-menu marker"
    assert word(base) == syms["_thread_stacktop"]
    assert word(base + 4) == syms["main"] | 1
    assert syms["emulation_vectors"] % 512 == 0
    assert syms["_sbss"] <= syms["emulation_vectors"]
    nr = 16 + (68 if mcu == "stm32f105" else 90)
    assert syms["emulation_vectors"] + nr*4 <= syms["_ebss"]
    assert 'apple2_emulation_ops' not in syms, 'duplicated Apple core'
    assert 'POLL_step' in syms and 'step_timer' in syms
    assert syms['fdd_IRQ_27'] == syms['IRQ_wdata_capture']
    assert 'hfe_image_handler' in syms and 'apple_image_types' in syms

    methods = ["floppy_init", "floppy_ribbon_is_reversed", "floppy_insert",
               "floppy_cancel", "floppy_handle", "floppy_set_cyl",
               "floppy_get_track", "floppy_set_fintf_mode",
               "floppy_set_max_cyl", "motor_chgrst_setup_exti"]
    for engine in ("fdd", "qd"):
        table = syms[engine + "_emulation_ops"]
        for index, method in enumerate(methods):
            expected = (0 if engine == "qd" and index == 5
                        else syms[engine + "_" + method] | 1)
            assert word(table + index*4) == expected, (engine, method)
        assert word(table + 10*4) == syms[engine + "_motor_chgrst_exti_mask"]
        for irq in (6, 7, 23, 28, 40):
            assert syms[f"fdd_IRQ_{irq}"] != syms[f"qd_IRQ_{irq}"]

    # The latency-sensitive, self-modifying FDD entry stub must stay in SRAM
    # and remain byte-for-byte equivalent to the standalone FDD implementation.
    standalone = directory / "shugart"
    old = symbols(standalone / "target.elf")
    blob = (standalone / "target.bin").read_bytes()
    assert syms["fdd_IRQ_6"] == syms["IRQ_SELA_changed"]
    assert syms["_sdat"] <= syms["fdd_IRQ_6"] < syms["_edat"]
    assert ram_code(data, syms, "fdd_IRQ_6", 20) == ram_code(
        blob, old, "IRQ_6", 20), "FDD SELECT entry stub changed"
    for handler in ['_IRQ_SELA_changed', 'Amiga_HD_ID']:
        delta = (syms[handler] & ~1) - ((syms['fdd_IRQ_6'] & ~1) + 12)
        assert -2048 <= delta <= 2046 and delta % 2 == 0, (handler, delta)

    image = IntelHex(str(dual / "target.hex"))
    assert image.tobinstr(start=base, size=len(data)) == data
    boot = IntelHex(str(directory / "bootloader" / "target.hex"))
    for address in boot.addresses():
        assert image[address] == boot[address], "combined HEX has stale bootloader"
    assert (dual / "target.dfu").is_file()
    updater = directory / "bl_update"
    if (updater / "target.elf").is_file():
        updater_syms = symbols(updater / "target.elf")
        updater_data = (updater / "target.bin").read_bytes()
        first = updater_syms["update_start"] - updater_syms["_stext"]
        last = updater_syms["update_end"] - updater_syms["_stext"]
        assert updater_data[first:last] == (directory / "bootloader" / "target.bin").read_bytes(), \
            "bootloader updater has stale payload"
    print(f"{mcu}/{level}: linked interfaces, SELECT ISR, vectors and HEX verified; "
          f"{budget - len(data)} bytes free")


def check_package(directory):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from mk_update import Catalog

    for subdir, pattern, target in (
        ("dual", "flashfloppy-dual-*.upd", "dual"),
        ("bootloader", "flashfloppy-bootloader-*.upd", "bl_update"),
    ):
        files = list((directory / "alt" / subdir).glob(pattern))
        assert len(files) == 1, (subdir, "expected one review update file")
        with files[0].open("rb") as stream:
            catalog = Catalog(stream)
        assert {fw.model for fw in catalog.catalog} == {1, 4}
        for fw in catalog.catalog:
            mcu = "stm32f105" if fw.model == 1 else "at32f435"
            current = BUILD_ROOT / mcu / "prod" / target / "target.bin"
            assert fw.binary[:-4] == current.read_bytes(), "update payload is stale"
        print(f"{files[0]}: both MCU payloads and checksums verified")


if __name__ == "__main__":
    for target in (("stm32f105", "prod"), ("at32f435", "prod"),
                   ("at32f435", "debug"), ("at32f435", "logfile")):
        check(*target)
    if len(sys.argv) > 1:
        check_package(Path(sys.argv[1]))
