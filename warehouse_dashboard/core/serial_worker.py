"""
core/serial_worker.py
Comunicatie seriala cu Arduino, rulata pe un thread separat ca sa nu
blocheze interfata. Trimite comenzi de tipul  L<dulap><coloana><rand>
si primeste linii inapoi (ex. "OK", "QR:PKG-002").
"""

from PySide6.QtCore import QObject, QThread, Signal

try:
    import serial
    import serial.tools.list_ports
    HAVE_SERIAL = True
except Exception:                      # pyserial neinstalat
    serial = None
    HAVE_SERIAL = False


class SerialWorker(QObject):
    line_received = Signal(str)        # linie primita de la Arduino
    sent = Signal(str)                 # confirmare trimitere
    status = Signal(bool, str)         # (conectat?, mesaj)

    def __init__(self):
        super().__init__()
        self._serial = None
        self._running = False

    @staticmethod
    def list_ports():
        if not HAVE_SERIAL:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    def is_open(self):
        return self._serial is not None and getattr(self._serial, "is_open", False)

    def open(self, port, baud=9600):
        if not HAVE_SERIAL:
            self.status.emit(False, "pyserial nu este instalat (pip install pyserial)")
            return
        self.close()
        try:
            self._serial = serial.Serial(port, int(baud), timeout=0.2)
            self.status.emit(True, f"Conectat la {port} @ {baud} baud")
        except Exception as e:
            self._serial = None
            self.status.emit(False, f"Eroare conectare: {e}")

    def close(self):
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self.status.emit(False, "Deconectat")

    def send(self, text):
        """Trimite o comanda (apelat din thread-ul GUI; scrierea e rapida)."""
        if not self.is_open():
            return False
        try:
            self._serial.write((text.strip() + "\n").encode("ascii", "ignore"))
            self.sent.emit(text.strip())
            return True
        except Exception as e:
            self.status.emit(False, f"Eroare trimitere: {e}")
            return False

    def run(self):
        """Bucla de citire, rulata in thread-ul propriu."""
        self._running = True
        while self._running:
            if self.is_open():
                try:
                    raw = self._serial.readline()
                    if raw:
                        line = raw.decode("utf-8", "ignore").strip()
                        if line:
                            self.line_received.emit(line)
                except Exception:
                    pass
            QThread.msleep(40)

    def stop(self):
        self._running = False
        self.close()
