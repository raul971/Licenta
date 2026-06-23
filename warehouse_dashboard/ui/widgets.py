"""
ui/widgets.py
Interfata Smart Warehouse Dashboard (PySide6) - temă light.
Schema operationala este interactiva: drag-and-drop direct din dulapuri pe
camion, cu animatia bratului robotic (pod rulant). Aceeasi schema apare in
tab-ul Schema si in tab-ul Dulapuri.
"""

import csv
from datetime import datetime

from PySide6.QtCore import (
    Qt, QThread, QTimer, QRectF, QPointF, QVariantAnimation,
    QSequentialAnimationGroup, QEasingCurve,
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QLineEdit, QDoubleSpinBox, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox, QFileDialog, QAbstractItemView,
    QGraphicsView, QGraphicsScene,
)

from core.data_manager import WarehouseData
from core.serial_worker import SerialWorker, HAVE_SERIAL
from ui.theme import LIGHT_QSS


# ===================================================================== #
#  Dialog adaugare pachet
# ===================================================================== #
class AddPackageDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adaugă pachet")
        self.data = data
        form = QFormLayout(self)
        self.id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.weight_edit = QDoubleSpinBox()
        self.weight_edit.setRange(0, 1000)
        self.weight_edit.setDecimals(2)
        self.weight_edit.setSuffix(" kg")
        self.dest_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.loc_combo = QComboBox()
        self.loc_combo.addItems(list(data.get_cabinets().keys()) + ["Supply Zone"])
        form.addRow("ID (cod QR):", self.id_edit)
        form.addRow("Nume:", self.name_edit)
        form.addRow("Greutate:", self.weight_edit)
        form.addRow("Destinație:", self.dest_edit)
        form.addRow("Tip:", self.type_edit)
        form.addRow("Locație:", self.loc_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def package(self):
        return {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip() or "Pachet",
            "weight": round(self.weight_edit.value(), 2),
            "destination": self.dest_edit.text().strip() or "—",
            "type": self.type_edit.text().strip(),
        }

    def location(self):
        return self.loc_combo.currentText()


# ===================================================================== #
#  Schema operationala interactiva (QGraphicsView + animatie braț)
# ===================================================================== #
class WarehouseScene(QGraphicsView):
    SW, SH = 1200, 600
    RAIL_Y = 120
    RAIL_X0, RAIL_X1 = 150, 1050

    def __init__(self, data, get_trailer, send_cmd, notify, refresh_all):
        super().__init__()
        self.data = data
        self.get_trailer = get_trailer
        self.send_cmd = send_cmd
        self.notify = notify
        self.refresh_all = refresh_all

        self.setScene(QGraphicsScene(0, 0, self.SW, self.SH, self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#ffffff"))
        self.setMinimumHeight(360)
        self.setMouseTracking(True)

        # stare animatie / drag
        self._headx = (self.RAIL_X0 + self.RAIL_X1) / 2
        self._drop = 0.0
        self._busy = False
        self._carrying = False
        self._robot = "Idle"
        self._dragging = False
        self._drag_pkg = None
        self._ghost = QPointF()
        self._group = None

        # geometrie (calculata la layout)
        self.cab_cells = []     # (QRectF, cabinet, r, c)
        self.truck_slots = []   # (QRectF, trow, tcol)
        self._home_x = self._headx
        self._layout()

    # ---------- geometrie ----------
    def _layout(self):
        self.cab_cells = []
        self.truck_slots = []
        CW, CH, GX, GY = 64, 48, 10, 10
        for ci, cab in enumerate(self.data.get_cabinets().keys()):
            base_x = 40 if ci == 0 else 920
            top = 160
            for r in range(3):
                for c in range(3):
                    x = base_x + 14 + c * (CW + GX)
                    y = top + 34 + r * (CH + GY)
                    self.cab_cells.append((QRectF(x, y, CW, CH), cab, r, c))
        # camion
        tname = self._trailer_name()
        trailer = self.data.get_trailers()[tname]
        cols = trailer["cols"]
        SWl = 104
        body_w = 24 + cols * SWl
        body_x = 566
        for c in range(cols):
            sx = body_x + 12 + c * SWl
            self.truck_slots.append((QRectF(sx, 410, SWl - 14, 42), 0, c))
        self._body_x = body_x
        self._body_w = body_w
        self._home_x = body_x + body_w / 2
        if not self._busy:
            self._headx = self._home_x

    def _trailer_name(self):
        name = self.get_trailer() if self.get_trailer else None
        trailers = self.data.get_trailers()
        if name not in trailers:
            name = list(trailers.keys())[0]
        return name

    def refresh(self):
        self._layout()
        self.viewport().update()

    def resizeEvent(self, e):
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        super().resizeEvent(e)

    def showEvent(self, e):
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        super().showEvent(e)

    # ---------- desen ----------
    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor("#ffffff"))
        p.setRenderHint(QPainter.Antialiasing)
        self._draw_title(p)
        self._draw_cabinets(p)
        self._draw_truck(p)
        self._draw_arm(p)
        self._draw_legend(p)
        if self._dragging and self._drag_pkg:
            self._draw_box(p, self._ghost.x() - 26, self._ghost.y() - 16, 52, 32,
                           self._drag_pkg["id"])

    def _draw_title(self, p):
        p.setPen(QColor("#5a6473"))
        f = QFont("Segoe UI", 12); f.setBold(True); p.setFont(f)
        p.drawText(34, 40, "SCHEMĂ OPERAȚIONALĂ DEPOZIT")

    def _cell(self, p, rect, fill, border, text, tcol):
        p.setPen(QPen(QColor(border), 1.4)); p.setBrush(QColor(fill))
        p.drawRoundedRect(rect, 7, 7)
        p.setPen(QColor(tcol)); f = QFont("Segoe UI", 8); f.setBold(True); p.setFont(f)
        p.drawText(rect, Qt.AlignCenter, text)

    def _draw_box(self, p, x, y, w, h, text):
        p.setPen(QPen(QColor("#b98a2a"), 1.4)); p.setBrush(QColor("#f5c869"))
        p.drawRoundedRect(QRectF(x, y, w, h), 5, 5)
        p.setPen(QColor("#5a420f")); f = QFont("Segoe UI", 8); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, text)

    def _draw_cabinets(self, p):
        for ci, cab in enumerate(self.data.get_cabinets().keys()):
            base_x = 40 if ci == 0 else 920
            top = 160
            p.setPen(QPen(QColor("#cfd6e0"), 1.5)); p.setBrush(QColor("#fbfcfe"))
            p.drawRoundedRect(QRectF(base_x, top, 226, 222), 12, 12)
            p.setPen(QColor("#3a6ea5")); f = QFont("Segoe UI", 9); f.setBold(True); p.setFont(f)
            p.drawText(int(base_x + 14), int(top + 22), cab)
        for rect, cab, r, c in self.cab_cells:
            pkg = self.data.get_package_at_shelf(cab, r, c)
            if pkg is None:
                self._cell(p, rect, "#dff6e4", "#3bbf5a", "FREE", "#1f8a3b")
            else:
                self._cell(p, rect, "#fad7d7", "#d84a4a", pkg["id"], "#9c2b2b")

    def _draw_truck(self, p):
        tname = self._trailer_name()
        p.setPen(QColor("#3a6ea5")); f = QFont("Segoe UI", 9); f.setBold(True); p.setFont(f)
        p.drawText(self._body_x, 392, f"Camion / {tname}")
        # cabina
        p.setPen(QPen(QColor("#3a6ea5"), 1.6)); p.setBrush(QColor("#eef4fb"))
        p.drawRoundedRect(QRectF(470, 400, 86, 64), 10, 10)
        p.setBrush(QColor("#3a6ea5")); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(486, 414, 34, 22), 5, 5)
        p.setBrush(QColor("#444c59"))
        p.drawEllipse(QRectF(486, 466, 15, 15)); p.drawEllipse(QRectF(524, 466, 15, 15))
        # remorca
        p.setPen(QPen(QColor("#3a6ea5"), 1.6)); p.setBrush(QColor("#f4f8fd"))
        p.drawRoundedRect(QRectF(self._body_x, 400, self._body_w, 70), 10, 10)
        for rect, trow, tcol in self.truck_slots:
            pkg = self.data.get_trailer_package(tname, trow, tcol)
            if pkg is not None:
                self._cell(p, rect, "#fbe3c0", "#e2932f", pkg["id"], "#9a6512")
            else:
                p.setPen(QPen(QColor("#7aa7d9"), 1.3, Qt.DashLine)); p.setBrush(QColor("#e7f0fb"))
                p.drawRoundedRect(rect, 6, 6)
                p.setPen(QColor("#3a6ea5"))
                p.drawText(rect, Qt.AlignCenter, f"P{trow + 1}-{tcol + 1}")
        p.setBrush(QColor("#444c59")); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(self._body_x + self._body_w - 74, 472, 15, 15))
        p.drawEllipse(QRectF(self._body_x + self._body_w - 46, 472, 15, 15))

    def _draw_arm(self, p):
        hx = self._headx
        # glow
        p.setPen(Qt.NoPen); p.setBrush(QColor(59, 191, 90, 40))
        p.drawEllipse(QRectF(hx - 60, self.RAIL_Y - 10, 120, 120))
        # rail
        pen = QPen(QColor("#9aa3af")); pen.setWidth(6); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(self.RAIL_X0, self.RAIL_Y, self.RAIL_X1, self.RAIL_Y)
        # head
        p.setPen(QPen(QColor("#2f9e4f"), 1.5)); p.setBrush(QColor("#3bbf5a"))
        p.drawRoundedRect(QRectF(hx - 34, self.RAIL_Y - 14, 68, 26), 7, 7)
        p.setBrush(QColor("#2f9e4f")); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(hx - 22, self.RAIL_Y - 20, 8, 8))
        p.drawEllipse(QRectF(hx + 14, self.RAIL_Y - 20, 8, 8))
        # brat
        shoulder_y = self.RAIL_Y + 12
        tip_y = shoulder_y + 60 + self._drop * 150
        arm = QPen(QColor("#3bbf5a")); arm.setWidth(5); arm.setCapStyle(Qt.RoundCap)
        p.setPen(arm)
        p.drawLine(int(hx), int(shoulder_y), int(hx), int(tip_y))
        p.drawLine(int(hx), int(tip_y), int(hx - 16), int(tip_y + 30))
        p.drawLine(int(hx), int(tip_y), int(hx + 16), int(tip_y + 30))
        # colet purtat
        if self._carrying:
            self._draw_box(p, hx - 22, tip_y + 6, 44, 28,
                           self._pkg["id"] if getattr(self, "_pkg", None) else "")

    def _draw_legend(self, p):
        x, y = 40, 432
        rows = [
            ("#3bbf5a", "Raft liber"),
            ("#d84a4a", "Raft ocupat"),
            ("#7aa7d9", "Slot trailer liber"),
            ("#e2932f", "Slot trailer ocupat"),
            ("#3bbf5a" if self._robot == "Idle" else "#e2932f", f"Robot — {self._robot}"),
        ]
        w, h = 252, 30 + len(rows) * 24
        p.setPen(QPen(QColor("#cfd6e0"), 1.4)); p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(x, y, w, h), 10, 10)
        p.setPen(QColor("#5a6473")); f = QFont("Segoe UI", 9); f.setBold(True); p.setFont(f)
        p.drawText(int(x + 14), int(y + 24), "LEGENDĂ")
        f2 = QFont("Segoe UI", 8); p.setFont(f2)
        for i, (col, lab) in enumerate(rows):
            yy = y + 38 + i * 24
            p.setPen(Qt.NoPen); p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(x + 14, yy, 14, 14), 3, 3)
            p.setPen(QColor("#3a4250")); p.drawText(int(x + 38), int(yy + 12), lab)

    # ---------- interactiune ----------
    def mousePressEvent(self, e):
        if self._busy:
            return
        pos = self.mapToScene(e.position().toPoint())
        for rect, cab, r, c in self.cab_cells:
            if rect.contains(pos):
                pkg = self.data.get_package_at_shelf(cab, r, c)
                if pkg:
                    self._dragging = True
                    self._drag_src = (cab, r, c)
                    self._drag_pkg = pkg
                    self._ghost = pos
                    self.viewport().update()
                return

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._ghost = self.mapToScene(e.position().toPoint())
            self.viewport().update()

    def mouseReleaseEvent(self, e):
        if not self._dragging:
            return
        pos = self.mapToScene(e.position().toPoint())
        self._dragging = False
        target = None
        for rect, trow, tcol in self.truck_slots:
            if rect.contains(pos):
                target = (trow, tcol)
                break
        if target is None:
            self.viewport().update()
            return
        tname = self._trailer_name()
        if self.data.get_trailer_package(tname, target[0], target[1]) is not None:
            self.notify("Slotul din camion este ocupat.")
            self.viewport().update()
            return
        self._start_transfer(self._drag_src, self._drag_pkg, tname, target)

    # ---------- animatie transfer ----------
    def _start_transfer(self, src, pkg, trailer, target):
        cab, r, c = src
        self._busy = True
        self._src = src
        self._srccab = cab
        self._pkg = pkg
        self._dsttrailer = trailer
        self._dst = (target[0], target[1])

        # comanda catre robot: L<dulap><coloana><rand>
        dulap = list(self.data.get_cabinets().keys()).index(cab)
        self._cmd = f"L{dulap}{c}{r}"
        self.send_cmd(self._cmd)
        self._set_robot("Activ")

        src_rect = next(rc for rc in self.cab_cells if rc[1] == cab and rc[2] == r and rc[3] == c)[0]
        dst_rect = next(rc for rc in self.truck_slots if rc[1] == target[0] and rc[2] == target[1])[0]
        srcX = src_rect.center().x()
        dstX = dst_rect.center().x()

        g = QSequentialAnimationGroup(self)
        g.addAnimation(self._anim_head(self._headx, srcX, 450))
        g.addAnimation(self._anim_drop(0.0, 1.0, 350))      # coboara la dulap
        pick = self._anim_drop(1.0, 0.0, 350)               # ridica (apuca)
        pick.finished.connect(self._on_pick)
        g.addAnimation(pick)
        g.addAnimation(self._anim_head(srcX, dstX, 600))    # merge la camion
        place = self._anim_drop(0.0, 1.0, 350)              # coboara la camion
        place.finished.connect(self._on_place)
        g.addAnimation(place)
        g.addAnimation(self._anim_drop(1.0, 0.0, 350))      # ridica
        g.addAnimation(self._anim_head(dstX, self._home_x, 450))  # acasa
        g.finished.connect(self._on_done)
        self._group = g
        g.start()

    def _anim_head(self, a, b, dur):
        an = QVariantAnimation(self)
        an.setStartValue(float(a)); an.setEndValue(float(b))
        an.setDuration(dur); an.setEasingCurve(QEasingCurve.InOutQuad)
        an.valueChanged.connect(self._set_head)
        return an

    def _anim_drop(self, a, b, dur):
        an = QVariantAnimation(self)
        an.setStartValue(float(a)); an.setEndValue(float(b))
        an.setDuration(dur); an.setEasingCurve(QEasingCurve.InOutQuad)
        an.valueChanged.connect(self._set_drop)
        return an

    def _set_head(self, v):
        self._headx = float(v); self.viewport().update()

    def _set_drop(self, v):
        self._drop = float(v); self.viewport().update()

    def _set_robot(self, state):
        self._robot = state; self.viewport().update()

    def _on_pick(self):
        cab, r, c = self._src
        self.data.set_package_at_shelf(cab, r, c, None)
        self.data.save()
        self._carrying = True
        self.viewport().update()

    def _on_place(self):
        self.data.set_trailer_package(self._dsttrailer, self._dst[0], self._dst[1], self._pkg)
        self.data.save()
        self.data.log("LOAD", self._pkg["id"], f"{self._srccab} -> {self._dsttrailer}")
        self._carrying = False
        self.refresh_all()

    def _on_done(self):
        self._busy = False
        self._set_robot("Idle")
        self.refresh_all()


# ===================================================================== #
#  Panou cu schema + bara de actiuni (folosit in tab-urile Schema/Dulapuri)
# ===================================================================== #
class SchemaPanel(QWidget):
    def __init__(self, data, send_cmd, notify, refresh_all):
        super().__init__()
        self.data = data
        self.notify = notify
        self.refresh_all = refresh_all

        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        add_btn = QPushButton("＋ Adaugă pachet")
        add_btn.clicked.connect(self.add_package)
        bar.addWidget(add_btn)
        bar.addWidget(QLabel("Trailer:"))
        self.trailer_combo = QComboBox()
        self.trailer_combo.addItems(list(self.data.get_trailers().keys()))
        self.trailer_combo.currentTextChanged.connect(lambda _: self.refresh_all())
        bar.addWidget(self.trailer_combo)
        deliver = QPushButton("🚚 Livrează comanda")
        deliver.setObjectName("danger")
        deliver.clicked.connect(self.deliver)
        bar.addWidget(deliver)
        reload_btn = QPushButton("↻ Reîncarcă")
        reload_btn.setObjectName("ghost")
        reload_btn.clicked.connect(self.refresh_all)
        bar.addWidget(reload_btn)
        bar.addStretch()
        hint = QLabel("Trage un colet din dulap pe un slot din camion → robotul îl transferă.")
        hint.setObjectName("muted")
        root.addLayout(bar)
        root.addWidget(hint)

        self.scene = WarehouseScene(self.data, self.current_trailer,
                                    send_cmd, notify, refresh_all)
        root.addWidget(self.scene, 1)

    def current_trailer(self):
        return self.trailer_combo.currentText()

    def refresh(self):
        self.scene.refresh()

    def add_package(self):
        dlg = AddPackageDialog(self.data, self)
        if dlg.exec() != QDialog.Accepted:
            return
        pkg = dlg.package()
        if not pkg["id"]:
            QMessageBox.warning(self, "Eroare", "ID-ul este obligatoriu.")
            return
        loc = dlg.location()
        if loc == "Supply Zone":
            ok, msg = self.data.add_package_to_supply(pkg)
        else:
            placed = False
            for r in range(3):
                for c in range(3):
                    if self.data.get_package_at_shelf(loc, r, c) is None:
                        ok, msg = self.data.add_package_to_cabinet(loc, r, c, pkg)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                ok, msg = False, "Dulapul este plin."
        self.notify(msg)
        self.refresh_all()

    def deliver(self):
        ok, msg = self.data.deliver_trailer(self.current_trailer())
        self.notify(msg)
        self.refresh_all()


# ===================================================================== #
#  Tab Inventar
# ===================================================================== #
class InventoryTab(QWidget):
    HEADERS = ["ID", "Nume", "Greutate", "Destinație", "Tip", "Locație"]

    def __init__(self, data, notify, refresh_all):
        super().__init__()
        self.data = data; self.notify = notify; self.refresh_all = refresh_all
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        t = QLabel("Inventar"); t.setObjectName("h1"); bar.addWidget(t); bar.addStretch()
        self.search = QLineEdit(); self.search.setPlaceholderText("Caută…")
        self.search.textChanged.connect(self.refresh); bar.addWidget(self.search)
        rm = QPushButton("Șterge selecția"); rm.setObjectName("danger")
        rm.clicked.connect(self.remove_selected); bar.addWidget(rm)
        exp = QPushButton("Export CSV"); exp.setObjectName("ghost")
        exp.clicked.connect(self.export_csv); bar.addWidget(exp)
        root.addLayout(bar)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table)

    def refresh(self):
        rows = self.data.all_packages_inventory()
        q = self.search.text().strip().lower()
        if q:
            rows = [r for r in rows if any(q in str(x).lower() for x in r)]
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))

    def remove_selected(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return
        pid = self.table.item(sel[0].row(), 0).text()
        ok, msg = self.data.remove_package_by_id(pid)
        self.notify(msg); self.refresh_all()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export inventar", "inventar.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(self.HEADERS); w.writerows(self.data.all_packages_inventory())
        self.notify(f"Inventar exportat în {path}")


# ===================================================================== #
#  Tab Jurnal
# ===================================================================== #
class LogTab(QWidget):
    HEADERS = ["Timp", "Acțiune", "Pachet", "Detalii"]

    def __init__(self, data, notify):
        super().__init__()
        self.data = data; self.notify = notify
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        t = QLabel("Jurnal operații"); t.setObjectName("h1"); bar.addWidget(t); bar.addStretch()
        exp = QPushButton("Export CSV"); exp.setObjectName("ghost")
        exp.clicked.connect(self.export_csv); bar.addWidget(exp)
        root.addLayout(bar)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table)

    def refresh(self):
        rows = self.data.get_log()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["timestamp", "action", "package_id", "details"]):
                self.table.setItem(i, j, QTableWidgetItem(str(r.get(key, ""))))

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export jurnal", "jurnal.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(self.HEADERS)
            for r in self.data.get_log():
                w.writerow([r["timestamp"], r["action"], r["package_id"], r["details"]])
        self.notify(f"Jurnal exportat în {path}")


# ===================================================================== #
#  Gantt + Analiza
# ===================================================================== #
class GanttWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.orders = []
        self.setMinimumHeight(150)

    def set_orders(self, orders):
        self.orders = orders; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        if not self.orders:
            p.setPen(QColor("#8a92a0"))
            p.drawText(self.rect(), Qt.AlignCenter, "Nicio comandă înregistrată încă.")
            return

        def parse(s):
            try:
                return datetime.fromisoformat(s) if s else None
            except Exception:
                return None

        starts = [parse(o["opened_at"]) for o in self.orders]
        ends = [parse(o["delivered_at"]) or datetime.now() for o in self.orders]
        valid = [s for s in starts if s]
        if not valid:
            return
        t0 = min(valid); t1 = max(ends)
        span = max((t1 - t0).total_seconds(), 1.0)
        left, top, rh, gap = 70, 14, 26, 10
        width = self.width() - left - 20
        p.setFont(QFont("Segoe UI", 9))
        for i, o in enumerate(self.orders):
            s = parse(o["opened_at"]) or t0
            e = parse(o["delivered_at"]) or datetime.now()
            x = left + (s - t0).total_seconds() / span * width
            w = max((e - s).total_seconds() / span * width, 6)
            y = top + i * (rh + gap)
            delivered = o["delivered_at"] is not None
            p.setBrush(QColor("#0f6b5c") if delivered else QColor("#e2932f")); p.setPen(Qt.NoPen)
            p.drawRoundedRect(int(x), int(y), int(w), rh, 5, 5)
            p.setPen(QColor("#444c59")); p.drawText(6, y + rh - 7, f"Cmd #{o['id']}")
            p.setPen(QColor("#ffffff"))
            p.drawText(int(x) + 6, y + rh - 7,
                       f"{o['package_count']} colete" if delivered else "în curs")


class AnalyticsTab(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        root = QVBoxLayout(self)
        t = QLabel("Analiză"); t.setObjectName("h1"); root.addWidget(t)
        row = QHBoxLayout(); root.addLayout(row)
        self._labels = {}
        for key in ["Rafturi ocupate", "Rafturi libere", "Comenzi livrate", "Comandă curentă"]:
            box = QGroupBox(key); v = QVBoxLayout(box)
            lab = QLabel("0"); lab.setObjectName("stat"); lab.setAlignment(Qt.AlignCenter)
            v.addWidget(lab); self._labels[key] = lab; row.addWidget(box)
        gbox = QGroupBox("Cronologie comenzi (Gantt)"); gl = QVBoxLayout(gbox)
        self.gantt = GanttWidget(); gl.addWidget(self.gantt); root.addWidget(gbox)
        root.addStretch()

    def refresh(self):
        self._labels["Rafturi ocupate"].setText(str(self.data.occupied_shelves()))
        self._labels["Rafturi libere"].setText(str(self.data.free_shelves()))
        meta = self.data.get_meta()
        self._labels["Comenzi livrate"].setText(str(meta.get("delivered_orders", 0)))
        self._labels["Comandă curentă"].setText(str(meta.get("current_order", 0)))
        self.gantt.set_orders(self.data.get_orders())


# ===================================================================== #
#  Tab Serial
# ===================================================================== #
class SerialTab(QWidget):
    def __init__(self, serial_worker, notify):
        super().__init__()
        self.serial = serial_worker; self.notify = notify
        root = QVBoxLayout(self)
        t = QLabel("Comunicație serială (Arduino)"); t.setObjectName("h1"); root.addWidget(t)
        if not HAVE_SERIAL:
            warn = QLabel("pyserial nu este instalat. Rulează:  pip install pyserial")
            warn.setObjectName("muted"); root.addWidget(warn)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Port:")); self.port_combo = QComboBox(); bar.addWidget(self.port_combo)
        refresh = QPushButton("↻"); refresh.setObjectName("ghost")
        refresh.clicked.connect(self.refresh_ports); bar.addWidget(refresh)
        bar.addWidget(QLabel("Baud:")); self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "57600", "115200"]); bar.addWidget(self.baud_combo)
        self.connect_btn = QPushButton("Conectează"); self.connect_btn.clicked.connect(self.toggle)
        bar.addWidget(self.connect_btn); bar.addStretch(); root.addLayout(bar)
        self.status_label = QLabel("Deconectat"); self.status_label.setObjectName("muted")
        root.addWidget(self.status_label)
        self.console = QPlainTextEdit(); self.console.setReadOnly(True); root.addWidget(self.console)
        send_row = QHBoxLayout()
        self.cmd_edit = QLineEdit(); self.cmd_edit.setPlaceholderText("Comandă manuală, ex. L012")
        self.cmd_edit.returnPressed.connect(self.send_manual); send_row.addWidget(self.cmd_edit)
        send_btn = QPushButton("Trimite"); send_btn.clicked.connect(self.send_manual)
        send_row.addWidget(send_btn); root.addLayout(send_row)
        self.serial.status.connect(self.on_status)
        self.serial.line_received.connect(lambda s: self.append(f"← {s}"))
        self.serial.sent.connect(lambda s: self.append(f"→ {s}"))
        self.refresh_ports()

    def refresh_ports(self):
        self.port_combo.clear()
        ports = self.serial.list_ports()
        self.port_combo.addItems(ports if ports else ["(niciun port)"])

    def toggle(self):
        if self.serial.is_open():
            self.serial.close()
        else:
            port = self.port_combo.currentText()
            if port.startswith("("):
                self.notify("Niciun port serial disponibil."); return
            self.serial.open(port, self.baud_combo.currentText())

    def send_manual(self):
        text = self.cmd_edit.text().strip()
        if text:
            if not self.serial.send(text):
                self.append("(neconectat — comanda nu a fost trimisă)")
            self.cmd_edit.clear()

    def on_status(self, connected, msg):
        self.status_label.setText(msg)
        self.connect_btn.setText("Deconectează" if connected else "Conectează")
        self.append(f"[{msg}]")

    def append(self, line):
        self.console.appendPlainText(line)


# ===================================================================== #
#  Fereastra principala
# ===================================================================== #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Warehouse Dashboard")
        self.resize(1200, 780)
        self.setStyleSheet(LIGHT_QSS)

        self.data = WarehouseData()

        self.serial = SerialWorker()
        self.serial_thread = QThread()
        self.serial.moveToThread(self.serial_thread)
        self.serial_thread.started.connect(self.serial.run)
        self.serial_thread.start()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # doua panouri cu schema interactiva (Schema + Dulapuri)
        self.schema_panel = SchemaPanel(self.data, self.send_cmd, self.notify, self.refresh_all)
        self.cabinets_panel = SchemaPanel(self.data, self.send_cmd, self.notify, self.refresh_all)
        self.inventory_tab = InventoryTab(self.data, self.notify, self.refresh_all)
        self.log_tab = LogTab(self.data, self.notify)
        self.analytics_tab = AnalyticsTab(self.data)
        self.serial_tab = SerialTab(self.serial, self.notify)

        self.panels = [self.schema_panel, self.cabinets_panel]

        self.tabs.addTab(self.schema_panel, "Schemă")
        self.tabs.addTab(self.cabinets_panel, "Dulapuri")
        self.tabs.addTab(self.inventory_tab, "Inventar")
        self.tabs.addTab(self.log_tab, "Jurnal")
        self.tabs.addTab(self.analytics_tab, "Analiză")
        self.tabs.addTab(self.serial_tab, "Serial")

        self.statusBar().showMessage("Gata.")
        self.serial.line_received.connect(self.on_serial_line)
        self.refresh_all()

    def send_cmd(self, text):
        if not self.serial.send(text):
            self.statusBar().showMessage(
                f"Comanda {text} nu a fost trimisă (serial neconectat).", 4000)

    def notify(self, msg):
        self.statusBar().showMessage(msg, 5000)

    def refresh_all(self):
        for panel in self.panels:
            panel.refresh()
        self.inventory_tab.refresh()
        self.log_tab.refresh()
        self.analytics_tab.refresh()

    def on_serial_line(self, line):
        if line.upper().startswith("QR:"):
            code = line.split(":", 1)[1].strip()
            found = self.data.find_by_qr(code)
            self.notify(f"QR {code} → {found[1]} (identificat)." if found
                        else f"QR {code} → necunoscut.")

    def closeEvent(self, e):
        try:
            self.serial.stop()
            self.serial_thread.quit()
            self.serial_thread.wait(1000)
            self.data.db.close()
        except Exception:
            pass
        super().closeEvent(e)
