# Radio Station Player

Přístupná aplikace pro přehrávání rozhlasových stanic s integrací Radio Browser API a plnou podporou pro čtečky obrazovky.

## Hlavní funkce

### Přehrávání
- Přehrávání internetových rozhlasových stanic
- Online databáze tisíců stanic z celého světa (Radio Browser API)
- Lokální přednastavené české stanice
- Přidávání vlastních rozhlasových stanic
- Ovládání hlasitosti

### Vyhledávání stanic
- Vyhledávání podle názvu stanice
- Filtrování podle země (kód země, např. CZ, US, GB)
- Filtrování podle jazyka (např. czech, english)
- Top hlasované stanice z celého světa
- Automatické načtení nejpopulárnějších stanic při spuštění

### Přístupnost (Accessibility)
- **Plná podpora čteček obrazovky** (NVDA, JAWS, Narrator, atd.)
- Všechny ovládací prvky mají přístupná jména a popisy
- Kompletní podpora klávesnice - vše lze ovládat bez myši
- Tooltips s nápovědou pro všechny prvky
- Status oznámení pro čtečky obrazovky
- Správné tab pořadí pro navigaci

### Klávesové zkratky
- **Mezerník** - Přehrát/Pozastavit
- **Escape** - Zastavit
- **Enter** - Přehrát vybranou stanici
- **+/-** - Zvýšit/Snížit hlasitost
- **I** - Zobrazit informace o stanici
- **F1** - Zobrazit nápovědu
- **Tab/Shift+Tab** - Navigace mezi prvky
- **Šipky** - Navigace v seznamech a ovládání hlasitosti

## Požadavky

- Python 3.7 nebo novější
- VLC Media Player (musí být nainstalován v systému)
- Internetové připojení (pro Radio Browser API)

## Instalace

### 1. Instalace VLC Media Player

Stáhněte a nainstalujte VLC Media Player z oficiálních stránek:
https://www.videolan.org/vlc/

### 2. Instalace Python závislostí

```bash
pip install -r requirements.txt
```

Nebo nainstalujte jednotlivé balíčky:

```bash
pip install PyQt5
pip install python-vlc
pip install requests
```

## Spuštění aplikace

```bash
python radio_player.py
```

## Použití

### Vyhledávání online stanic

1. Otevřete záložku "Online Stations"
2. Vyberte typ vyhledávání (Name, Country Code, Language, Top Voted)
3. Zadejte hledaný výraz (např. "BBC", "CZ", "czech")
4. Klikněte na "Search" nebo stiskněte Enter
5. Ze seznamu vyberte stanici dvojklikem nebo Enter

**Příklady vyhledávání:**
- Country Code: **CZ** (České stanice), **GB** (Britské stanice), **US** (Americké stanice)
- Language: **czech**, **english**, **german**
- Name: **BBC**, **NPR**, **jazz**, **rock**

### Přehrávání stanic

1. Vyberte stanici ze seznamu (online nebo lokální)
2. Dvojklikem nebo tlačítkem "Play" (nebo mezerníkem) spusťte přehrávání
3. Použijte tlačítko "Pause" nebo mezerník pro pozastavení
4. Použijte tlačítko "Stop" nebo Escape pro zastavení

### Ovládání hlasitosti

- Použijte posuvník pro nastavení hlasitosti (0-100%)
- Klávesy + a - pro rychlé změny
- Šipky vlevo/vpravo když je fokus na posuvníku

### Přidání vlastní stanice

1. Přejděte na záložku "Local Stations"
2. Zadejte název stanice do pole "Name"
3. Zadejte URL stream do pole "URL"
4. Klikněte na tlačítko "Add Station"

### Informace o stanici

- Stiskněte klávesu **I** nebo klikněte na "Show Station Info"
- Zobrazí se detailní informace o aktuální stanici
- Pro online stanice: název, země, jazyk, žánr, bitrate, codec, homepage

## Přednastavené lokální stanice

- Český rozhlas Radiožurnál
- Český rozhlas Dvojka
- Český rozhlas Vltava
- Frekvence 1
- Evropa 2

## Radio Browser API

Aplikace využívá [Radio Browser](https://www.radio-browser.info/) - komunitní open source databázi rozhlasových stanic:

- Více než 30,000 stanic z celého světa
- Pravidelně aktualizovaná databáze
- Zdarma a open source
- Bez reklam
- Podpora pro filtrování podle země, jazyka, žánru

## Přístupnost pro zrakově postižené

Aplikace je navržena s ohledem na přístupnost:

### Čtečky obrazovky
- Všechny prvky mají popisné názvy
- Status změny jsou oznamovány
- Logická navigační struktura
- Podpora pro NVDA, JAWS, Narrator a další

### Klávesnice
- Kompletní ovládání bez myši
- Logické tab pořadí
- Intuitivní klávesové zkratky
- Enter pro aktivaci, Escape pro zrušení

### Další funkce
- Tooltips s nápovědou
- Vestavěná nápověda (F1)
- Viditelné oznámení klávesových zkratek
- Barevné indikace s textovými ekvivalenty

## Formáty URL streamů

Aplikace podporuje různé formáty audio streamů:
- MP3 streams (.mp3)
- AAC streams (.aac)
- OGG streams (.ogg)
- M3U playlist (.m3u)
- PLS playlist (.pls)
- HLS streams (.m3u8)

## Technické informace

- **Framework**: PyQt5
- **Audio backend**: python-vlc (VLC Media Player)
- **API**: Radio Browser (community-driven open source)
- **Platforma**: Windows (kompatibilní i s Linux a macOS)
- **Verze Pythonu**: 3.7+
- **Accessibility**: WCAG 2.1 guidelines

## Struktura projektu

```
FT897/
├── radio_player.py       # Hlavní aplikace s GUI
├── radio_api.py          # Radio Browser API klient
├── requirements.txt      # Python závislosti
├── README.md            # Tato dokumentace
├── test_imports.py      # Test importů
├── test_structure.py    # Test struktury kódu
└── TEST_RESULTS.md      # Výsledky testování
```

## Řešení problémů

### VLC nelze najít

Pokud dostanete chybu, že VLC nelze najít:
- Ujistěte se, že máte nainstalovaný VLC Media Player
- Na Windows zkontrolujte, že VLC je v Program Files nebo Program Files (x86)
- Možná bude potřeba restartovat systém po instalaci VLC

### Stream se nepřehrává

- Zkontrolujte internetové připojení
- Zkuste jinou stanici
- Některé streamy mohou být geo-restricted nebo dočasně nedostupné
- Zkontrolujte firewall nastavení

### API stanice se nenačítají

- Zkontrolujte internetové připojení
- Radio Browser API může být dočasně nedostupná
- Aplikace použije alternativní servery automaticky
- Můžete použít lokální stanice jako zálohu

### Problémy s přístupností

- Ujistěte se, že máte aktuální verzi čtečky obrazovky
- Zkuste restart aplikace
- Všechny funkce lze ovládat klávesnicí
- Pro nápovědu stiskněte F1

## Budoucí vylepšení

- [ ] Ukládání oblíbených stanic
- [ ] Export/Import seznamu stanic
- [ ] Zobrazení metadat (aktuální píseň/pořad)
- [ ] Ekvalizér
- [ ] Časovač vypnutí
- [ ] Nahrávání streamů
- [ ] Systémová lišta (system tray)
- [ ] Vícejazyčné rozhraní
- [ ] Témata / dark mode

## Přispívání

Projekt je open source. Pull requesty jsou vítány!

## Licence

Tento projekt je open source.

## Odkazy

- [Radio Browser API](https://www.radio-browser.info/)
- [VLC Media Player](https://www.videolan.org/vlc/)
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [python-vlc](https://github.com/oaubert/python-vlc)

## Autor

Vytvořeno pomocí Claude Code

## Poděkování

- Radio Browser komunitě za skvělou open source databázi stanic
- VLC týmu za výborný media player
- PyQt týmu za GUI framework
