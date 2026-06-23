"""
core/database.py
Strat de persistenta SQLite pentru Smart Warehouse Dashboard.

Starea depozitului (dulapuri, trailere, supply zone, meta) este pastrata
ca document JSON intr-un singur rand din tabelul `state`, ca structura sa
ramana identica cu cea din `warehouse_state.json`. In plus exista tabele
dedicate pentru jurnalul de operatii (`operation_log`) si pentru comenzi
(`orders`), folosite in tab-urile Jurnal si Analiza.
"""

import os
import json
import sqlite3
import datetime


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def default_state():
    """Stare implicita, folosita daca nu exista nici DB, nici seed JSON."""
    empty = lambda: [[None, None, None] for _ in range(3)]
    return {
        "meta": {"current_order": 1, "delivered_orders": 0},
        "cabinets": {"Cabinet 1": empty(), "Cabinet 2": empty()},
        "trailers": {
            "Trailer 1x1": {"rows": 1, "cols": 1, "grid": [[None]]},
            "Trailer 1x2": {"rows": 1, "cols": 2, "grid": [[None, None]]},
            "Trailer 1x3": {"rows": 1, "cols": 3, "grid": [[None, None, None]]},
        },
        "supply_zone": [],
    }


class Database:
    def __init__(self, db_path, seed_path=None):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        if self._state_is_empty():
            self._seed(seed_path)

    # ---------- schema ----------
    def _create_tables(self):
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
        c.execute(
            "CREATE TABLE IF NOT EXISTS operation_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, "
            "action TEXT, package_id TEXT, details TEXT)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "id INTEGER PRIMARY KEY, opened_at TEXT, "
            "delivered_at TEXT, package_count INTEGER)"
        )
        self.conn.commit()

    def _state_is_empty(self):
        row = self.conn.execute("SELECT COUNT(*) AS n FROM state").fetchone()
        return row["n"] == 0

    def _seed(self, seed_path):
        state = None
        if seed_path and os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = None
        if state is None:
            state = default_state()
        self.save_state(state)
        # deschide comanda curenta pentru Gantt
        self.open_order(int(state.get("meta", {}).get("current_order", 1)))

    # ---------- stare ----------
    def load_state(self):
        row = self.conn.execute(
            "SELECT value FROM state WHERE key='warehouse'"
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def save_state(self, state):
        self.conn.execute(
            "INSERT INTO state(key, value) VALUES('warehouse', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(state, ensure_ascii=False),),
        )
        self.conn.commit()

    # ---------- jurnal ----------
    def log(self, action, package_id="", details=""):
        self.conn.execute(
            "INSERT INTO operation_log(timestamp, action, package_id, details) "
            "VALUES(?, ?, ?, ?)",
            (_now(), action, package_id or "", details or ""),
        )
        self.conn.commit()

    def get_log(self, limit=1000):
        rows = self.conn.execute(
            "SELECT timestamp, action, package_id, details "
            "FROM operation_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_log(self):
        self.conn.execute("DELETE FROM operation_log")
        self.conn.commit()

    # ---------- comenzi (orders) ----------
    def open_order(self, order_id):
        exists = self.conn.execute(
            "SELECT id FROM orders WHERE id=?", (order_id,)
        ).fetchone()
        if not exists:
            self.conn.execute(
                "INSERT INTO orders(id, opened_at, delivered_at, package_count) "
                "VALUES(?, ?, NULL, 0)",
                (order_id, _now()),
            )
            self.conn.commit()

    def deliver_order(self, order_id, package_count):
        self.conn.execute(
            "UPDATE orders SET delivered_at=?, package_count=? WHERE id=?",
            (_now(), package_count, order_id),
        )
        self.conn.commit()

    def get_orders(self):
        rows = self.conn.execute(
            "SELECT id, opened_at, delivered_at, package_count FROM orders ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
