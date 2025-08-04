# FT897 CAT aplikace

Tato ukázková aplikace v PyQt5 umožňuje sledovat stav rádia FT-897 pomocí CAT rozhraní.

## Vlastnosti
- Robustní vlákno pro pravidelný dotaz rádia (200 ms)
- Automatická detekce seriového portu
- Připojení používá pevnou rychlost 9600 bps
- Ukazatel připojení v status baru
- Debounce pro změny velikosti okna a cache fontů
- Ukončení všech vláken a timerů při zavření okna
- Toast notifikace pro chyby a LED indikátor připojení
- Používá utilitu [rigctl](https://hamlib.github.io/) z balíku Hamlib pro všechny CAT příkazy – ujistěte se, že jsou nástroje Hamlib nainstalovány a `rigctl` je v PATH nebo v `C:\\Program Files\\hamlib-w64-4.6.3\\bin` (modelové číslo `1023` pro FT-897)

## Instalace rigctl

Na Debian/Ubuntu:

```
sudo apt install libhamlib-utils
```

Na Windows stáhněte [Hamlib balík](https://hamlib.github.io/) a přidejte `rigctl.exe` do PATH, případně jej nainstalujte do `C:\\Program Files\\hamlib-w64-4.6.3\\bin`, který aplikace kontroluje automaticky.

Alternativně lze balík Hamlib nainstalovat pomocí pipu:

```
pip install hamlib
```

Spusťte aplikaci:

```bash
python src/main.py
```
