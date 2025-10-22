# Radio Station Player

Aplikace pro přehrávání rozhlasových stanic vytvořená s použitím PyQt5 a python-vlc.

## Funkce

- Přehrávání internetových rozhlasových stanic
- Přednastavené české a mezinárodní stanice
- Přidávání vlastních rozhlasových stanic
- Ovládání hlasitosti
- Intuitivní grafické rozhraní
- Podpora pro Windows

## Požadavky

- Python 3.7 nebo novější
- VLC Media Player (musí být nainstalován v systému)

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
```

## Spuštění aplikace

```bash
python radio_player.py
```

## Použití

### Přehrávání stanic

1. Vyberte stanici ze seznamu
2. Dvojklikem nebo tlačítkem "Play" spusťte přehrávání
3. Použijte tlačítko "Pause" pro pozastavení
4. Použijte tlačítko "Stop" pro zastavení přehrávání

### Ovládání hlasitosti

- Použijte posuvník pro nastavení hlasitosti (0-100%)

### Přidání vlastní stanice

1. Zadejte název stanice do pole "Name"
2. Zadejte URL stream do pole "URL"
3. Klikněte na tlačítko "Add Station"

## Přednastavené stanice

Aplikace obsahuje následující přednastavené stanice:

- Český rozhlas Radiožurnál
- Český rozhlas Dvojka
- Český rozhlas Vltava
- Frekvence 1
- Evropa 2
- BBC World Service
- NPR News

## Formáty URL streamů

Aplikace podporuje různé formáty audio streamů:
- MP3 streams (.mp3)
- AAC streams (.aac)
- OGG streams (.ogg)
- M3U playlist (.m3u)
- PLS playlist (.pls)

## Technické informace

- **Framework**: PyQt5
- **Audio backend**: python-vlc (VLC Media Player)
- **Platforma**: Windows (kompatibilní i s Linux a macOS)
- **Verze Pythonu**: 3.7+

## Řešení problémů

### VLC nelze najít

Pokud dostanete chybu, že VLC nelze najít:
- Ujistěte se, že máte nainstalovaný VLC Media Player
- Na Windows zkontrolujte, že VLC je v Program Files nebo Program Files (x86)
- Možná bude potřeba restartovat systém po instalaci VLC

### Stream se nepřehrává

- Zkontrolujte internetové připojení
- Zkuste jinou stanici
- Některé streamy mohou být dočasně nedostupné

## Licence

Tento projekt je open source.

## Autor

Vytvořeno pomocí Claude Code
