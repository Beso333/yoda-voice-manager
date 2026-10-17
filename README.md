# Yoda – hlasové ovládanie

A compact GTK 4 voice-control panel for Ubuntu/GNOME. Hold Right Ctrl, speak a Slovak command, and release. Speech recognition runs locally through Voxtype; optional spoken confirmations use Piper and the Lili voice.

Malý panel pre lokálne slovenské hlasové príkazy. Bez cloudového API pri rozpoznávaní a vykonávaní príkazov.

<img src="docs/preview.png" alt="Kompaktný tmavý panel Yody s kruhovým indikátorom a prepínačom hlasu" width="180">

## Ovládanie

1. Otvor Yodu ručne zo spúšťača alebo odkazu na ploche.
2. Podrž **pravý Ctrl**, povedz jeden príkaz a kláves uvoľni.
3. Yoda text prepíše, zobrazí a vykoná iba presne povolený príkaz.
4. Nesprávny prepis môžeš opraviť v poli a potvrdiť Enterom.

Voxtype je proces Yody: beží iba počas otvoreného okna. Nové nahrávanie preruší Lili. Neznámy text sa nevykoná a dva spojené príkazy sa neodhadujú.

Príklady: `otvor terminál`, `otvor súbory`, `hlasnejšie`, `tichšie`, `vypni zvuk`, `zamkni počítač`. Podporovaná je aj koncovka `prosím`.

**Celá slovenská nápoveda a zoznam fráz: [NAPOVEDA.txt](NAPOVEDA.txt).**

## Požiadavky

Overené na Ubuntu 26.04.1, GNOME 50.1/Wayland, GTK 4.22 a Voxtype 1.1.1. Iné distribúcie a verzie zatiaľ neboli overené.

- Systémový Python 3, PyGObject, Cairo a GTK 4. Na Ubuntu ide o balíky `python3-gi`, `python3-cairo` a `gir1.2-gtk-4.0`.
- [Voxtype](https://voxtype.io), nainštalovaný lokálny viacjazyčný Whisper model `small` a funkčný mikrofón.
- Prístup Voxtype ku klávesniciam cez evdev. V overenom nastavení je používateľ členom skupiny `input`; táto skupina má široký prístup k vstupným zariadeniam. Zmenu skupín urob vedome podľa nastavenia svojej distribúcie a potom sa znovu prihlás.
- Pre hlas Lili: lokálny Piper, model `sk_SK-lili-medium.onnx` s príslušným konfiguračným JSON a `mpv`. Hlasový výstup je voliteľný.
- Jednotlivé akcie vyžadujú zodpovedajúce aplikácie: GNOME Terminal, Nautilus, `wpctl`, `loginctl`; Codex/OpenCode len vtedy, ak ich príkazy chceš používať.

Projekt neobsahuje rozpoznávacie ani hlasové modely alebo binárky tretích strán. Tie si zaobstaraj od ich vydavateľov spolu s príslušnými licenčnými podmienkami.

## Inštalácia

Najprv nainštaluj a over vyššie uvedené závislosti. Inštalátor projektu nič nesťahuje, nepoužíva sudo, nemení skupiny a nezapína služby.

```bash
git clone https://github.com/Beso333/yoda-voice-manager.git
cd yoda-voice-manager
python3 install.py
```

Vytvorí `~/.local/bin/yoda-voice-manager` a položku v menu aplikácií. Existujúce odlišné súbory pred zmenou zálohuje. Príklad konfigurácie Voxtype skopíruje iba vtedy, ak konfigurácia ešte neexistuje.

Pre voliteľný odkaz na ploche zadaj svoju skutočnú cestu k ploche:

```bash
python3 install.py --desktop-dir "$HOME/Desktop"
# Pri slovenskom názve priečinka môže byť cesta napríklad "$HOME/Plocha".
```

GNOME môže pri prvom otvorení odkazu vyžadovať voľbu „Povoliť spúšťanie“.

Skontroluj `~/.config/voxtype/config.toml` podľa [voxtype.example.toml](voxtype.example.toml). Model `small` musí byť už stiahnutý. Ak máš samostatný `voxtype.service`, vypni ho pred otvorením Yody, aby o klávesnicu a mikrofón nesúťažili dva procesy.

Yoda vytvára dočasnú konfiguráciu v `$XDG_RUNTIME_DIR/voxtype/yoda-config.toml`: nastaví výstup do súboru, lokálny Whisper, štyri vlákna a optimalizáciu krátkeho zvukového kontextu. Existujúcu konfiguráciu na disku nemení. Použi čisté lokálne nastavenie bez vlastných externých hookov/postprocessingu; vlastné hooky z konfigurácie Voxtype môžu spúšťať iné programy.

## Voliteľný hlas Lili

Predvolené umiestnenia:

- Piper: program `piper` v PATH alebo `~/.local/bin/piper`.
- Model: `~/.local/share/yoda/voices/sk_SK-lili-medium.onnx`; jeho JSON patrí vedľa modelu.
- Uložený prepínač: `~/.config/yoda/output-state` (rešpektuje `XDG_CONFIG_HOME`).

Iné umiestnenia môžeš zadať pri spustení:

```bash
YODA_PIPER=/cesta/k/piper \
YODA_LILI_MODEL=/cesta/k/sk_SK-lili-medium.onnx \
~/.local/bin/yoda-voice-manager
```

Premenná `YODA_VOXTYPE` môže zmeniť predvolenú cestu `/usr/bin/voxtype`. Pre spúšťanie z menu nastav premenné vo svojej desktopovej relácii alebo uprav lokálny desktop spúšťač. Prepínač hlasu je pri novej inštalácii predvolene vypnutý.

## Testy a diagnostika

```bash
/usr/bin/python3 yoda-voice-manager --self-test
/usr/bin/python3 test_yoda.py
```

17 regresných testov nevyžaduje mikrofón ani nespúšťa skutočné desktopové akcie; používa neškodné testovacie procesy. PyGObject/GTK musia byť dostupné systémovému Pythonu.

V GNOME boli overené kompaktné rozmery 180 × 368, jediná inštancia, smerovanie lokálneho prepisu, odmietnutie neznámych fráz, otvorenie terminálu, skutočné prehrávanie Piper/mpv a zobrazenie chyby po ukončení Voxtype. Detaily a obmedzenia sú v [docs/TESTING.md](docs/TESTING.md).

- Záznam: `$XDG_RUNTIME_DIR/yoda-voxtype.log`.
- Stav: `$XDG_RUNTIME_DIR/voxtype/state`.
- Po páde Voxtype Yodu zavri a znovu otvor.
- Presnosť a rýchlosť závisia od mikrofónu, nahrávky a hardvéru. Neznámy prepis sa nevykonáva.
- Kompaktný panel používa drobné písmo; jeho aktuálna veľkosť je zámerná.

## Rozsah projektu

Ide o slovenský nástroj s pevnou sadou príkazov, nie všeobecného asistenta. Mená desktop spúšťačov Codex/OpenCode môžu na inom počítači vyžadovať úpravu v `COMMANDS`. Výsledok „úspech“ znamená úspešný návrat spúšťača/príkazu, nie overenie vnútorného stavu cudzej aplikácie.
