"""
Глобальная шина сигналов для связи между модулями, которые не имеют
прямых ссылок друг на друга.
"""
from PySide6.QtCore import QObject, Signal


class GlobalSignals(QObject):
    """Центральный объект, содержащий все глобальные сигналы приложения"""
    # Сигнал для отправки сообщения в панель вывода (текст, вкладка)
    message_to_output = Signal(str)
    open_file_at_line = Signal(str, int)
    # Другие сигналы можно добавлять по мере необходимости
    # project_opened = Signal(str)
    # file_saved = Signal(str)


global_signals = GlobalSignals()