from PySide6.QtCore import QObject, Signal

class BufferManager(QObject):
    buffer_cleared = Signal()

    def __init__(self, max_lines: int = 10000):
        super().__init__()
        self.max_lines = max_lines
        self._lines = []  # храним строки в виде (text, msg_type, timestamp)

    def append(self, text: str, msg_type: str, timestamp: str):
        self._lines.append((text, msg_type, timestamp))
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines:]

    def get_all(self):
        return self._lines

    def clear(self):
        self._lines.clear()
        self.buffer_cleared.emit()

    def set_max_lines(self, max_lines: int):
        self.max_lines = max_lines
        if len(self._lines) > max_lines:
            self._lines = self._lines[-max_lines:]
            self.buffer_cleared.emit()