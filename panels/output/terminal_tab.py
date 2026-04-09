# terminal_tab_t.py
import os
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLineEdit,
    QPushButton, QApplication, QFileDialog, QDialog, QColorDialog,
    QFontDialog, QComboBox, QLabel, QMessageBox
)
from PySide6.QtCore import QProcess, Qt, QTimer, Signal, QSettings
from PySide6.QtGui import QTextCursor, QFont, QKeySequence, QShortcut, QColor   # <-- добавлен QColor

class terminal_tab_t(QWidget):
    """Интерактивный терминал с полной панелью инструментов."""
    navigate_to = Signal(str, int)

    def __init__(self, shell_path=None, shell_args=None, shell_name="Shell", parent=None):
        super().__init__(parent)
        self.shell_name = shell_name
        self.process = None
        self.current_dir = os.path.expanduser("~")
        self.last_command_output = ""

        if shell_path is None:
            if platform.system() == "Windows":
                self.shell_path = "cmd.exe"
                self.shell_args = []
            else:
                self.shell_path = "/bin/bash"
                self.shell_args = ["-i"]
        else:
            self.shell_path = shell_path
            self.shell_args = shell_args or []

        self._init_ui()
        self._init_history()
        self._load_settings()
        self.start_shell()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(self._get_mono_font())

        self.input_line = QLineEdit()
        self.input_line.setFont(self._get_mono_font())
        self.input_line.returnPressed.connect(self.send_command)

        self.copy_btn = QPushButton("Копировать")
        self.paste_btn = QPushButton("Вставить")
        self.copy_last_btn = QPushButton("Копировать вывод")
        self.clear_btn = QPushButton("Очистить")
        self.save_btn = QPushButton("Сохранить")
        self.settings_btn = QPushButton("Настройки")
        self.expand_btn = QPushButton("Развернуть")

        self.bookmark_combo = QComboBox()
        self.bookmark_combo.addItem("📁 Избранные папки")
        self.bookmark_combo.addItem("Домашняя", os.path.expanduser("~"))
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desktop):
            self.bookmark_combo.addItem("Рабочий стол", desktop)
        self.bookmark_combo.currentIndexChanged.connect(self._on_bookmark_selected)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.input_line, stretch=2)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.paste_btn)
        btn_layout.addWidget(self.copy_last_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.bookmark_combo)
        btn_layout.addWidget(self.settings_btn)
        btn_layout.addWidget(self.expand_btn)

        layout.addWidget(self.output_area, stretch=1)
        layout.addLayout(btn_layout)

        self.copy_btn.clicked.connect(self.copy_selected)
        self.paste_btn.clicked.connect(self.paste_to_input)
        self.copy_last_btn.clicked.connect(self.copy_last_output)
        self.clear_btn.clicked.connect(self.clear)
        self.save_btn.clicked.connect(self.save_to_file)
        self.settings_btn.clicked.connect(self.show_settings_dialog)
        self.expand_btn.clicked.connect(self.open_expanded_terminal)

        QShortcut(QKeySequence.Copy, self.output_area, self.copy_selected)
        QShortcut(QKeySequence.Paste, self.input_line, self.paste_to_input)

        # Применяем стили после создания всех виджетов
        self._apply_style()

    def _init_history(self):
        self.history = []
        self.history_index = -1
        self.input_line.installEventFilter(self)

    def _get_mono_font(self):
        if platform.system() == "Windows":
            return QFont("Consolas", 9)
        elif platform.system() == "Darwin":
            return QFont("Menlo", 11)
        else:
            return QFont("Monospace", 9)

    def _apply_style(self):
        settings = QSettings("MyIDE", "Terminal")
        bg = settings.value("bg_color", "#1e1e1e")
        fg = settings.value("text_color", "#d4d4d4")
        style = f"""
            QPlainTextEdit {{
                background-color: {bg};
                color: {fg};
                selection-background-color: #264f78;
            }}
            QLineEdit {{
                background-color: {bg};
                color: {fg};
                selection-background-color: #264f78;
                border: 1px solid #3c3c3c;
                padding: 2px;
            }}
        """
        self.output_area.setStyleSheet(style)
        self.input_line.setStyleSheet(style)
        font_str = settings.value("font", "")
        if font_str:
            font = QFont()
            font.fromString(font_str)
            self.output_area.setFont(font)
            self.input_line.setFont(font)

    def _load_settings(self):
        self._apply_style()

    def show_settings_dialog(self):
        print("Настройки вызваны")  # для отладки
        settings = QSettings("MyIDE", "Terminal")
        current_bg = settings.value("bg_color", "#1e1e1e")
        current_fg = settings.value("text_color", "#d4d4d4")
        current_font = self.output_area.font()

        dialog = QDialog(self)
        dialog.setWindowTitle("Настройки терминала")
        layout = QVBoxLayout(dialog)

        def choose_bg():
            color = QColorDialog.getColor(QColor(current_bg), dialog, "Цвет фона")
            if color.isValid():
                settings.setValue("bg_color", color.name())
                self._apply_style()
        def choose_fg():
            color = QColorDialog.getColor(QColor(current_fg), dialog, "Цвет текста")
            if color.isValid():
                settings.setValue("text_color", color.name())
                self._apply_style()
        def choose_font():
            ok, font = QFontDialog.getFont(current_font, dialog, "Шрифт терминала")
            if ok:
                settings.setValue("font", font.toString())
                self._apply_style()

        btn_bg = QPushButton("Цвет фона")
        btn_fg = QPushButton("Цвет текста")
        btn_font = QPushButton("Шрифт")
        btn_bg.clicked.connect(choose_bg)
        btn_fg.clicked.connect(choose_fg)
        btn_font.clicked.connect(choose_font)

        layout.addWidget(btn_bg)
        layout.addWidget(btn_fg)
        layout.addWidget(btn_font)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def _on_bookmark_selected(self, index):
        if index <= 0:
            return
        self.bookmark_combo.setCurrentIndex(0)

    def start_shell(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_output)
        self.process.finished.connect(self._on_finished)
        self.process.setWorkingDirectory(self.current_dir)

        self.process.start(self.shell_path, self.shell_args)
        if not self.process.waitForStarted(1000):
            self.append_output(f"Ошибка запуска {self.shell_path}\n")
        else:
            self.append_output(f"Терминал [{self.shell_name}] запущен. Директория: {self.current_dir}\n")

    def send_command(self):
        cmd = self.input_line.text().strip()
        if not cmd:
            return
        self.history.append(cmd)
        self.history_index = len(self.history)
        self.input_line.clear()

        # Отправляем команду в процесс, включая cd
        self.append_output(cmd + "\n")
        data = (cmd + "\n").encode(self._get_encoding(), errors='replace')
        self.process.write(data)
        self.last_command_output = ""

    def _on_output(self):
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode(self._get_encoding(), errors='replace')
        self.last_command_output += text
        self.append_output(text)

    def _on_finished(self, exit_code, exit_status):
        self.append_output(f"\n[Процесс завершён, код {exit_code}]\n")
        QTimer.singleShot(1000, self.start_shell)

    def _get_encoding(self):
        return 'cp866' if platform.system() == "Windows" else 'utf-8'

    def append_output(self, text: str):
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)
        self.output_area.insertPlainText(text)
        self.output_area.verticalScrollBar().setValue(
            self.output_area.verticalScrollBar().maximum()
        )

    def clear(self):
        self.output_area.clear()

    def copy_selected(self):
        cursor = self.output_area.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())

    def paste_to_input(self):
        text = QApplication.clipboard().text()
        if text:
            self.input_line.insert(text)

    def copy_last_output(self):
        if self.last_command_output:
            QApplication.clipboard().setText(self.last_command_output)
            self.append_output("[Скопирован вывод последней команды]\n")
        else:
            self.append_output("[Нет вывода последней команды]\n")

    def save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить вывод терминала", "", "*.txt")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.output_area.toPlainText())
            self.append_output(f"[Вывод сохранён в {path}]\n")

    def open_expanded_terminal(self):
        expanded = QDialog(self)
        expanded.setWindowTitle(f"Терминал (развёрнутый) – {self.shell_name}")
        expanded.resize(1200, 800)
        terminal_copy = terminal_tab_t(self.shell_path, self.shell_args, self.shell_name)
        terminal_copy.current_dir = self.current_dir
        terminal_copy.append_output("--- Развёрнутый терминал ---\n")
        layout = QVBoxLayout(expanded)
        layout.addWidget(terminal_copy)
        expanded.exec()

    def eventFilter(self, obj, event):
        if obj == self.input_line and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Up:
                self._history_prev()
                return True
            elif event.key() == Qt.Key_Down:
                self._history_next()
                return True
        return super().eventFilter(obj, event)

    def _history_prev(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.input_line.setText(self.history[self.history_index])

    def _history_next(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.input_line.setText(self.history[self.history_index])
        else:
            self.history_index = len(self.history)
            self.input_line.clear()

    def closeEvent(self, event):
        """Корректно завершаем процесс при закрытии виджета."""
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()
            if not self.process.waitForFinished(1000):
                self.process.kill()
        super().closeEvent(event)