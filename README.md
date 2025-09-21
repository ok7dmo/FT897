# FT-897 Remote Control Server

Tato aplikace poskytuje přístupný webový server napsaný v jazyce Python,
který umožňuje ovládání radiostanice Yaesu FT-897 přes CAT rozhraní a
streamování zvuku z připojené zvukové karty.

## Vlastnosti

- **CAT ovládání** – nastavení frekvence, přepínání PTT a odesílání
  libovolných CAT příkazů přes jednoduché webové rozhraní.
- **Přístupnost** – stránky jsou optimalizované pro zrakově postižené,
  využívají vysoký kontrast, větší písmo a prvky ARIA.
- **Audio streaming** – stream zvuku ve formátu WAV z libovolného
  vstupního zařízení systému (například zvukové karty připojené ke
  stanici).

## Požadavky

- Python 3.10+
- Nainstalované balíčky uvedené v `requirements.txt`
- Pro CAT komunikaci balíček `pyserial` a dostupný sériový port
- Pro audio streaming knihovna `sounddevice` (vyžaduje PortAudio)

## Instalace

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Konfigurace

Server lze konfigurovat pomocí proměnných prostředí nebo souboru `.env`.

| Proměnná | Výchozí hodnota | Popis |
| --- | --- | --- |
| `FT897_SERIAL_PORT` | `/dev/ttyUSB0` | Sériový port připojené stanice |
| `FT897_BAUDRATE` | `9600` | Přenosová rychlost CAT rozhraní |
| `FT897_SERIAL_TIMEOUT` | `1.0` | Timeout (s) pro CAT komunikaci |
| `FT897_SIMULATE` | `False` | Pokud je `True`, neotevírá sériový port a odpovědi se simulují |
| `FT897_AUDIO_SAMPLERATE` | `16000` | Vzorkovací frekvence audio streamu |
| `FT897_AUDIO_CHANNELS` | `1` | Počet kanálů audio streamu |
| `FT897_AUDIO_BLOCKSIZE` | `1024` | Velikost bloku (počet vzorků) |
| `FT897_AUDIO_ENABLED` | `True` | Povolit/zakázat audio stream |
| `FT897_AUDIO_DEVICE` | `None` | Index zařízení pro `sounddevice`, ponechte prázdné pro výchozí |

Příklad `.env` souboru:

```env
FT897_SERIAL_PORT=/dev/ttyUSB0
FT897_BAUDRATE=9600
FT897_SIMULATE=True
```

## Spuštění

```bash
python -m app.main
```

Příkaz zajistí korektní načtení balíčku `app` a spustí vestavěný uvicorn
server, který je nakonfigurovaný v souboru `app/main.py`. Pokud dáváte
přednost spouštění dvojklikem na Windows, můžete použít soubor `app/main.py`
(otevře stejného servera a díky úpravám se již nezavře hned po startu).

Aplikace běží na adrese <http://127.0.0.1:8000>.

## Poznámky

- V režimu simulace (`FT897_SIMULATE=True`) server vrací ukázkové
  odpovědi a nevyžaduje připojenou radiostanici.
- Pro správné fungování audio streamu je nutné mít nainstalován PortAudio
  (například balíček `portaudio19-dev` na Debian/Ubuntu) a odpovídající
  zvukové zařízení.
