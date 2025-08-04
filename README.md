# FT897 CAT aplikace

Tato ukázková aplikace v PyQt5 umožňuje sledovat stav rádia FT-897 pomocí CAT rozhraní.

## Vlastnosti
- Robustní vlákno pro pravidelný dotaz rádia (500 ms)
- Automatická detekce seriového portu
- Ukazatel připojení v status baru
- Debounce pro změny velikosti okna a cache fontů
- Ukončení všech vláken a timerů při zavření okna
- Toast notifikace pro chyby a LED indikátor připojení
- Používá utilitu [rigctl](https://hamlib.github.io/) z balíku Hamlib pro všechny CAT příkazy – ujistěte se, že jsou nástroje Hamlib nainstalovány a `rigctl` je v PATH

## Instalace rigctl

Na Debian/Ubuntu:

```
sudo apt install libhamlib-utils
```

Na Windows stáhněte [Hamlib balík](https://hamlib.github.io/) a přidejte adresář obsahující `rigctl.exe` do proměnné PATH.

Spusťte aplikaci:

```bash
python src/main.py
```
