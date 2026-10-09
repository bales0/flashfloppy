# Universal 3.46: Apple II integration and validation

Date: 9 October 2026. Baseline: the completed Task 2 FDD/QD firmware,
rebuilt immediately before Task 3. Version remains 3.46.

## Architecture and changed files

`dual` still links only `floppy.o`, `quickdisk.o` and `emulation.o` as engines.
Apple II selects the existing `fdd_emulation_ops`, sharing its drive/image/DMA
state and HFE handler. No third engine, image buffer, parser or vector array
was added. Only the selected engine is initialised.

Changes for this task:

- `inc/emulation.h`, `src/emulation.c`: third boot mode, shared FDD dispatch.
- `inc/emulation_backend.h`, `src/emulation_backend.c`: direct capture IRQ27 binding.
- `inc/config.h`: Apple reads fixed defaults instead of user `fdd-*` fields.
- `inc/floppy.h`, `src/floppy_generic.c`: Apple-only capture IRQ, 1000 ns read pulses.
- `src/floppy.c`: fixed Apple interface and WRPROT polarity.
- `src/gotek/floppy.c`: original Apple phase decoder/timer and capture ISR,
  selected GPIO configuration; Shugart STEP/DIR stays in its own IRQ.
- `src/gotek/board.c`, `src/fw_update.c`: QFN32 SELECT/JC phase-pin protection,
  bootloader loads saved mode before reading buttons; debug KC30 conflicts.
- `src/image/image.c`: HFE-only Apple catalog/open path with the existing handler.
- `src/main.c`: four-item boot menu, saved mode, banner and config side-effect gating.
- `examples/FF.CFG`, `docs/dual-firmware.md`: configuration and wiring explanation.

No new firmware source files were required. Host harnesses remain in the
repository's already ignored `tests/`; generated files and packages are in `out/`.
Earlier Task 1/2 changes in the working tree are retained.

## Flash and RAM

The STM32F105 application region is 94 KiB = 96256 B, excluding bootloader
and the persistent configuration page.

| STM32F105 production dual | Baseline | Final | Change |
|---|---:|---:|---:|
| `target.bin` | 94648 B | 95756 B | +1108 B |
| Free application Flash | 1608 B | 500 B | −1108 B |
| `.text` | 94276 B | 95384 B | +1108 B |
| `.data` | 372 B | 372 B | 0 B |
| `.bss` | 7296 B | 7296 B | 0 B |
| `.flags` (reset state) | 4 B | 4 B | 0 B |
| `_ebss` | `0x20001e80` | `0x20001e80` | 0 B |

The new timer occupies 16 B and phase history 4 B. They fit the existing padding
before the 512-byte-aligned RAM vector table: total reserved static RAM does
not grow. No additional image/track buffers or full floppy states are allocated.
The dynamic arena starts at the same address. These figures do not measure
peak stack usage or prove interrupt timing on hardware.

AT32F435 production dual grows from 92476 B to 93548 B (+1072 B), leaving
117396 B of its 210944 B application budget. `.data` remains 368 B,
`.bss` 7380 B, `.flags` 4 B and `_ebss` `0x20001ed4`.

500 B is a small Flash margin (about 0.5% of the application region). No
unrelated formats, error handling or safety checks were removed. Future additions
must be measured. If more space is needed, first inspect mode-dependent config
loads and menu strings/tables; no further unrelated size changes are included.

Largest STM32F105 additions/growth (aliases share storage and must not be summed):

| Symbol | Final size | Change |
|---|---:|---:|
| `POLL_step` | 212 B | +212 B |
| `fdd_floppy_init` | 876 B | +204 B |
| `fdd_floppy_insert` | 512 B | +100 B |
| `IRQ_MOTOR_CHGRST_rotary` / `fdd_IRQ_40` | 448 B | +84 B |
| `dma_rd_handle` | 1036 B | +80 B |
| `fdd_motor_chgrst_setup_exti` | 160 B | +40 B |
| `image_open` | 312 B | +32 B |
| `apple_image_types` | 24 B | +24 B |
| `IRQ_wdata_capture` / `fdd_IRQ_27` | 20 B | +20 B |
| `backend_bind_irqs` | 104 B | +20 B |

The capture ISR is the same 20 B as standalone Apple II. The phase decoder is
the same 212 B. The Shugart STEP handler remains 280 B: it reads its own settings
directly because Apple never enables that IRQ. The critical SELECT entry stub
is compared byte for byte against the standalone FDD build by the artifact test.
Raw size/symbol reports are `out/apple2-memory-report.txt` and
`out/apple2-{stm32f105,at32f435}-symbols.txt`.

## Boot menu and configuration

SELECT held during power-on opens QuickDisk / FDD / Apple II / Update FW.
Release SELECT, choose with encoder or LEFT/RIGHT, then confirm. The existing
`boot_emulation` byte stores FDD=0, QD=1, Apple II=2. Invalid values start FDD.
Boot mode persists; Main Menu runtime setting overrides still remain RAM-only.
OLED identifies Apple mode as `FlashFloppy A2`; seven-segment boot choice is `A2`.

Apple uses global UI/filesystem/protection options, `step-volume` and meaningful
HFE/common stream settings. It ignores `fdd-*`, `qd-*` and JC interface choices.
No new `apple2-*` option is necessary. The selector exposes HFE only in Apple
mode; FDD retains HFE and its other formats, QD retains QD/MZQ/QDF. Apple and
FDD currently share `IMAGE_A.CFG`/`INIT_A.CFG`; QD uses `IMAGE_Q.CFG`/`INIT_Q.CFG`.
Logical QD formats remain unconditionally read-only; physical QD remains writable.

## Validation and its limits

Commands:

```sh
make all
python3 out/refresh_combined_activity.py
python3 tests/check_settings_qd.py
python3 tests/check_qd_images.py
python3 tests/check_apple2.py
cc -Wall -Wextra -Werror -Wno-pointer-to-int-cast tests/emulation_test.c -o out/emulation_test
out/emulation_test
cc -Wall -Wextra -Werror -Wno-pointer-to-int-cast -DMCU=4 tests/emulation_test.c -o out/emulation_test_at32
out/emulation_test_at32
python3 tests/check_dual_artifacts.py out/release-3.46-universal
```

Host checks exercise actual extracted functions with hardware mocked:

- FDD: actual parser, legacy option rejection, JC/explicit interface selection,
  fixed Apple defaults, config reconfiguration isolation and unchanged SELECT stub.
- QD: all four host/READY policies, JC independence from all FDD interfaces,
  WGATE vs USB flush, read activity/read-only UI, real physical/logical handlers,
  CRC/bitcell equivalence, random seeks/wrap, malformed records and write protection.
- Apple: original phase debounce, inward/outward stepping across all test cylinders,
  bounds, no movement mid-step, active DMA stop, direct capture polarity toggle,
  HFE-only filter, actual IRQ27 vs IRQ28 binding/enabling and QFN32 pin protection.
- Boot/UI: all initial modes, both navigation directions/wrap, OLED/LED choices,
  update action, persistence request, real Flash-config reload including mode 2,
  shared FDD dispatcher and vector alignment on both MCU variants.

Full builds cover STM32F105 and AT32F435 production/debug/logfile standalone
targets and bootloaders/updaters, production dual on STM32F105 and
production/debug/logfile dual on AT32F435, plus the special STM32 Apple bootloader.
STM dual debug/logfile builds remain excluded by the existing Flash constraint.
Combined HEX/DFU are refreshed from the final matching bootloaders. Update
catalogs, payloads, CRCs and bootloader updater payloads are checked separately.

Actual FDD STEP/DIR/read/write, QD read/write/READY timing and Apple HFE
read/write/phase stepping must still be tested on connected hardware. Host
tests and successful builds do not establish electrical/timing compatibility.

Production Apple phase pins: PA10, PA9, PB0, PA1. Debug PH0/PH1: PA6/PA15;
the conflicting KC30 rotary header is disabled after Apple selection. On QFN32,
PA10 encoder SELECT and PA9 JC are unavailable in Apple mode. Use PA5 SELECT
where present for the boot menu; LEFT+RIGHT at power-on enters recovery update.
Install the new universal bootloader as well as the application so a saved
Apple mode cannot turn a low phase input on PA10 into a false button press.
