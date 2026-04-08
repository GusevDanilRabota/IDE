# main.py (фрагменты)
import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor

from core.settings import save_window_geometry, restore_window_geometry
from core.signals import global_signals
from panels.file_explorer import FileExplorerPanel
from panels.editor import CentralEditor
from panels.output import interaction_panel_t
from panels.outline import OutlinePanel
from core.vcs import VCSRepository   # новая VCS

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IDE COLLECTIVE")

        # Центральный редактор
        self.editor = CentralEditor()
        self.setCentralWidget(self.editor)

        # Панель файлов (слева)
        self.file_panel = FileExplorerPanel(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_panel)

        # Панель вывода (снизу)
        self.output_panel = interaction_panel_t(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_panel)

        # Панель структуры / VCS (справа)
        self.outline_panel = OutlinePanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.outline_panel)

        # Сигналы
        self.file_panel.file_activated.connect(self.editor.open_file)
        global_signals.message_to_output.connect(self.output_panel.append_message)

        # Обновление структуры при открытии/изменении файла
        self.editor.file_opened.connect(self._update_outline)
        self.editor.content_changed.connect(self._update_outline_delayed)
        self._update_outline_timer = None

        # Подсветка файла в дереве
        self.editor.file_opened.connect(self._reveal_file_in_tree)

        # Навигация по ошибкам
        self.output_panel.output_data_tab.navigate_to.connect(self._open_file_at_line)

        # Инициализация VCS (корень проекта – текущая рабочая папка)
        project_root = os.getcwd()
        self.vcs = VCSRepository(project_root)
        self.outline_panel.set_vcs(self.vcs)           # передаём VCS в панель структуры
        self.file_panel.set_vcs(self.vcs)              # передаём VCS в панель файлов (для отображения статусов)

        # Обновляем статусы VCS периодически (например, при изменении фокуса)
        self.vcs.status_changed.connect(self._on_vcs_status_changed)

        # Восстановление геометрии
        restore_window_geometry(self)

    def _update_outline(self):
        code = self.editor.get_code()
        ext = self.editor.get_file_extension()
        if ext not in ['.py', '.c', '.h', '.asm', '.s']:
            self.outline_panel.clear()
            return
        self.outline_panel.update_from_code(code, ext)

    def _update_outline_delayed(self):
        if self._update_outline_timer is None:
            self._update_outline_timer = QTimer()
            self._update_outline_timer.setSingleShot(True)
            self._update_outline_timer.timeout.connect(self._update_outline)
        self._update_outline_timer.start(500)

    def _reveal_file_in_tree(self, file_path: str):
        self.file_panel.reveal_file(file_path)

    def _open_file_at_line(self, file_path: str, line: int):
        self.editor.open_file(file_path)
        block = self.editor.document().findBlockByLineNumber(line - 1)
        if block.isValid():
            cursor = self.editor.textCursor()
            cursor.setPosition(block.position())
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()

    def _on_vcs_status_changed(self):
        # Обновляем отображение статусов в дереве файлов
        self.file_panel.update_vcs_status()

    def closeEvent(self, event):
        save_window_geometry(self)
        super().closeEvent(event)


def load_stylesheet(app):
    style_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        print("Файл стилей не найден, используются стандартные настройки")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("MyIDE")
    app.setApplicationName("ModularIDE")
    load_stylesheet(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())