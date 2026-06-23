"""ui/theme.py - tema dark (QSS) pentru dashboard."""

DARK_QSS = """
* { font-family: "Segoe UI", Arial, sans-serif; }
QWidget { background-color: #1e1f26; color: #e6e6e6; }
QMainWindow, QDialog { background-color: #1e1f26; }

QTabWidget::pane { border: 1px solid #33343d; top: -1px; }
QTabBar::tab {
    background: #262732; color: #b8b8c0; padding: 8px 18px;
    border: 1px solid #33343d; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #0f6b5c; color: #ffffff; }
QTabBar::tab:hover:!selected { background: #2f303c; }

QPushButton {
    background-color: #0f6b5c; color: #ffffff; border: none;
    padding: 7px 14px; border-radius: 6px; font-weight: 600;
}
QPushButton:hover { background-color: #138a76; }
QPushButton:pressed { background-color: #0c5749; }
QPushButton:disabled { background-color: #3a3b45; color: #7c7c86; }
QPushButton#danger { background-color: #8a2f24; }
QPushButton#danger:hover { background-color: #a83a2c; }
QPushButton#ghost { background-color: #2f303c; color: #d0d0d8; }
QPushButton#ghost:hover { background-color: #3a3b48; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background-color: #262732; border: 1px solid #3a3b45;
    border-radius: 5px; padding: 5px; color: #e6e6e6;
    selection-background-color: #0f6b5c;
}
QComboBox QAbstractItemView { background: #262732; selection-background-color: #0f6b5c; }

QTableWidget {
    background-color: #23242e; gridline-color: #33343d;
    border: 1px solid #33343d; border-radius: 6px;
}
QHeaderView::section {
    background-color: #2c2d38; color: #c9c9d2; padding: 6px;
    border: none; border-right: 1px solid #33343d; font-weight: 600;
}
QTableWidget::item:selected { background-color: #0f6b5c; color: #ffffff; }

QLabel#h1 { font-size: 18px; font-weight: 700; color: #ffffff; }
QLabel#muted { color: #9a9aa4; }
QLabel#stat { font-size: 22px; font-weight: 700; color: #2fd0b5; }

QGroupBox {
    border: 1px solid #33343d; border-radius: 8px; margin-top: 12px; padding: 8px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #b8b8c0; }
"""


LIGHT_QSS = """
* { font-family: "Segoe UI", Arial, sans-serif; }
QWidget { background-color: #ffffff; color: #1f2430; }
QMainWindow, QDialog { background-color: #f5f6f8; }

QTabWidget::pane { border: 1px solid #dfe3ea; top: -1px; background: #ffffff; }
QTabBar::tab {
    background: #eef1f5; color: #5a6473; padding: 8px 18px;
    border: 1px solid #dfe3ea; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #0f6b5c; color: #ffffff; }
QTabBar::tab:hover:!selected { background: #e3e8ef; }

QPushButton {
    background-color: #0f6b5c; color: #ffffff; border: none;
    padding: 7px 14px; border-radius: 6px; font-weight: 600;
}
QPushButton:hover { background-color: #138a76; }
QPushButton:pressed { background-color: #0c5749; }
QPushButton:disabled { background-color: #c9ced6; color: #8a8f99; }
QPushButton#danger { background-color: #c0392b; }
QPushButton#danger:hover { background-color: #d94436; }
QPushButton#ghost { background-color: #e8ecf1; color: #3a4250; }
QPushButton#ghost:hover { background-color: #dde2e9; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background-color: #ffffff; border: 1px solid #cfd6e0;
    border-radius: 5px; padding: 5px; color: #1f2430;
    selection-background-color: #0f6b5c; selection-color: #ffffff;
}
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #0f6b5c; selection-color:#ffffff; }

QTableWidget {
    background-color: #ffffff; gridline-color: #e3e7ee;
    border: 1px solid #dfe3ea; border-radius: 6px;
}
QHeaderView::section {
    background-color: #eef1f5; color: #444c59; padding: 6px;
    border: none; border-right: 1px solid #dfe3ea; font-weight: 600;
}
QTableWidget::item:selected { background-color: #0f6b5c; color: #ffffff; }

QLabel#h1 { font-size: 18px; font-weight: 700; color: #1f2430; }
QLabel#muted { color: #8a92a0; }
QLabel#stat { font-size: 22px; font-weight: 700; color: #0f6b5c; }

QGroupBox {
    border: 1px solid #dfe3ea; border-radius: 8px; margin-top: 12px;
    padding: 8px; background: #ffffff;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #5a6473; }

QScrollArea { border: none; background: #ffffff; }
QStatusBar { background: #eef1f5; color: #444c59; }
"""
