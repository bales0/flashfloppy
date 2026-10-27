# Universal 3.47 — nativní Apple obrazy, 27. 10. 2026

Změna vychází z `dc2247f15d7c1fb40d45d68e2032651e211feb74` ve větvi
`codex/apple2-native-formats`. Při začlenění do `main` byla verze zvýšena na
**3.47**. Obsahuje FDD, QuickDisk,
Apple II a Update FW. Starší audit s velikostí 94776 B je výchozí stav této
změny, nikoli velikost nového firmwaru.

## Podporované obrazy

Apple režim nově podporuje čtení i zápis NIB, NIC, DSK, DO a PO vedle stávajícího
HFE. Nativní formáty mají 35–40 stop:

| Přípona | Obsah jedné stopy | Pořadí / chování |
|---|---|---|
| NIB | 6656 bajtů GCR | Nibble stream, zápis se vrací do původní polohy |
| NIC | 16 bloků po 512 bajtech | Každý obsahuje 416 bajtů streamu; padding se zachovává |
| DO | 16 sektorů po 256 bajtech | DOS 3.3 |
| PO | 16 sektorů po 256 bajtech | ProDOS |
| DSK | 16 sektorů po 256 bajtech | Detekce adresáře ProDOS, jinak DOS 3.3 |

Sektorové obrazy mohou mít navíc 128bajtový Agat trailer; zápis ho nemění.
Browser filtruje neplatné délky nativních obrazů. HFE má stejný velikostní limit
1280 KiB jako aktuální upstream; jeho hlavičku dále ověřuje existující HFE parser.
Starší indexované sloty bez přípony stále mohou otevřít HFE podle hlavičky.
WOZ, 2MG a další kontejnery tato změna nepřidává.

Apple `.dsk` obsluhuje nový Apple handler pouze v Apple režimu. FDD `.dsk`
zůstává u původního FDD parseru a jeho fallbacků. QD katalog ani jeho handlery se
nemění: fyzické QD čte i zapisuje, logické QD/MZQ/QDF zůstávají read-only s `*`.
Žádné nové nastavení FF.CFG není potřeba.

## Původ a implementace

Kodek pochází z upstream [apple2.c v commitu 44a4063](https://github.com/keirf/flashfloppy/blob/44a4063/src/image/apple2.c).
Aktuální upstream `bd4242a3ec7d058beb9b124bd00e024a4f20568b` se v tomto souboru
liší následným globálním refaktorem open API. Ten není pro tento fork potřeba;
zůstává místní `bool_t open` a stávající image API.

Tři původní Apple handler struktury jsou sloučené do jedné. Formát se určí podle
přípony před společným otevřením; dekódování dat, checksumy a pořadí sektorů
zůstávají převzaté. Kontrola velikosti je společná pro browser a otevření obrazu.
Samostatný Apple build přilinkovává společný `bc_rdata_flux` z mfm.c, Universal
už ho obsahoval. Nový soubor firmwaru je pouze `src/image/apple2.c`.

Pro získání Flash se změnily ještě tyto společné části:

- Katalog přípon používá `ext[4]`; čtyřznakové `v9t9` nemá v katalogu NUL.
  Všechna porovnání proto procházejí `image_type_is`, které kontroluje délku a
  používá omezené porovnání. UI kopíruje jen tři zobrazované znaky; T99 zůstává
  zvláštní případ. Regrese pokrývá také V9T9 a odmítnutí delších přípon.
- Oba OLED fonty sdílejí slovník 16bitových sloupců s bajtovými indexy.
  Všechny původní znaky a pixely zůstávají. Plná data mají 237 sloupců;
  původních 2660 bajtů bitmap nahradí 1804 bajtů dat před zarovnáním.
  Bootloader používá vlastní menší slovník pouze pro font 6x13.
  Převod má pevný počet kroků na znak, nevyhledává ve slovníku a nepřidává
  RAM buffer. Linkovaná úspora tohoto kroku je 904 B na STM32.
- `read_ff_cfg` a `tag_open` mají přenositelné GCC atributy cold/noinline;
  jsou to parsery při načítání konfigurace/obrazu. `parse_pin_str` používá
  tabulku hodnot a existující `word_index`. Význam nastavení ověřuje původní
  golden digest 4655 případů.

IRQ, DMA, phase decoder a časování FDD/QD/Apple se v této změně neupravují.
Nebyl zvětšen limit aplikace, zmenšen buffer, odebrán formát ani zapnuto LTO.
Pokusy s plošným cold/noinline u FDD parserů a Apple helperů byly zamítnuty,
protože nepřinesly užitečnou úsporu. Atributy vyžadující `-Oz` nejsou použity.

## Flash a RAM

Debian/WSL, ARM GCC 14.2.1 20241119, GNU ld 2.44, `-Os`, bez LTO; stejné
limity jako před změnou. Měří se aplikační BIN, nikoli HEX nebo ZIP.

| Produkční Universal | Před změnou | Nyní | Nárůst | Zbývá |
|---|---:|---:|---:|---:|
| STM32F105 | 94776 B | 95908 B | 1132 B | **348 B** |
| AT32F435 | 92584 B | 93744 B | 1160 B | 117200 B |

Samotný úplný port bez následných úspor měl 97016 B a přesahoval STM32 limit
o 760 B. Následné úpravy ušetřily 1108 B, včetně přidaného filtrování velikosti.
Rezerva STM32 je malá; každé další rozšíření vyžaduje nové měření.

| MCU | .text včetně konstant | .data | .bss | .flags |
|---|---:|---:|---:|---:|
| STM32F105 | 95540 B | 368 B | 6980 B | 4 B |
| AT32F435 | 93380 B | 364 B | 7060 B | 4 B |

Statické `.data`, `.bss` a `.flags` zůstaly shodné s baseline. ARM velikost
`struct image` zůstává 856 B, `struct img_image` 76 B; Apple stav se vejde do
stávající union. Apple staging používá 8 KiB již existujícího sdíleného bufferu
(minimum alokace je 10 KiB). Nepřidává se samostatná sada image bufferů.
Tyto hodnoty neznamenají měření maximální spotřeby zásobníku při provozu.

SHA256 produkčních Universal BIN původního ověřovacího balíčku **3.46**:

- STM32F105: `7ceeea22d4f9154ce541ee5fd54c448e5b4d52a79993cbce731c2dfe30c9441c`.
- AT32F435: `700e594fc4542945c36cc6cadd0b72554e8879aa9b58dcc7654088511117ef65`.

BIN obsahuje čas sestavení; při novém buildu se může hash změnit i při stejné
velikosti. Přesné sekce, velikosti a kontrolní součty obsahuje také
`audit/final-measurements.json` v balíčku.

## Ověření a reprodukce

Kompletní `make all` sestavil 37 variant včetně obou MCU, samostatných emulací,
bootloaderů, bootloader updaterů a zvláštního Apple bootloaderu. Universal na
STM32 má stejně jako dříve pouze produkční variantu; jeho debug/logfile se do
128 KiB nevejdou. AT32 Universal prod/debug/logfile prošly.

- `check_apple2_images.py`: 17 převzatých upstream testů pro standalone Apple i
  Universal, skutečný kodek a dispatcher; nezávislé očekávané streamy/CRC,
  DOS/ProDOS, 35–40 stop, čtení, zápis, trailer, vadná pole/checksumy, NIC/NIB,
  otáčení stopy, čtení po zápisu a oddělení FDD/Apple DSK. Soubory jsou v RAM;
  tato sada neověřuje FatFS fragmentaci, HFE ani elektrické IRQ.
- `check_oled_fonts.py`: všechny původní znaky obou fontů proti bitmapovým
  hashům; skutečný renderer obou MCU, boot/plné fonty, všech 256 vstupních bajtů,
  šířky displeje, padding a ochranné bajty; ASan/UBSan.
- `check_apple2.py`: phase decoder, boot menu, katalog, IRQ binding a QFN32 piny.
- `check_config_semantics.py`: 46 klíčů FF.CFG / 4655 validních i chybných hodnot
  proti golden digestu a všech 20 indexů IMG.CFG.
- `check_upstream_fixes.py`, `check_settings_qd.py`, `check_qd_images.py`:
  předchozí opravy, HFE encoding, konfigurace, QD obrazy a read-only, UI a READY.
- `check_dual_artifacts.py`: linkované rozhraní, přímé IRQ vektory, SELECT ISR,
  HEX a limity všech podporovaných Universal variant.
- `package_universal.py`: všech 37 BIN/HEX/DFU, vložené bootloadery, verze,
  moderní update katalogy pro oba MCU, legacy STM32 update CRC, SHA256 a ZIP.

Příkazy ze základu projektu:

```sh
make all O="$PWD/out/apple-native-build"
python3 tests/check_apple2_images.py
python3 tests/check_oled_fonts.py
python3 tests/check_apple2.py
python3 tests/check_config_semantics.py
python3 tests/check_upstream_fixes.py
python3 tests/check_settings_qd.py
python3 tests/check_qd_images.py
FF_BUILD_ROOT=out/apple-native-build/out python3 tests/check_dual_artifacts.py
python3 scripts/package_universal.py out/apple-native-build/out \
  out/release-3.46-universal-apple-formats-20261027 --audit out/apple-native-audit
```

Balíček obsahuje moderní i legacy aktualizace v `alt/dual`, updater bootloaderu
v `alt/bootloader`, kombinované HEX/DFU v `variants` a měření v `audit`.
Kořenové FF.CFG je Sharp MZ-800 preset, obecné nastavení je v `examples`.
Výše uvedený balíček je původní ověřovací sestava 3.46 z pracovní větve.
Zdrojový projekt byl následně zvýšen na 3.47 a commitován do lokální `main`;
historický ZIP tím nebyl přepsán. Nový balíček musí mít v názvu 3.47 a vlastní
kontrolní součty. Změny nebyly odeslány na vzdálený repozitář.

**Elektrické časování a provoz na skutečném Apple II nejsou tímto host testem
ověřeny.** Při hardwarové zkoušce ověřit čtení, zápis, boot a formát každého
nového typu, dále FDD/QD regresi a OLED během aktivity. Úspěšný build ani
test streamu nenahrazují měření na zařízení. Omezení QFN32 SELECT/JC zůstávají
popsaná v [návodu Universal](dual-firmware.md).
