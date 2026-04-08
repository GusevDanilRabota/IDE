import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor

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

        # ПАНЕЛЬ ФАЙЛОВ (СЛЕВА) – улучшенная (VS Code стиль)
        self.file_panel = FileExplorerPanel(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_panel)

        # ПАНЕЛЬ ВЫВОДА (СНИЗУ) – вкладки "Вывод данных" и "Терминал"
        self.output_panel = interaction_panel_t(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_panel)

        # ПАНЕЛЬ СТРУКТУРЫ (СПРАВА) – вкладки "Структура" и "Контроль версий"
        self.outline_panel = OutlinePanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.outline_panel)

        # ПОДКЛЮЧЕНИЕ СИГНАЛОВ
        self.file_panel.file_activated.connect(self.editor.open_file)
        global_signals.message_to_output.connect(self.output_panel.append_message)

        # ОБНОВЛЕНИЕ СТРУКТУРЫ ПРИ ОТКРЫТИИ И ИЗМЕНЕНИИ ФАЙЛА
        self.editor.file_opened.connect(self._update_outline)
        self.editor.content_changed.connect(self._update_outline_delayed)
        self._update_outline_timer = None

        # ПОДСВЕТКА ФАЙЛА В ДЕРЕВЕ ПРОЕКТА ПРИ ОТКРЫТИИ
        self.editor.file_opened.connect(self._reveal_file_in_tree)

        # НАВИГАЦИЯ ПО ОШИБКАМ ИЗ ПАНЕЛИ ВЫВОДА
        self.output_panel.output_data_tab.navigate_to.connect(self._open_file_at_line)

        # ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ КОНТРОЛЯ ВЕРСИЙ (VCS) – корень проекта = текущая рабочая папка
        project_root = os.getcwd()
        self.outline_panel.set_project_root(project_root)

        # ВОССТАНОВЛЕНИЕ ГЕОМЕТРИИ
        restore_window_geometry(self)

    def _update_outline(self):
        """Немедленное обновление структуры по текущему содержимому редактора."""
        code = self.editor.get_code()
        ext = self.editor.get_file_extension()
        if ext not in ['.py', '.c', '.h', '.asm', '.s']:
            self.outline_panel.clear()
            return
        self.outline_panel.update_from_code(code, ext)

    def _update_outline_delayed(self):
        """Обновление структуры с задержкой (чтобы не обновлять при каждом символе)."""
        if self._update_outline_timer is None:
            self._update_outline_timer = QTimer()
            self._update_outline_timer.setSingleShot(True)
            self._update_outline_timer.timeout.connect(self._update_outline)
        self._update_outline_timer.start(500)

    def _reveal_file_in_tree(self, file_path: str):
        """Раскрывает дерево файлов до указанного файла и подсвечивает его."""
        self.file_panel.reveal_file(file_path)

    def _open_file_at_line(self, file_path: str, line: int):
        """Открывает файл и переводит курсор на указанную строку."""
        self.editor.open_file(file_path)
        # Перемещаем курсор на строку (нумерация строк в QTextDocument начинается с 0)
        block = self.editor.document().findBlockByLineNumber(line - 1)
        if block.isValid():
            cursor = self.editor.textCursor()
            cursor.setPosition(block.position())
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()

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