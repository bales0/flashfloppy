# Universal 3.47 — doplnění upstream oprav, 28. 10. 2026

Výchozí commit `5b4bdb9d680b0ce7643da62e4b059346c2465842`, čistý `master`.
Uživatel schválil pět oprav a testování a výslovně požadoval **nezakládat novou
větev**. Změny jsou proto pracovní diff přímo v `master`; bez commitu, push,
změny verze či přepsání distribučního ZIP. Verze zůstává **3.47**.

Původní referenční upstream je `bd4242a3ec7d058beb9b124bd00e024a4f20568b`.
Při auditu byl vzdálený HEAD již `9bc3ba82df2c565958cd57b289089b30e938f1d5`
(ověřeno `git -c http.sslBackend=openssl ls-remote upstream refs/heads/master`).
[Dalších 16 commitů](https://github.com/keirf/flashfloppy/compare/bd4242a3ec7d058beb9b124bd00e024a4f20568b...9bc3ba82df2c565958cd57b289089b30e938f1d5)
mění především ffemu/testy; jediná následná změna `src/image/apple2.c` mění
kontaktní e-mail autora. Opravy se převzaly jednotlivě podle původních patchů,
nikoli mergem nebo cherry-pickem celé upstream větve.

## Pět oprav

| Upstream | Změna ve forku | Ověření |
|---|---|---|
| [d2a48893f4](https://github.com/keirf/flashfloppy/commit/d2a48893f4) | Plochá bitová pole HNPTXSTS/HPTXSTS a aktualizace všech přístupů v `usb_hcd_int.c`; odstranění již nepotřebné inicializace větší union | Oba registry mají 4 B; všechny kombinace channel/token/terminate/odd-even, skutečné FIFO handlery, ARM M3/M4 accessor `ubfx … #27, #4`; staré přístupy nenalezeny |
| [0940bdc09b](https://github.com/keirf/flashfloppy/commit/0940bdc09b), [f9d02b913b](https://github.com/keirf/flashfloppy/commit/f9d02b913b) | `delay_ticks` volá `cpu_relax`; makro je čistá compiler memory barrier bez NOP | Skutečné smyčky pro STK 9/18 MHz: nula, wrap, dlouhé čekání a převody ns/us/ms; ARM assembler a test ochrany zápisů před optimalizací |
| [aa9c8bf398](https://github.com/keirf/flashfloppy/commit/aa9c8bf398) | Reset 7seg stavu přesunut z konce `run_floppy` bezprostředně za návrat `F_call_cancellable` | Normální návrat, odmítnutý mount, USB loss a backend error; skutečný `led_handle_display` nezahodí první následný stisk |
| [e136057136](https://github.com/keirf/flashfloppy/commit/e136057136) | `b = 0` ve `floppy_main`; `fres = FR_OK` zachováno | Selhání před prvním zápisem tlačítek nevytvoří `-` na LCD/OLED; normální stisk indikaci zachová |
| [fcfb426f4e](https://github.com/keirf/flashfloppy/commit/fcfb426f4e) | Vnitřní cancellable flush, zaručené `quiesce = FALSE` a propagace chyby | Skutečný `src/logfile.c` i FatFS cancellation wrapper, append/CRLF, ring overflow, chyby open/write/close a následné obnovení logování |

Změněné existující soubory jsou pouze `inc/intrinsics.h`, `src/cortex.c`,
`src/main.c`, `src/logfile.c`, `src/usb/stm32_usbh_msc/inc/usb_regs.h` a
`src/usb/stm32_usbh_msc/usb_hcd_int.c`. Doplňují je dva host testy a tento report.
Odchylka od upstreamu je pouze místní stručnější komentář u logfile wrapperu;
funkční změny odpovídají patchům.

USB stack je společný pro obě MCU a konfigurace zapíná FS core bez interního
DMA (`usb_conf.h`, `USB_OTG_SelectCore`). FIFO handlery jsou dosažitelné z
`USBH_OTG_ISR_Handler`; oprava není jen odstranění nepoužité definice.
Simulované FIFO přenosy nejsou simulací úplné USB enumerace ani fyzického
hot-plug. Tyto scénáře zůstávají v HW checklistu.

`logfile.o` se linkuje pouze pro `LEVEL_logfile`. Debug používá konzoli,
produkce logfile wrapper vůbec neobsahuje. Oprava logování proto nepřidala
produkčnímu Universal žádný bajt. Test používá skutečné `F_call_cancellable`,
`handle_fr` a `F_die`; pouze ARM stack switching nahrazuje host setjmp/longjmp.
Ověřuje i obě dostupné úrovně cancellation a předání chyby na vnější úroveň.

## Měření Flash a RAM

Čistý baseline i finální build používají Debian/WSL, ARM GCC
`14.2.1 20241119` (balík `15:14.2.rel1-1`), GNU ld `2.44` (`2.44-3+23+b1`),
`-Os`, Cortex-M3/M4, Thumb, soft float, section GC, bez LTO. Přesné flags jsou
v nezměněném `Rules.mk`. Aplikační limity zůstávají STM32 **96256 B**, AT32
**210944 B**. Tabulka měří produkční `dual/target.bin`, nikoli HEX nebo ZIP.

| Krok | STM32 BIN | Δ předchozí | STM32 volno | AT32 BIN | Δ předchozí | AT32 volno |
|---|---:|---:|---:|---:|---:|---:|
| Čistý baseline 3.47 | 95908 | — | 348 | 93744 | — | 117200 |
| USB registry | 95932 | +24 | 324 | 93772 | +28 | 117172 |
| Delay + odstranění NOP | 95916 | −16 | 340 | 93760 | −12 | 117184 |
| Displej po cancellation | 95912 | −4 | 344 | 93756 | −4 | 117188 |
| Inicializace tlačítek | 95916 | +4 | 340 | 93760 | +4 | 117184 |
| Logfile recovery | **95916** | 0 | **340** | **93760** | 0 | **117184** |

Celkem přibylo **8 B STM32 / 16 B AT32**. Žádný limit, buffer, formát ani
bezpečnostní kontrola nebyly odstraněny či změněny kvůli velikosti.

| MCU | Sekce | Baseline | Finální |
|---|---|---:|---:|
| STM32 | .text včetně konstant | 95540 | 95548 |
| STM32 | .data / .bss / .flags | 368 / 6980 / 4 | 368 / 6980 / 4 |
| STM32 | konec .bss / SRAM vektory | 0x20001d44 / 0x20000a00 | stejné |
| STM32 | produkční bootloader BIN | 29836 | 29836 |
| AT32 | .text včetně konstant | 93380 | 93396 |
| AT32 | .data / .bss / .flags | 364 / 7060 / 4 | 364 / 7060 / 4 |
| AT32 | konec .bss / SRAM vektory | 0x20001d94 / 0x20000a00 | stejné |
| AT32 | produkční bootloader BIN | 28392 | 28400 |

Statická RAM je beze změny, včetně adres a zarovnání vektorů. Neměří se tím
maximální runtime zásobník. Logfile cesta používá další vnořené cancellable
volání podle upstreamu; ostatní emulační buffery a konfigurace se nemění.
Každý krok má samostatný `measurement.json`, sekce, symboly, BIN/ELF/HEX/DFU
a build log v `out/audit-347-upstream/measurements/`.

Finální produkční BIN z kompletního buildu mají SHA256:

- STM32: `b159029842899384dbf19cd154159889a4026b1e7632fda2eaeeeb26a4850b59`.
- AT32: `c5bbda9aba5a5e04e6f0969208fe3f98b19b76ca1760cd3f8072930a47b36656`.

Čas sestavení je součástí BIN, takže další build může mít odlišný hash při
stejné velikosti. Přesné finální hodnoty jsou v `measurements/06-final/`.

## Assembler a časování

Instrukce linkované `delay_ticks` jsou u obou MCU shodné s baseline po
normalizaci absolutních adres větví. Přidaná compiler barrier nevytváří CPU
instrukci. Samostatný ARM compiler test nad skutečným tělem této funkce
ukazuje jeden zachovaný zápis bez bariéry a dva s bariérou, bez přidaného NOP.
Výstupy jsou v `out/audit-347-upstream/assembly/`.

Odstranění NOP ovlivní existující polling smyčky `cpu_relax` (startup MCU,
FPEC, SPI, konzole a čekání LCD). Nadále čekají na stejné volatile registry;
pořadí periferních operací zachovává memory clobber. Neznamená to důkaz
shodné elektrické latence. FDD/QD/Apple ISR, priority, phase decoder, DMA
backendy, SELA stub ani emulation dispatch nejsou zdrojově upraveny.
Linkované vektory a přímé ISR ověřuje `check_dual_artifacts.py`.

## Testy a buildy

Kompletní `make all` i všechny dostupné host kontroly prošly. Sestavilo se
**37 podporovaných variant**, včetně samostatných FDD/QD/Apple, AT32 Universal
prod/debug/logfile, bootloaderů/updaterů a zvláštního STM32 Apple bootloaderu.
STM32 Universal debug/logfile se nesestavují podle již existujícího Makefile;
nejde o nově vynechané cíle. Žádné AVR targety tento projekt nepoužívá.

| Příkaz | Výsledek |
|---|---|
| `python3 tests/check_universal_347_fixes.py` | PASS — skutečné USB/delay/UI/logfile části, fault injection, ASan/UBSan, ARM layout |
| `python3 tests/check_upstream_fixes.py` | PASS — předchozí opravy včetně skutečného updateru 7seg `rd/wrt/qd`, HFE a CRC |
| `python3 tests/check_config_semantics.py` | PASS — 46 klíčů FF.CFG, 4655 případů se shodným golden digestem, 20 indexů IMG.CFG |
| `python3 tests/check_settings_qd.py` | PASS — menu, RAM-only nastavení, READY, pinová/konfigurační izolace |
| `python3 tests/check_qd_images.py` | PASS — logické QD/MZQ/QDF read-only, fyzické QD se zapisovačem, zachování bajtů |
| `python3 tests/check_apple2.py` | PASS — menu, fáze, IRQ, piny, katalog a oddělení přípon |
| `python3 tests/check_apple2_images.py` | PASS — 17 nativních testů pro standalone i Universal, čtení/zápis a oddělení Apple/FDD DSK |
| `python3 tests/check_oled_fonts.py` | PASS — původní pixely obou fontů, oba MCU, boot/full renderer a ochrany bufferu |
| `make all O="$PWD/out/audit-347-upstream/final"` | PASS — všech 37 podporovaných variant |
| `FF_BUILD_ROOT=out/audit-347-upstream/final/out python3 tests/check_dual_artifacts.py` | PASS — Universal obou MCU, AT32 debug/logfile, přímé vektory a SELECT stub, vložené bootloader payloady |
| `python3 tests/check_universal_payloads.py out/audit-347-upstream/final/out out/audit-347-upstream/payload-checks` | PASS — 37 BIN/HEX/DFU, verze, bootloader segmenty, moderní katalogy obou MCU a legacy STM32 update CRC |

Logy jsou v `out/audit-347-upstream/*-tests.log` a `all-build.log`. Výsledné
produkční aplikace jsou v `final/out/stm32f105/prod/dual/` a
`final/out/at32f435/prod/dual/` pod tímto auditním adresářem.

Reprodukce čistých buildů a závěrečných kontrol:

```sh
make dual-stm32f105 dual-at32f435 O="$PWD/out/audit-347-upstream/baseline"
# Baseline se musí sestavit z čistého 5b4bdb9 PŘED aplikací změn.
make all O="$PWD/out/audit-347-upstream/final"
FF_BUILD_ROOT=out/audit-347-upstream/final/out python3 tests/check_dual_artifacts.py
python3 tests/check_universal_payloads.py out/audit-347-upstream/final/out \
  out/audit-347-upstream/payload-checks
```

Nový payload test sestaví jen dočasné kontrolní update katalogy v auditním
adresáři. Nejde o vytvoření distribučního balíčku ani GitHub release.
Stávající ZIP/UPD z dřívějších úkolů nebyly přepsány. Pro distribuci těchto
oprav bude nutné po samostatném pokynu vytvořit nový balíček 3.47 včetně
aktuálního bootloader/updater payloadu.

## Ostatní upstream rozdíly — pouze audit

| Commit / oblast | Klasifikace a závěr |
|---|---|
| [da92536be3](https://github.com/keirf/flashfloppy/commit/da92536be3) | Uživatelské vylepšení: řazení podle základu a přípony. Fork stále porovnává celé jméno v `native_dir_cmp`; mění pořadí souborů, nepřevzato. |
| [f838a6081a](https://github.com/keirf/flashfloppy/commit/f838a6081a) | Oprava/vylepšení zobrazení verze: fork v `maybe_show_version` stále ořezává segment na 3 znaky; problém hlavně dlouhých verzí a dvouciferného displeje. Pro 3.47 na 3 číslicích není kritický. Úspora se bez měření netvrdí; nepřevzato. |
| [3830b3914e](https://github.com/keirf/flashfloppy/commit/3830b3914e) | Nová funkce a FF.CFG pole `show-filename-ext`; vyžaduje širší změnu konfigurace/UI, mimo rozsah. |
| [586ef9b769](https://github.com/keirf/flashfloppy/commit/586ef9b769) | Nová diagnostická funkce `FLASH.DMP` a položka menu; fork ji nemá, nepřidána. |
| [df8ad3970f](https://github.com/keirf/flashfloppy/commit/df8ad3970f) | Refaktor sdíleného LCD driveru. Fork už má komprimované fonty a opravené OSD v obou implementacích; do jedné MCU binárky se stejně linkuje jeden driver. Méně duplicitních zdrojů nezaručuje nižší Flash; nepřevzato. |
| [d4278a8ad1](https://github.com/keirf/flashfloppy/commit/d4278a8ad1) | Host build ergonomie. Fork má explicitní `PYTHON := python3`, nikoli chybnou upstream autodetekci. Její oprava zde nemá stejný výchozí problém; bez změny. |
| ffemu, upstream harness a novějších 16 commitů | Vývojové nástroje, testy a jejich opravy; neprokazují chybějící firmware funkce a samy nespotřebují aplikační Flash. ffemu nebyl přidán. |
| [5d5a88b32f](https://github.com/keirf/flashfloppy/commit/5d5a88b32f) | Diagnostika/úspora logovacích řetězců: fork má původní `Write %d` v DSK. Možný společný literál v debug/logfile; nepřevzato. |
| [f9a77dd533](https://github.com/keirf/flashfloppy/commit/f9a77dd533) | Diagnostika: fork používá `TRC_FUNC`/`__FUNCTION__` v USB enumeraci. Kratší názvy mohou ušetřit debug/logfile Flash, nikoli řešit produkční USB chybu. Nepřevzato. |
| [caf252934d](https://github.com/keirf/flashfloppy/commit/caf252934d) | Diagnostika: kratší config/interface logy. Produkční přínos nelze předpokládat při vypnutém printk. Nepřevzato. |

## HW NEOVĚŘENO

Host fault injection nenahrazuje připojený Gotek. Před označením sestavy za
hardwarově ověřené vydání zbývá:

- USB opakované připojení/odpojení, čtení/zápis, plný a poškozený filesystem.
- FDD STEP/TRK0, JC/Shugart/IBM, Direct Access a různé zapisovatelné obrazy.
- Sharp MZ-800 QD: PA0/MOTOR, READY/RESET, LOAD/SAVE/FORMAT, rotary při WGATE,
  fyzické QD R/W a ochrana logických QD/MZQ/QDF.
- Apple II: boot/read/write HFE/NIB/NIC/DSK/DO/PO, WRPROT, fáze, polarity WDATA
  a omezení QFN32.
- LCD/OLED/7seg: odpojení během track režimu, první vadný mount a první tlačítko
  po odpojení, opětovné zasunutí USB.
- Případné měření RDATA/WDATA a IRQ latencí osciloskopem; fyzické chování
  periferních polling smyček po odstranění NOP.

FFCFG_VERSION, persistentní layout, osm RAM-only nastavení, QD READY politika,
OLED fonty, obrazové handlery i verze projektu zůstávají beze změny.
