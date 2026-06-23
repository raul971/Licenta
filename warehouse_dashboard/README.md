# Smart Warehouse Dashboard — versiune finală

Interfață de monitorizare și control (PySide6) pentru sistemul automat de
încărcare. Comunică prin serial cu Arduino (comenzi `L<dulap><coloană><rând>`)
și persistă datele în SQLite.

## Rulare

```bash
pip install -r requirements.txt
python main.py
```

La prima pornire, baza de date `warehouse.db` se creează automat din
`warehouse_state.json` (seed). După aceea, toate modificările se păstrează în
SQLite între rulări.

## Structură

```
warehouse_dashboard/
├── main.py                  punct de intrare
├── requirements.txt         PySide6 + pyserial
├── warehouse_state.json     stare inițială (seed)
├── core/
│   ├── database.py          strat SQLite (state, operation_log, orders)
│   ├── data_manager.py      logica depozitului (API păstrat din varianta JSON)
│   └── serial_worker.py     comunicație serială (thread separat, pyserial)
└── ui/
    ├── theme.py             temă dark (QSS)
    └── widgets.py           ferestra principală + taburi
```

## Taburi

- **Dulapuri** — două dulapuri 3×3 + trailer. Tragi un colet din dulap în
  trailer → se mută, se scrie în jurnal și se trimite comanda `L<dulap><col><rand>`
  către Arduino. Click-dreapta pe un colet = ștergere.
- **Inventar** — toate coletele (cu căutare, ștergere, export CSV).
- **Jurnal** — istoricul operațiilor (din SQLite), export CSV.
- **Analiză** — ocupare rafturi, comenzi livrate, diagramă Gantt a comenzilor.
- **Serial** — alegere port + baud, conectare la Arduino, consolă, comandă manuală.

## Integrare ESP32-CAM (QR)

Dacă ESP32-CAM trimite pe serial linii de forma `QR:PKG-002`, dashboard-ul
identifică automat pachetul și afișează locația lui.

## Note

- Comanda serială respectă firmware-ul `sistem_incarcare.ino`
  (`L<dulap><coloană><rând>`, 0-based, ex. `L012`).
- `Cabinet 1` → dulap 0, `Cabinet 2` → dulap 1 (ordinea din date). Asigură-te
  că orientarea fizică a robotului corespunde.
- Pentru a reseta datele, șterge `warehouse.db` (se regenerează din JSON).
