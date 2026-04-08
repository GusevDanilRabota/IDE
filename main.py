import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow
)
from PySide6.QtCore import Qt

from core.settings import (
    save_window_geometry,
    restore_window_geometry
)
from core.signals import global_signals
from panels.file_explorer import FileExplorerPanel
from panels.editor import CentralEditor
from panels.output import interaction_panel_t
from panels.outline import OutlinePanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IDE COLLECTIVE")

        # ЦЕНТРАЛЬНЫЙ РЕДАКТОР
        self.editor = CentralEditor()
        self.setCentralWidget(self.editor)

        # ПАНЕЛЬ ФАЙЛОВ (СЛЕВА)
        self.file_panel = FileExplorerPanel(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_panel)

        # ВАНЕЛЬ ВВОДА (СНИЗУ)
        self.output_panel = interaction_panel_t(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_panel)

        # ПАНЕЛЬ СТРУКТУРЫ (СПРАВА)
        self.outline_panel = OutlinePanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.outline_panel)

        # СОЕДИНЕНИЕ СИГНАЛОВ
        self.file_panel.file_activated.connect(self.editor.open_file)
        global_signals.message_to_output.connect(self.output_panel.append_message)

        # ОБНОВЛЕНИЕ СТРУКТУРЫ ПРИ ОТКРЫТИИИ И ИЗМЕНЕНИИ ФАЙЛА
        self.editor.file_opened.connect(self._update_outline)
        self.editor.content_changed.connect(self._update_outline_delayed)
        self._update_outline_timer = None

        # ВОССТАНОВЛЕНИЕ ГЕОМЕТРИИ
        restore_window_geometry(self)

    def _update_outline(self):  # НЕМЕДЛЕННОЕ ОБНОВЛЕНИЕ СТРУКТУРЫ ПО ТЕКУЩЕМУ СОДЕРЖИМОМУ
        code = self.editor.get_code()
        ext = self.editor.get_file_extension()
        if ext not in ['.py']:
            self.outline_panel.clear()
            return
        self.outline_panel.update_from_code(code, ext)

    def _update_outline_delayed(self):  # ОБНОВЛЕНИЕ СТРУКТУРЫ С ЗАДЕРЖКОЙ (ЧТОБЫ НЕ ОБНОВЛЯТЬ ПРИ КАЖДОМ СИМВОЛЕ)
        if self._update_outline_timer is None:
            from PySide6.QtCore import QTimer
            self._update_outline_timer = QTimer()
            self._update_outline_timer.setSingleShot(True)
            self._update_outline_timer.timeout.connect(self._update_outline)
        self._update_outline_timer.start(500)  # задержка 500 мс

    def closeEvent(self, event):
        save_window_geometry(self)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("MyIDE")
    app.setApplicationName("ModularIDE")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())