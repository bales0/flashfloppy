# Universal 3.46 — audit Flash a SRAM, 27. 10. 2026

Výchozí zdroj `ca2f27daf8a17474ff429e1d1d33a25ce2223239`, větev změn
`codex/upstream-fixes-flash-audit`. Aktuální výsledek je pracovní diff proti
tomuto commitu, nikoli merge celého upstreamu. Referenční upstream je
`bd4242a3ec7d058beb9b124bd00e024a4f20568b`; obě vzdálené větve byly ověřeny
pomocí `git ls-remote`. Před změnami byl pracovní strom čistý.

## Toolchain, konfigurace a baseline

- Debian/WSL, `arm-none-eabi-gcc 14.2.1 20241119`, balík `15:14.2.rel1-1`.
- GNU ld `2.44`, balík `2.44-3+23+b1`; Python `3.13.5`.
- MCU STM32F105 a AT32F435, `level=prod`, `target=dual`, `-Os`, bez LTO.
- Baseline: `make dual-stm32f105 dual-at32f435 O="$PWD/out/audit-20261027/baseline"`.
- Varianty/final: stejné zdroje a toolchain kromě zaznamenaného kroku,
  `O="$PWD/out/audit-20261027/work"`. Finální `make all` prošlo.
- Aplikační limit STM32F105 **96256 B**, AT32F435 **210944 B**. Bootloader a
  persistentní stránka jsou oddělené; žádný limit ani buffer nebyl zvětšen.
- Měří se skutečný aplikační BIN a ELF sekce. HEX/ZIP nejsou měřítkem kódu.
  `.rodata` není samostatná sekce, konstanty jsou součástí `.text`.

| Produkční Universal | Baseline BIN | Finální BIN | Rozdíl | Volno |
|---|---:|---:|---:|---:|
| STM32F105 | 95764 B | 94776 B | −988 B | 1480 B |
| AT32F435 | 93552 B | 92584 B | −968 B | 118360 B |

Historických 95756 B / 500 B se tento audit netýká: skutečný čerstvě sestavený
baseline má 95764 B / 492 B. Baseline BIN/ELF a reporty zůstaly oddělené.

SHA256 přesných baseline BIN:

- STM32: `6af8141d7302b7d86f3a98d21c22ab55e261d755aab3478d6db5534260bac8e0`.
- AT32: `63a02603f77dc7c5122178ba69f71d79308de3917241d324da460f01b055cc44`.

SHA256 finálních BIN z kompletního buildu:

- STM32: `95b904ec8ca958e500d1d396c908cacc1dc6e273e124cf6373cbaa96b6e1c4ce`.
- AT32: `ce6ea991fc24fdda7cd59244a5c2050c87a7dc7862701fb57705ec02f566ea41`.

`build_info` obsahuje čas sestavení, takže při nové reprodukci může být SHA
jiné. Porovnání variant používá shodný toolchain/flags a měří velikost, ne
rovnost celé časově označené binárky.

## Měření jednotlivých kroků STM32F105

| Krok | BIN B | Δ baseline | Volno B | .text | .data | .bss |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 95764 | 0 | 492 | 95392 | 372 | 7296 |
| p0a-filename-format | 95768 | +4 | 488 | 95396 | 372 | 7296 |
| p0b-sela-offset | 95768 | +4 | 488 | 95396 | 372 | 7296 |
| p0c-rotary-priority | 95824 | +60 | 432 | 95452 | 372 | 7296 |
| p1a-invalid-interface | 95824 | +60 | 432 | 95452 | 372 | 7296 |
| p1b-direct-access-trk0 | 95852 | +88 | 404 | 95480 | 372 | 7296 |
| p1c-ejected-result | 95852 | +88 | 404 | 95480 | 372 | 7296 |
| p1d-hfe-encoding | 95884 | +120 | 372 | 95512 | 372 | 7296 |
| o1-section-alignment | 95812 | +48 | 444 | 95444 | 368 | 6980 |
| o2-shared-yes | 95708 | -56 | 548 | 95340 | 368 | 6980 |
| o3-compact-option-names | 95528 | -236 | 728 | 95160 | 368 | 6980 |
| o4-enum-maps | 95044 | -720 | 1212 | 94676 | 368 | 6980 |
| o4-list-values | 94900 | -864 | 1356 | 94532 | 368 | 6980 |
| o5-boot-config-pointer | 94664 | -1100 | 1592 | 94296 | 368 | 6980 |
| p2-osd-volatile | 94660 | -1104 | 1596 | 94292 | 368 | 6980 |
| p2-osd-rows | 94664 | -1100 | 1592 | 94296 | 368 | 6980 |
| p2-led-atomic | 94676 | -1088 | 1580 | 94308 | 368 | 6980 |
| p2-special-register-barriers | 94676 | -1088 | 1580 | 94308 | 368 | 6980 |
| p2-empty-folder | 94760 | -1004 | 1496 | 94392 | 368 | 6980 |
| p2-initial-data-crc | 94776 | -988 | 1480 | 94408 | 368 | 6980 |
| Finální make all | 94776 | −988 | 1480 | 94408 | 368 | 6980 |

Každý krok má vlastní BIN/ELF, SHA, source diff, seznam symbolů, sekce a build
log v `out/audit-20261027/steps/<krok>/`. P0/P1 prošly samostatným kompletním
buildem ještě před optimalizacemi; po každé optimalizaci parseru prošlo porovnání
výsledků proti golden digestu původního produkčního parseru.

Součet přínosných optimalizací O1–O5 je **1220 B**. Povinné opravy spotřebovaly
**120 B**, další opravy dohromady **112 B**. Výsledkem je čistá úspora **988 B**.
Čísla jsou inkrementální výsledky v uvedeném pořadí, nikoli slib stejného součtu
při libovolné kombinaci jiných kompilátorů a pořadí změn.

## Vyhodnocení O1–O7

| Varianta / reference | Měřený dopad STM32 | Rozhodnutí |
|---|---:|---|
| O1 [15470c22e](https://github.com/keirf/flashfloppy/commit/15470c22e), sort-section=alignment | −72 B | Ponecháno; SELA SRAM a zarovnání vektorů ověřeny |
| O2 [d151cd1a5](https://github.com/keirf/flashfloppy/commit/d151cd1a5), společné `yes` | −104 B | Ponecháno pro pět existujících bool voleb. `show-filename-ext` v tomto forku vůbec není; nová volba se nepřidávala |
| O3 [7eae35333](https://github.com/keirf/flashfloppy/commit/7eae35333), seznam názvů bez pointerů | −180 B | Ponecháno; FF.CFG i IMG.CFG převedeny současně; žádná nová RAM alokace |
| O4, enum mapy | −484 B | Ponecháno; neznámé hodnoty i alias hodnoty jako `akai-s950` zachovány. To nejsou nové aliasy názvů klíčů |
| O4, [7df64ece0](https://github.com/keirf/flashfloppy/commit/7df64ece0), dělení seznamů + rotary/twobutton mapy | −144 B | Ponecháno; pořadí/reverse/v2/notify slotnr i fallbacky ověřeny |
| O5, boot-selected FDD config pointer | −236 B | Ponecháno; FDD reload stále mění stejný objekt, Apple má pevné defaults, předčasné použití při board init nenalezeno |
| O6, zbylé FDD/QD duplicity | Bez změny kódu | Jen audit: u zkoumaných kritických dvojic žádná přesná shoda strojových bajtů. Není doložena bezpečná úspora dalším slučováním |
| O7, izolované konzistentní `-flto` při kompilaci/linku | Aplikační BIN nevznikl | Nepřijato: linker ztratil `_IRQ_SELA_changed` používaný assemblerovým SRAM stubem. Bez HW kontroly by LTO nebylo přijato ani po opravě symbolu |

O6: baseline dvojice IRQ_WGATE_rotary 260/324 B, DMA RDATA 264/264 B, WDATA
16/16 B, dma_rd_handle 1036/512 B, dma_wr_handle 160/160 B, rdata_stop 88/80 B,
wdata_stop 252/152 B. Stejná velikost neznamenala stejné bajty. Toto není důkaz,
že relokačně podobné úseky nikdy nelze sdílet; pouze chybí podklad pro bezpečný
refaktor, který proto nebyl proveden. Již existující `floppy_image.c` ani
sdílené FDD/Apple jádro nebyly znovu slučovány.

LTO je pouze v kopii `out/audit-20261027/lto-source` a samostatném buildu,
nikoli ve výsledném Rules.mk. Log: `lto-build.log`, výsledek `lto-result.json`.
Neprováděly se spekulativní anotace/změny ISR jen proto, aby LTO prošlo.

## SRAM, kritické vstupy a časování

| Sekce / adresa | STM baseline | STM final | AT baseline | AT final |
|---|---:|---:|---:|---:|
| `.text` | 95392 B | 94408 B | 93184 B | 92220 B |
| `.data` | 372 B | 368 B | 368 B | 364 B |
| `.bss` | 7296 B | 6980 B | 7380 B | 7060 B |
| `.flags` | 4 B | 4 B | 4 B | 4 B |
| `_ebss` | 0x20001e80 | 0x20001d44 | 0x20001ed4 | 0x20001d94 |
| RAM vektory | 0x20001400 | 0x20000a00 | 0x20001400 | 0x20000a00 |

Vektory zůstávají 512B aligned a uvnitř `.bss`. Menší mezery znamenají, že
za `_ebss` je navíc **316 B na STM32** / **320 B na AT32** pro sdílenou arénu.
Úspora `.data` neznamená ještě další nezávislý přírůstek arény, protože mezi
sekcemi je zarovnání. Nový config pointer a rotary příznak tento výsledek již
zahrnuje. Žádný další image/track buffer ani plný drive stav nepřibyl.

Dočasný `struct opts` má navíc počet klíčů; perzistentní `ff_cfg` má stále
82 B, stejné offsety a verzi. Peak stack nebyl měřen na HW; statické ELF sekce
nejsou měření nejhoršího provozního zásobníku.

Na obou MCU se porovnáním BIN/ELF potvrdilo:

- Prvních 20 B SELA entry stubu je shodných s baseline i standalone FDD.
  Maskování offsetu mění patcher, nikoliv spekulativní vstup do ISR.
- Apple WDATA capture je stejných 20 B jako baseline, bez runtime dispatch.
- STM FDD STEP handler zůstává 280 B, Apple POLL_step 212 B a 1ms timer.
- WDATA capture vector míří přímo na FDD/Apple handler; IRQ priority a
  odpovídající čtení/zápis do periferií zůstávají vybrané při bootu.
- WGATE má pouze nutné odložení encoderu; žádné obecné rozhodování o backendu
  nebo parser v hot cestě. O5 nahrazuje opakované mode testy dvěma datovými
  loady přes předem vybraný pointer, bez nového volání v ISR.

Výpisy kritických funkcí jsou v `final-<mcu>/critical-isrs.txt`. Elektrická
latence, WAIT states, nejhorší souběhy DMA/IRQ a reálný stack jsou
**NEOVĚŘENO NA HW**. Úspěšné host testy nejsou potvrzení read/write na zařízení.

## Největší symboly a podklady

| Symbol STM32F105 | Bajtů |
|---|---:|
| `dir_register` | 652 |
| `ff_cfg_opts.6` | 668 |
| `USBH_MSC_HandleBOTXfer` | 668 |
| `qd_logical_open` | 700 |
| `dsk_write_track` | 702 |
| `eject_menu.isra.0` | 736 |
| `dsk_setup_track` | 776 |
| `adf_read_track` | 784 |
| `button_timer_fn` | 784 |
| `follow_path` | 792 |
| `raw_write_track` | 824 |
| `mount_volume` | 874 |
| `fdd_floppy_init` | 876 |
| `USBH_Process` | 940 |
| `USB_OTG_Core` | 944 |
| `dma_rd_handle` | 1000 |
| `cfg` | 1060 |
| `oled_font_6x13` | 1140 |
| `raw_seek_track` | 1160 |
| `dsk_read_track` | 1360 |
| `da_read_track` | 1468 |
| `oled_font_8x16` | 1520 |
| `USBH_OTG_ISR_Handler` | 1862 |
| `lcd_init` | 1872 |
| `cfg_update` | 1976 |
| `EXC_reset` | 2084 |
| `img_open` | 2084 |
| `main` | 2084 |
| `raw_read_track` | 2144 |
| `floppy_main` | 5214 |

Aliasy `main`/`EXC_reset` nebo IRQ aliasy sdílí uložený kód a nesmí se sčítat
jako nezávislá spotřeba. Kompletní `nm -S --size-sort`, adresy a sekce jsou
uloženy pro baseline, každý krok i final; symboly s compiler suffixem se mohou
při změně zdrojů přejmenovat.

## Finální validace a další rozvoj

Kompletní podporovaná matice 37 variant včetně bootloaderů/updaterů prošla.
STM dual debug/logfile zůstává nepodporovaný stávajícím omezením. Host regrese,
oba dispatchery, konfigurace/overrides, OSD, CRC, HFE encoding, image filtry,
read-only logické QD a kritické SRAM stuby prošly; viz
[report oprav a HW checklist](universal-upstream-fixes-optimization-2026-10.md).
Balicí skript kontroluje BIN/HEX/DFU payloady, bootloaderové části, DFU CRC,
legacy/modern UPD katalogy/CRC, verze a ZIP. Jeho výstup je doplňkový log auditu.

Rezerva STM32 vzrostla z **492 B na 1480 B**. To je měřitelný přínos bez
odstranění formátů nebo funkcí, stále však nejde o velkou rezervu. Pro NIB/NIC/
Apple DSK/DO/PO nebyl napsán ani přeložen parser, proto jeho cenu ani možnost
vměstnání nelze tvrdit. Těchto 1480 B samo o sobě neprokazuje, že se plná nová
podpora vejde; případný další úkol musí začít izolovaným měřeným prototypem.
