# Universal 3.46 — cílené opravy upstreamu, 27. 10. 2026

Výchozí fork: `ca2f27daf8a17474ff429e1d1d33a25ce2223239`.
Ověřený upstream: `bd4242a3ec7d058beb9b124bd00e024a4f20568b`.
Merge-base: `822b6e3e3146c8f2856f4b65813bd781361ce5e6`.
Změny jsou v pracovní větvi `codex/upstream-fixes-flash-audit`, bez merge/rebase
celého upstreamu, bez pushování a bez nasazení na zařízení. Verze zůstává 3.46.

STM32F105: **94776 B**, **1480 B volné Flash**, proti nově sestavenému baseline
úspora **988 B**. Podrobnosti a cena každého kroku jsou v
[auditu Flash](universal-flash-audit-2026-10.md).

## Povinné opravy

| Bod / upstream | Výsledek ve forku | Test a omezení |
|---|---|---|
| P0-A [a7fc4ec55](https://github.com/keirf/flashfloppy/commit/a7fc4ec55) | `native_update()` kopíruje název přes pevný formát `%s` | Skutečná sorted větev pro `A%B 100%.dsk`, `D%x 50%`, `%s`, soubory i složky, metadata vybraného souboru; ASan/UBSan |
| P0-B [18355cb12](https://github.com/keirf/flashfloppy/commit/18355cb12) | SELA branch offset je maskovaný na 11 bitů | Skutečný patcher pro všechny sudé offsety −2048…2046 a opakovanou synchronizaci; vstupní stub zachován |
| P0-C [e14d7e874](https://github.com/keirf/flashfloppy/commit/e14d7e874) | FDD i QD odkládají rotary dekódování do IRQ40 s prioritou timeru | Skutečné WGATE/odložené handlery, opakované hrany, prázdné IRQ a tabulky priorit; elektrické souběhy vyžadují HW |
| P1-A [aeb7d5da2](https://github.com/keirf/flashfloppy/commit/aeb7d5da2) | Neplatný uložený FDD interface přejde na JC před indexací | Všech 256 hodnot, JC open/closed, standalone FDD/Apple a Universal, izolace QD |
| P1-B [3ca8a6472](https://github.com/keirf/flashfloppy/commit/3ca8a6472) | Cylinder a TRK0 se nastavují atomicky, TRK0 se i deaktivuje | Skutečná funkce pro cylindry 0…255, návrat na 0, unit 1 beze změny; mock kontroluje vypnuté IRQ a jejich obnovení |
| P1-C [2eeeb3314](https://github.com/keirf/flashfloppy/commit/2eeeb3314) | `fres` v `floppy_main()` začíná na `FR_OK` | Kontrola skutečného toku a inicializace před ejected/run větví; fyzický USB startup se stisknutým tlačítkem zbývá otestovat |
| P1-D [fec71c639](https://github.com/keirf/flashfloppy/commit/fec71c639), [92ef569aa](https://github.com/keirf/flashfloppy/commit/92ef569aa) | Sdílený `hfe_open()` kontroluje boot-selected režim před inicializací cache/seek | Všech 256 encodingů pro HFEv1/v3 a oba režimy: Apple pouze GCR1/GCR2/unknown, FDD odmítá GCR1/GCR2 |
| P1-E [2beecd765](https://github.com/keirf/flashfloppy/commit/2beecd765) | Příčina se **neuplatňuje**: fork už má `image_type.ext[8]` a `slot.type[7]`; `.v9t9` je ukončené NUL | Doplněna regrese `.v9t9`/`.V9T9` se skutečným `image_type` z hlavičky. Zbytečný upstream refaktor image API nepřevzat |

Odchylka u rotary: fork nemá upstream `xchg()`. Příznak ukládá pouze FALSE/TRUE,
proto jeho atomické vybrání a vynulování používá stávající
`cmpxchg(&rotary_changed, TRUE, FALSE)`. Hrana je publikována před pending IRQ
pomocí compiler barrier. QD používá vlastní přímý IRQ40; jeho MOTOR/RESET zůstává
na své stávající prioritě. Do vysokofrekvenčního IRQ nebyl přidán obecný dispatch.

Další doložené použití názvu souboru jako formátu se při auditu nenašlo.
Kontrola HFE nemění podporované kontejnery ani neslučuje další stavové automaty.

## Další převzaté opravy

| Upstream | Adaptace | Relevantní test |
|---|---|---|
| [de8396498](https://github.com/keirf/flashfloppy/commit/de8396498) | `osd_buttons_tx/rx` jsou volatile v hlavičce i obou LCD implementacích | Build obou MCU a všech variant, existující menu/OSD cesty |
| [bc57f8094](https://github.com/keirf/flashfloppy/commit/bc57f8094) a [984fb1fae](https://github.com/keirf/flashfloppy/commit/984fb1fae) | FF OSD nejvýše tři řádky; neexistující řádek se vyplní mezerami | Obě skutečné funkce `osd_prep_buffer()`, všech 65536 pořadí řádků, 16/21 sloupců, hlavička, obsah a konec bufferu |
| [4779cf036](https://github.com/keirf/flashfloppy/commit/4779cf036) | Přechod LED_TRACK → QUIESCENT používá cmpxchg | Skutečný 7-seg updater, injektovaný stisk těsně před atomickou operací, zachování `rd/wrt/qd` |
| [f65951a26](https://github.com/keirf/flashfloppy/commit/f65951a26) | `sv_call` a `write_special` mají memory clobber | Kompletní ARM build a inspekce kritického kódu; žádná přidaná CPU bariérová instrukce z této změny |
| [f777e9c2d](https://github.com/keirf/flashfloppy/commit/f777e9c2d) | Po opuštění prázdné složky se autoselect jednou pozastaví | Skutečný timeout blok; kladný i nulový folder timeout, image timeout. Výchozí `autoselect-folder-secs=0` zachováno |
| [6ad56d7a7](https://github.com/keirf/flashfloppy/commit/6ad56d7a7) | IMG/FM/MFM a DSK inicializují data CRC odpovídajícím DAM seedem | Skutečné `calc_start_pos()` pro všech 512 offsetů prvního datového chunku a skutečná CRC funkce |

CRC oprava je stejně jako upstream best-effort: neřeší všechny pozice v dalších
chuncích, v samotném CRC poli ani nestandardní data mark. Není to úplná změna
generátoru stopy.

## Zachované rozhraní a konfigurace

- Universal boot menu: QuickDisk / FDD / Apple II / Update FW. Jen boot mód se
  persistuje; osm Main Menu editorů zůstává v RAM včetně ochrany při config reloadu.
- Layout `ff_cfg`, `FFCFG_VERSION`, migrace QD READY a stávající offsety se nemění.
  `struct opts` je dočasný parserový popis, nikoliv perzistentní konfigurace.
- FDD Shugart/IBM/JC, pin02/pin34, STEP a Direct Access zůstávají dostupné.
- QD host Sharp/Roland/Akai/generic; auto READY = motor-off pro Sharp/Roland,
  standard pro Akai/generic. Jen `qd-ready=jc` čte fyzický JC.
- QD /MOTOR zůstává PA0 / Gotek pin 10; fyzický QD má writer, logické MZQ/QD/QDF
  zůstávají vždy read-only. OLED `*`/R/W i sedmisegmentové stavy jsou zachované.
- Apple II sdílí FDD jádro a HFE handler. PH0=PA10, PH1=PA9, PH2=PB0, PH3=PA1,
  1ms poll, obě WDATA polarity, WRPROT a 1000ns RDATA proti 400ns FDD zachovány.
  QFN32 PA9/PA10 a debug KC30 omezení se nemění.
- `FDD_CFG` v Universal používá ukazatel nastavený v `emulation_select()` před
  IRQ bindingem a inicializací. Ve FDD ukazuje na stále stejný `ff_cfg`, takže
  reload i runtime editace působí okamžitě; Apple ukazuje na pevný `dfl_ff_cfg`.
  Standalone varianty si zachovávají původní přímé makro.
- FF.CFG neobsahuje nové sekce ani aliasy. Staré neprefixované interface/host/pin
  klíče zůstávají ignorované. Optimalizovaný parser má stejný výsledek pro všech
  4655 uložených validních/nevalidních kombinací a všech 46 klíčů FF.CFG.
- IMG.CFG používá stejnou parserovou infrastrukturu; ověřeny všechny indexy
  jeho 20 klíčů, sekce, quoting, CRLF a unknown/case pravidla.
- Žádné NIB/NIC/DO/PO/Apple DSK ani nové FDD image handlery nejsou přidány.

## Reprodukce a testy

Požadavky: Debian/WSL Linux x86-64, GNU ARM toolchain, host `cc`, Python 3,
`intelhex`, `crcmod`, `srec_cat`. SELA test používá Linux `MAP_32BIT`; host C
testy běží s ASan/UBSan. Nevyžadují připojený Gotek.

```sh
make dual-stm32f105 dual-at32f435 O="$PWD/out/audit-20261027/work"
make all O="$PWD/out/audit-20261027/work"
python3 tests/check_upstream_fixes.py
python3 tests/check_config_semantics.py
python3 tests/check_settings_qd.py
python3 tests/check_qd_images.py
python3 tests/check_apple2.py
cc -Wall -Wextra -Werror -Wno-pointer-to-int-cast tests/emulation_test.c -o out/emulation_test
out/emulation_test
cc -Wall -Wextra -Werror -Wno-pointer-to-int-cast -DMCU=4 tests/emulation_test.c -o out/emulation_test_at32
out/emulation_test_at32
FF_BUILD_ROOT=out/audit-20261027/work/out python3 tests/check_dual_artifacts.py
python3 scripts/package_universal.py out/audit-20261027/work/out out/release-3.46-universal-upstream-20261027 --audit out/audit-20261027
```

Všechny uvedené testy a podporovaná matice 37 variant prošly. STM32F105 dual
debug/logfile zůstává vynechaný stávajícím Makefile. Bootloader, `bl_update`,
standalone FDD/QD/Apple, I/O testy a zvláštní STM32 Apple bootloader byly sestaveny.
Host testy byly původně lokální a ignorované. Selektivní změna `.gitignore` nyní
umožňuje verzovat pouze jejich `.py`/`.c` zdroje, nikoli cache a výstupy.

Logy: `out/audit-20261027/final-all-build.log`, `final-host-tests.log`,
`final-artifacts.log`, `baseline.json`, `final.json` a jednotlivé `steps/`.
Původní baseline zůstává oddělený, nebyl přepsán.

## HW regrese před vydáním — NEOVĚŘENO NA HW

1. Sharp QD s PA0: opakovaný LOAD/SAVE/FORMAT fyzického QD, READY/RESET/MOTOR;
   Roland/Akai/generic a všechny READY volby včetně JC open/closed.
2. Logické MZQ/legacy QD/QDF: čtení a okamžitá write protection, odmítnutí SAVE/FORMAT.
3. FDD Shugart/IBM/JC: STEP/DIR, TRK0/Direct Access, pin02/pin34, READY, čtení a
   zápis IMG/DSK/HFE, v9t9, eject/reinsert.
4. Apple II HFE: obousměrné kroky a meze, read/write, GCR/unknown přijetí a
   FM/MFM odmítnutí; WRPROT, obě WDATA hrany a RDATA pulzy osciloskopem/analyzátorem.
5. Rychlý encoder při WGATE a motor/reset událostech v každém režimu; přímé
   IRQ priority a latence na skutečném MCU, nikoli pouze simulované registry.
6. OLED 6x13/8x16, FF OSD, 7-seg, Main Menu bez USB, RAM-only editace/reload/reset,
   autoselect a prázdné složky; startup s USB a stisknutým tlačítkem.
7. Boot menu/persistence/update/recovery, nový univerzální bootloader a QFN32
   SELECT na PA5 při Apple; kontrola PA9/PA10 konfliktu.

Inspekce strojového kódu a úspěšné testy neměří elektrickou kompatibilitu,
nejhorší latenci ISR ani skutečný peak stack za provozu.
