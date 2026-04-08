from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

class BaseOutputTab(QWidget):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def append_message(self, text: str, msg_type: str = "INFO"):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

    def save_to_file(self, file_path: str = None):
        raise NotImplementedError

    def set_read_only(self, readonly: bool):
        raise NotImplementedError

    def get_title(self) -> str:
        return self.windowTitle() if hasattr(self, 'windowTitle') else "Output"