"""
Работа с настройками приложения: сохранение и загрузка геометрии окна,
состояния док-панелей и других пользовательских настроек.
"""
from PySide6.QtCore import QSettings


def save_window_geometry(window):
    """Сохраняет геометрию и состояние док-панелей главного окна"""
    settings = QSettings()
    settings.setValue("geometry", window.saveGeometry())
    settings.setValue("windowState", window.saveState())


def restore_window_geometry(window):
    """Восстанавливает геометрию и состояние док-панелей"""
    settings = QSettings()
    geometry = settings.value("geometry")
    state = settings.value("windowState")
    if geometry is not None:
        window.restoreGeometry(geometry)
    if state is not None:
        window.restoreState(state)