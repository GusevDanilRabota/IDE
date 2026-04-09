from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QObject, Signal

class StatsLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.error_count = 0
        self.warning_count = 0
        self.info_count = 0
        self._update_text()

    def add_message(self, msg_type: str):
        if msg_type == "ERROR":
            self.error_count += 1
        elif msg_type == "WARNING":
            self.warning_count += 1
        else:
            self.info_count += 1
        self._update_text()

    def clear(self):
        self.error_count = 0
        self.warning_count = 0
        self.info_count = 0
        self._update_text()

    def _update_text(self):
        self.setText(f"⚠️ Ошибок: {self.error_count}  ⚠️ Предупреждений: {self.warning_count}  ℹ️ Инфо: {self.info_count}")