# Universal firmware 3.46: interface configuration and validation

Date: 9 October 2026. Baseline: Task 1 build, 3.45-dual, flat Main Menu.

This report records Task 2 before Apple II integration. For the current universal
build, sizes and Apple II boot frontend, see [Task 3 validation](universal-apple2-validation.md).

## Configuration inventory and final option table

There is one packed configuration structure, with independent FDD and QD
interface fields. No INI sections or legacy option-name aliases are added.
All current FF.CFG keys are listed below. Existing values/ranges are retained
unless described separately for QD Host/READY. The FDD prefixes change only
names, not field offsets or FDD interface meanings.

| Current key | Scope | Previous key | Compiled default |
|---|---|---|---|
| `fdd-interface` | FDD interface/host/timing | `interface` | `jc` |
| `qd-host` | QuickDisk | `new` | `sharp` |
| `qd-ready` | QuickDisk | `qd-ready` | `auto` |
| `fdd-host` | FDD interface/host/timing | `host` | `unspecified` |
| `fdd-pin02` | FDD interface/host/timing | `pin02` | `auto` |
| `fdd-pin34` | FDD interface/host/timing | `pin34` | `auto` |
| `write-protect` | Global UI/filesystem/navigation/protection | `write-protect` | `no` |
| `fdd-max-cyl` | FDD interface/host/timing | `max-cyl` | `255` |
| `fdd-side-select-glitch-filter` | FDD interface/host/timing | `side-select-glitch-filter` | `0` |
| `track-change` | Common stream policy (FDD/QD/Apple II) | `track-change` | `instant` |
| `write-drain` | Common stream policy (FDD/QD/Apple II) | `write-drain` | `instant` |
| `index-suppression` | Common stream policy (FDD/QD/Apple II) | `index-suppression` | `yes` |
| `fdd-head-settle-ms` | FDD interface/host/timing | `head-settle-ms` | `12` |
| `fdd-motor-delay` | FDD interface/host/timing | `motor-delay` | `ignore` |
| `fdd-chgrst` | FDD interface/host/timing | `chgrst` | `step` |
| `ejected-on-startup` | Global UI/filesystem/navigation/protection | `ejected-on-startup` | `no` |
| `image-on-startup` | Global UI/filesystem/navigation/protection | `image-on-startup` | `last` |
| `display-probe-ms` | Global UI/filesystem/navigation/protection | `display-probe-ms` | `3000` |
| `autoselect-file-secs` | Global UI/filesystem/navigation/protection | `autoselect-file-secs` | `2` |
| `autoselect-folder-secs` | Global UI/filesystem/navigation/protection | `autoselect-folder-secs` | `2` |
| `folder-sort` | Global UI/filesystem/navigation/protection | `folder-sort` | `always` |
| `sort-priority` | Global UI/filesystem/navigation/protection | `sort-priority` | `folders` |
| `nav-mode` | Global UI/filesystem/navigation/protection | `nav-mode` | `default` |
| `nav-loop` | Global UI/filesystem/navigation/protection | `nav-loop` | `yes` |
| `twobutton-action` | Global UI/filesystem/navigation/protection | `twobutton-action` | `zero` |
| `rotary` | Global UI/filesystem/navigation/protection | `rotary` | `full` |
| `indexed-prefix` | Global UI/filesystem/navigation/protection | `indexed-prefix` | `"DSKA"` |
| `display-type` | Global UI/filesystem/navigation/protection | `display-type` | `auto` |
| `oled-font` | Global UI/filesystem/navigation/protection | `oled-font` | `6x13` |
| `oled-contrast` | Global UI/filesystem/navigation/protection | `oled-contrast` | `143` |
| `display-order` | Global UI/filesystem/navigation/protection | `display-order` | `default` |
| `osd-display-order` | Global UI/filesystem/navigation/protection | `osd-display-order` | `default` |
| `osd-columns` | Global UI/filesystem/navigation/protection | `osd-columns` | `40` |
| `display-off-secs` | Global UI/filesystem/navigation/protection | `display-off-secs` | `60` |
| `display-on-activity` | Global UI/filesystem/navigation/protection | `display-on-activity` | `yes` |
| `display-scroll-rate` | Global UI/filesystem/navigation/protection | `display-scroll-rate` | `200` |
| `display-scroll-pause` | Global UI/filesystem/navigation/protection | `display-scroll-pause` | `2000` |
| `nav-scroll-rate` | Global UI/filesystem/navigation/protection | `nav-scroll-rate` | `80` |
| `nav-scroll-pause` | Global UI/filesystem/navigation/protection | `nav-scroll-pause` | `300` |
| `hfe-step` | HFE images (FDD/Apple II) | `hfe-step` | `0` |
| `hfe-rpm` | HFE images (FDD/Apple II) | `hfe-rpm` | `0` |
| `step-volume` | FDD + Apple II STEP sound | `step-volume` | `10` |
| `qd-motor-volume` | QuickDisk | `qd-motor-volume` | `10` |
| `notify-volume` | Global UI/filesystem/navigation/protection | `notify-volume` | `5` |
| `da-report-version` | FDD image/Direct Access feature | `da-report-version` | `""` |
| `extend-image` | FDD image/Direct Access feature | `extend-image` | `yes` |

The common stream policies remain unprefixed deliberately: actual
`floppy_generic.c` code uses them for both QD and conventional disks. They
are not FDD-only settings. HFE overrides also serve Apple II HFE images.
`extend-image` and `da-report-version` remain format-specific names, rather
than interface options. Apple II receives no fabricated apple2-* controls.

## Exact parser and READY behaviour

- Key and enum-value matching remains case-sensitive, using the existing
  compact parser. No [FDD]/[QD]/[APPLE2] parser was introduced.
- Only the nine new fdd-* option names are recognised for the renamed fields.
  Old unprefixed keys and other unknown keys are ignored. Omission/unknown
  keys leave the saved/default value unchanged; they do not reset it.
- `qd-host`: sharp (default), roland, akai, generic. Unknown values select sharp.
- `qd-ready`: auto (default), standard, motor-off, jc. Unknown values select auto.
- Auto selects motor-off for sharp/roland, standard for akai/generic.
  Explicit standard/motor-off override host and ignore JC. Explicit jc uses
  physical JC alone: open=standard, closed=motor-off.
- `fdd-interface=jc` retains open=Shugart, closed=IBM PC. Every explicit FDD
  interface ignores JC for selection. FDD choices never feed QD READY.
- Sharp/Roland requirements and Akai's standard branch are based on the
  upstream [Quick Disk documentation](https://github.com/keirf/flashfloppy/wiki/Quick-Disk)
  and existing READY control paths. No new electrical behaviour is invented.
  Hardware verification of auto on these hosts remains outstanding.

Sharp MZ QuickDisk:

```ini
qd-host = sharp
qd-ready = auto
```

Roland QuickDisk:

```ini
qd-host = roland
qd-ready = auto
```

Akai QuickDisk:

```ini
qd-host = akai
qd-ready = auto
```

Conventional FDD (independent of the above):

```ini
fdd-interface = shugart
fdd-host = unspecified
```

## Audio, runtime settings and isolation

`step-volume=0..20` controls head STEP sound in FDD and Apple II.
`qd-motor-volume=0..20` controls only the QD spindle hum. Both default to 10;
zero silences the corresponding drive sound. `notify-volume` stays global.
The separate menu labels are FDD/Apple Volume and QD Motor Volume.

Main Menu now has eight runtime controls: both drive volumes, notify volume,
OLED contrast, timeout, FDD interface, QD READY and QD host. The existing
flat service-menu path is retained; no Eject Menu Settings hierarchy returns.
Without mounted USB, briefly press/release SELECT to open Main Menu. A
three-second hold retains the existing Factory Reset behaviour.

All runtime edits remain RAM-only. Eight one-byte values and bases use the
existing override mask; no second configuration structure or image buffer.
Flash writes exclude overrides even during unrelated configuration writes.
FF.CFG reload updates the persisted base and reapplies RAM overrides; reset
restores persisted/default configuration. Existing saved field offsets and
valid READY numeric values are retained; the new QD host byte is appended.

QD ignores FDD interface/pins/motor/CHGRST/cylinder configuration, including
reconfiguration side effects in the global config load path. Apple II uses
fixed compiled interface defaults and fixed Shugart output mapping, never
user FDD or QD interface settings. It remains a standalone target; Task 3's
possible third boot backend is outside this change. QD wiring and image
read/write handlers, including logical image write protection, are unchanged.

## Size and compatibility measurement

| Production dual application | Baseline | 3.46 | Delta | Free Flash |
|---|---:|---:|---:|---:|
| STM32F105 | 94,344 B | 94,648 B | +304 B | 1,608 B |
| AT32F435 | 92,192 B | 92,476 B | +284 B | 118,468 B |

Application limits: STM32F105 96,256 B, AT32F435 210,944 B.
`arm-none-eabi-size` reports the same text deltas, zero data, and unchanged
BSS: 7,300 B / 7,384 B. `_ebss` remains 0x20001e80 / 0x20001ed4. The packed
config grows from 81 to 82 B; override arrays grow by two bytes total. These
three bytes fit existing section alignment, so reserved RAM is unchanged.
No linker-padding optimisation or extra image buffer was introduced.

A linked STM32F105 comparison added all nine legacy-name aliases using the
same parser cases. It measured 94,700 B versus 94,648 B, a cost of **52 B**.
This is a modest cost, not a large parser. The approved breaking-name policy
is retained: production includes no aliases. The audit copy is isolated in
`out/config-alias-audit/`; baseline ELF/BIN are in `out/config-split-baseline/`.

## Validation and build

Host tests execute actual production functions with simulated GPIO/Flash:

- Real option names generated from FF.CFG, actual parser case bodies, all nine
  renamed FDD fields, QD Host/READY parsing, ignored legacy names and fallback.
- Actual FDD interface selection: Shugart/IBM PC/JC and every explicit mode
  with JC open/closed, default pin mapping and manual pin configuration.
- Actual QD READY control across all four hosts, four READY modes, both JC
  states and seven FDD interface values. MOTOR OFF and RESET are exercised.
- Actual global configuration application proves no FDD reconfiguration in
  QD or Apple II and no FDD reconfiguration from QD-only changes.
- Apple II build of the actual interface function ignores user FDD values
  and uses fixed pin and motor/CHGRST defaults.
- Actual Main Menu/editor visits eight runtime settings in both dual modes,
  tests bounds and wrap, notify flags, independent volumes and service entries.
- Simulated Flash tests cover all eight override bits, unrelated writes,
  reload/reset and prior READY layouts. No menu edit persists.
- QD WGATE/drain and UI tests, physical/logical image CRC/flux/read-only tests,
  and dual dispatch tests for both MCUs pass under the existing host checks.
  Interface menu labels are checked against the actual FDD mode numbers.

`make all` builds every supported production/debug/logfile target, both
bootloaders/updaters, IO tests and the STM32F105 Apple II bootloader.
The existing STM32F105 dual debug/logfile exclusion is retained.
Combined HEX/DFU use their final matching bootloaders. Linked-engine, IRQ,
size-limit, bootloader payload, update-catalog and CRC checks all passed
before packaging. All USB packages carry version 3.46 and updated FF.CFG.

Hardware checks remain necessary: FDD read/write on Sharp, QD LOAD/SAVE/FORMAT,
Main Menu without USB, contrast and sound, reconnect preserving runtime edits,
and power-cycle restoring configuration. Host tests do not verify electrical
compatibility or real host timing.

Changed source/config files: Makefile, examples/FF.CFG, inc/config.h,
scripts/mk_config.py, src/main.c, src/flash_cfg.c, src/floppy.c,
src/gotek/board.c, src/gotek/floppy.c, src/gotek/quickdisk.c,
src/image/image.c and src/image/img.c. Documentation: docs/dual-firmware.md
and this report. Existing ignored host tests were updated; added
`tests/backend_config_test.c`. No new production source file, commit or push.
