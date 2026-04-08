# signals.py
from PySide6.QtCore import QObject, Signal

class GlobalSignals(QObject):
    message_to_output = Signal(str)
    open_file_at_line = Signal(str, int)
    vcs_status_changed = Signal()   # новый сигнал

global_signals = GlobalSignals()