"""
core/data_manager.py
Gestioneaza starea depozitului. API-ul (metode publice) este identic cu
versiunea pe JSON, dar persistenta se face acum prin SQLite (core/database.py),
iar operatiile importante sunt scrise in jurnal.
"""

import os
from copy import deepcopy

from core.database import Database, default_state

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "warehouse_state.json")   # seed initial
DB_FILE = os.path.join(BASE_DIR, "warehouse.db")               # persistenta


class WarehouseData:
    def __init__(self, db_path=DB_FILE, seed_path=STATE_FILE):
        self.db = Database(db_path, seed_path=seed_path)
        self.state = self.load()

    # ---------- persistenta ----------
    def load(self):
        state = self.db.load_state()
        if state is None:
            state = default_state()
            self.db.save_state(state)
        return state

    def save(self):
        self.db.save_state(self.state)

    def reload(self):
        self.state = self.load()

    def log(self, action, package_id="", details=""):
        self.db.log(action, package_id, details)

    def get_log(self, limit=1000):
        return self.db.get_log(limit)

    def get_orders(self):
        return self.db.get_orders()

    # ---------- accesori ----------
    def get_cabinets(self):
        return self.state["cabinets"]

    def get_trailers(self):
        return self.state["trailers"]

    def get_supply_zone(self):
        return self.state["supply_zone"]

    def get_meta(self):
        return self.state["meta"]

    def total_shelves(self):
        return 18

    def occupied_shelves(self):
        count = 0
        for _, grid in self.get_cabinets().items():
            for r in range(3):
                for c in range(3):
                    if grid[r][c] is not None:
                        count += 1
        return count

    def free_shelves(self):
        return self.total_shelves() - self.occupied_shelves()

    def trailer_loaded_count(self, trailer_name):
        trailer = self.get_trailers()[trailer_name]
        count = 0
        for r in range(trailer["rows"]):
            for c in range(trailer["cols"]):
                if trailer["grid"][r][c] is not None:
                    count += 1
        return count

    def trailer_capacity(self, trailer_name):
        trailer = self.get_trailers()[trailer_name]
        return trailer["rows"] * trailer["cols"]

    def get_package_at_shelf(self, cabinet_name, row, col):
        return self.state["cabinets"][cabinet_name][row][col]

    def set_package_at_shelf(self, cabinet_name, row, col, package):
        self.state["cabinets"][cabinet_name][row][col] = package

    def get_trailer_package(self, trailer_name, row, col):
        return self.state["trailers"][trailer_name]["grid"][row][col]

    def set_trailer_package(self, trailer_name, row, col, package):
        self.state["trailers"][trailer_name]["grid"][row][col] = package

    def clear_trailer(self, trailer_name):
        trailer = self.get_trailers()[trailer_name]
        for r in range(trailer["rows"]):
            for c in range(trailer["cols"]):
                trailer["grid"][r][c] = None

    # ---------- inventar ----------
    def all_packages_inventory(self):
        rows = []
        for cabinet_name, grid in self.get_cabinets().items():
            for r in range(3):
                for c in range(3):
                    pkg = grid[r][c]
                    if pkg:
                        rows.append([
                            pkg["id"], pkg["name"], str(pkg["weight"]),
                            pkg["destination"], pkg.get("type", ""),
                            f"{cabinet_name} / R{r + 1}C{c + 1}",
                        ])
        for trailer_name, trailer in self.get_trailers().items():
            for r in range(trailer["rows"]):
                for c in range(trailer["cols"]):
                    pkg = trailer["grid"][r][c]
                    if pkg:
                        rows.append([
                            pkg["id"], pkg["name"], str(pkg["weight"]),
                            pkg["destination"], pkg.get("type", ""),
                            f"{trailer_name} / P{r + 1}-{c + 1}",
                        ])
        for pkg in self.get_supply_zone():
            rows.append([
                pkg["id"], pkg["name"], str(pkg["weight"]),
                pkg["destination"], pkg.get("type", ""), "Supply Zone",
            ])
        return rows

    def find_package(self, package_id):
        for cabinet_name, grid in self.get_cabinets().items():
            for r in range(3):
                for c in range(3):
                    pkg = grid[r][c]
                    if pkg and pkg["id"] == package_id:
                        return ("cabinet", cabinet_name, r, c, pkg)
        for trailer_name, trailer in self.get_trailers().items():
            for r in range(trailer["rows"]):
                for c in range(trailer["cols"]):
                    pkg = trailer["grid"][r][c]
                    if pkg and pkg["id"] == package_id:
                        return ("trailer", trailer_name, r, c, pkg)
        for i, pkg in enumerate(self.get_supply_zone()):
            if pkg["id"] == package_id:
                return ("supply", "Supply Zone", i, None, pkg)
        return None

    # ---------- operatii ----------
    def add_package_to_cabinet(self, cabinet_name, row, col, pkg):
        if self.find_package(pkg["id"]) is not None:
            return False, "Există deja un pachet cu acest ID."
        if self.get_package_at_shelf(cabinet_name, row, col) is not None:
            return False, "Raftul selectat este ocupat."
        self.set_package_at_shelf(cabinet_name, row, col, pkg)
        self.save()
        self.log("ADD", pkg["id"], f"{cabinet_name} R{row + 1}C{col + 1}")
        return True, "Pachet adăugat în dulap."

    def add_package_to_supply(self, pkg):
        if self.find_package(pkg["id"]) is not None:
            return False, "Există deja un pachet cu acest ID."
        self.state["supply_zone"].append(pkg)
        self.save()
        self.log("ADD", pkg["id"], "Supply Zone")
        return True, "Pachet adăugat în Supply Zone."

    def move_supply_to_cabinet(self, package_id, cabinet_name, row, col):
        if self.get_package_at_shelf(cabinet_name, row, col) is not None:
            return False, "Raftul selectat este ocupat."
        found_idx, package_obj = None, None
        for i, pkg in enumerate(self.get_supply_zone()):
            if pkg["id"] == package_id:
                found_idx, package_obj = i, pkg
                break
        if package_obj is None:
            return False, "Pachetul nu există în Supply Zone."
        self.set_package_at_shelf(cabinet_name, row, col, deepcopy(package_obj))
        del self.state["supply_zone"][found_idx]
        self.save()
        self.log("STOCK", package_id, f"-> {cabinet_name} R{row + 1}C{col + 1}")
        return True, "Pachet mutat din Supply Zone în dulap."

    def move_cabinet_to_trailer(self, package_id, trailer_name, target_row, target_col):
        found = self.find_package(package_id)
        if not found:
            return False, "Pachetul nu a fost găsit."
        if found[0] != "cabinet":
            return False, "Poți muta în trailer doar pachete aflate în dulap."
        if self.get_trailer_package(trailer_name, target_row, target_col) is not None:
            return False, "Poziția din trailer este deja ocupată."
        _, cabinet_name, row, col, pkg = found
        self.set_trailer_package(trailer_name, target_row, target_col, deepcopy(pkg))
        self.set_package_at_shelf(cabinet_name, row, col, None)
        self.save()
        self.log("LOAD", package_id, f"{cabinet_name} -> {trailer_name}")
        return True, "Pachetul a fost pus în trailer."

    def remove_package_by_id(self, package_id):
        found = self.find_package(package_id)
        if not found:
            return False, "Pachetul nu există."
        if found[0] == "cabinet":
            _, cabinet_name, row, col, _ = found
            self.set_package_at_shelf(cabinet_name, row, col, None)
        elif found[0] == "trailer":
            _, trailer_name, row, col, _ = found
            self.set_trailer_package(trailer_name, row, col, None)
        elif found[0] == "supply":
            _, _, idx, _, _ = found
            del self.state["supply_zone"][idx]
        self.save()
        self.log("REMOVE", package_id, "")
        return True, "Pachet șters."

    def deliver_trailer(self, trailer_name):
        loaded = self.trailer_loaded_count(trailer_name)
        if loaded == 0:
            return False, "Trailerul este gol."
        order_id = int(self.state["meta"]["current_order"])
        self.clear_trailer(trailer_name)
        self.state["meta"]["delivered_orders"] += 1
        self.state["meta"]["current_order"] += 1
        self.save()
        # inchide comanda curenta si o deschide pe urmatoarea (pentru Gantt)
        self.db.deliver_order(order_id, loaded)
        self.db.open_order(int(self.state["meta"]["current_order"]))
        self.log("DELIVER", "", f"{trailer_name}: {loaded} colete (comanda #{order_id})")
        return True, "Comanda a fost livrată. Trailerul a fost golit și s-a trecut la următoarea comandă."

    # ---------- coduri QR ----------
    def find_by_qr(self, code):
        """Cauta un pachet dupa codul QR primit de la ESP32-CAM
        (codul QR = ID-ul pachetului)."""
        return self.find_package(code)
