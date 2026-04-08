# terminal_tab.py
# -*- coding: utf-8 -*-

import platform
import os
import time
import locale
import re
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLineEdit, QPushButton, QDialog, QApplication, QMenu,
    QColorDialog, QFontDialog, QFileDialog, QMessageBox,
    QInputDialog, QComboBox, QLabel, QToolButton, QSplitter
)
from PySide6.QtCore import QProcess, Slot, Qt, QSettings, QTimer
from PySide6.QtGui import (
    QTextCursor, QFont, QTextCharFormat, QColor,
    QKeySequence, QShortcut, QTextDocument
)


class terminal_tab_t(QWidget):
    """
    ТЕРМИНАЛ С РАСШИРЕННЫМИ ВОЗМОЖНОСТЯМИ:
    - ИСТОРИЯ КОМАНД (СТРЕЛКИ ВВЕРХ/ВНИЗ)
    - ОТОБРАЖЕНИЕ ПРОМПТА (ТЕКУЩАЯ ДИРЕКТОРИЯ)
    - ПОДДЕРЖКА ANSI ESCAPE-ПОСЛЕДОВАТЕЛЬНОСТЕЙ (ЦВЕТА)
    - ПОИСК ПО ВЫВОДУ (CTRL+F)
    - НАСТРОЙКА ЦВЕТОВ И ШРИФТА (СОХРАНЕНИЕ В QSETTINGS)
    - ВРЕМЯ ВЫПОЛНЕНИЯ КОМАНДЫ
    - ЭКСПОРТ ВЫВОДА В ФАЙЛ
    - ЗАКЛАДКИ ДЛЯ ЧАСТО ИСПОЛЬЗУЕМЫХ ПАПОК
    - АВТООПРЕДЕЛЕНИЕ КОДИРОВКИ ДЛЯ WINDOWS (CP866)
    - КНОПКА ОЧИСТКИ ВЫВОДА
    """
    def __init__(self, shell_path: str, shell_args: list, shell_name: str = None, parent=None):
        super().__init__(parent)
        self.shell_path = shell_path
        self.shell_args = shell_args
        self.shell_name = shell_name or shell_path

        self.current_dir = None
        self._set_initial_directory()
        self.last_command_output = ""

        # ИСТОРИЯ КОМАНД
        self.command_history = []      # СПИСОК ВВЕДЁННЫХ КОМАНД
        self.history_index = -1        # ТЕКУЩАЯ ПОЗИЦИЯ В ИСТОРИИ

        # ВРЕМЯ ВЫПОЛНЕНИЯ
        self.command_start_time = None

        # ANSI ПАРСИНГ
        self.ansi_regex = re.compile(r'\x1b\[[0-9;]*[mK]')  # УПРОЩЁННЫЙ

        # СОЗДАНИЕ UI
        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(self._get_mono_font())
        # НАСТРОЙКА ЦВЕТОВ (ПО УМОЛЧАНИЮ)
        self._apply_color_scheme()

        self.input_line = QLineEdit()
        self.input_line.setFont(self._get_mono_font())
        self.input_line.returnPressed.connect(self.execute_command)
        # ПОДДЕРЖКА СТРЕЛОК ДЛЯ ИСТОРИИ
        self.input_line.installEventFilter(self)

        # ПАНЕЛЬ КНОПОК
        self.copy_button = QPushButton("Копировать")
        self.paste_button = QPushButton("Вставить")
        self.execute_button = QPushButton("Выполнить")
        self.clear_button = QPushButton("Очистить")
        self.save_button = QPushButton("Сохранить")
        self.expand_button = QPushButton("Развернуть")
        self.settings_button = QPushButton("Настройки")
        self.bookmark_button = QPushButton("Закладки")

        # ЗАКЛАДКИ ДИРЕКТОРИЙ
        self.bookmark_combo = QComboBox()
        self.bookmark_combo.addItem("📁 Избранные папки")
        self.bookmark_combo.addItem("Домашняя", os.path.expanduser("~"))
        self.bookmark_combo.addItem("Рабочий стол", os.path.join(os.path.expanduser("~"), "Desktop"))
        self.bookmark_combo.currentIndexChanged.connect(self._on_bookmark_selected)

        # КОМПОНОВКА
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.input_line, stretch=2)
        bottom_layout.addWidget(self.copy_button)
        bottom_layout.addWidget(self.paste_button)
        bottom_layout.addWidget(self.execute_button)
        bottom_layout.addWidget(self.clear_button)
        bottom_layout.addWidget(self.save_button)
        bottom_layout.addWidget(self.bookmark_combo)
        bottom_layout.addWidget(self.settings_button)
        bottom_layout.addWidget(self.expand_button)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.output_area, stretch=1)
        main_layout.addLayout(bottom_layout)

        # ПРОЦЕСС
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_finished)

        # ПОДКЛЮЧЕНИЕ КНОПОК
        self.copy_button.clicked.connect(self.copy_last_output)
        self.paste_button.clicked.connect(self.paste_to_input)
        self.execute_button.clicked.connect(self.execute_command)
        self.clear_button.clicked.connect(self.clear_output)
        self.save_button.clicked.connect(self.export_output)
        self.expand_button.clicked.connect(self.open_expanded_terminal)
        self.settings_button.clicked.connect(self.show_settings_dialog)

        # ПОИСК (CTRL+F)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.show_search_dialog)
        self.search_dialog = None

        # ЗАГРУЗКА НАСТРОЕК
        self._load_settings()

        self._show_welcome()

    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------
    def _get_system_encoding(self):
        """ВОЗВРАЩАЕТ КОДИРОВКУ СИСТЕМЫ (ДЛЯ WINDOWS CP866, ИНАЧЕ UTF-8)"""
        if platform.system() == "Windows":
            return 'cp866'
        else:
            return 'utf-8'

    def _get_mono_font(self) -> QFont:
        if platform.system() == "Windows":
            return QFont("Consolas", 9)
        else:
            return QFont("Monospace", 9)

    def _set_initial_directory(self):
        self.current_dir = os.path.expanduser("~")
        if not os.path.isdir(self.current_dir):
            self.current_dir = os.getcwd()

    def _show_welcome(self):
        self.append_output(f"Терминал [{self.shell_name}] готов.\n")
        self._show_prompt()

    def _show_prompt(self):
        """ВЫВОДИТ ПРИГЛАШЕНИЕ С ТЕКУЩЕЙ ДИРЕКТОРИЕЙ"""
        prompt = f"{self.current_dir}> "
        self.append_output(prompt, is_prompt=True)

    def append_output(self, text: str, is_prompt: bool = False):
        """ДОБАВЛЯЕТ ТЕКСТ, ПОДДЕРЖИВАЕТ ANSI, ОБЫЧНЫЙ И ПРОМПТ"""
        if not is_prompt:
            # УДАЛЯЕМ ANSI ПОСЛЕДОВАТЕЛЬНОСТИ (ПОКА ПРОСТО УДАЛЯЕМ, МОЖНО РАСШИРИТЬ)
            text = self.ansi_regex.sub('', text)
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)
        self.output_area.insertPlainText(text)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # ЦВЕТОВЫЕ СХЕМЫ
    # ------------------------------------------------------------------
    def _apply_color_scheme(self):
        """ПРИМЕНЯЕТ ТЕКУЩИЕ НАСТРОЙКИ ЦВЕТОВ ИЗ QSETTINGS"""
        settings = QSettings("MyIDE", "Terminal")
        bg_color = settings.value("bg_color", "#1e1e1e")
        text_color = settings.value("text_color", "#d4d4d4")
        self.output_area.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg_color};
                color: {text_color};
                selection-background-color: #264f78;
            }}
        """)
        font_str = settings.value("font", "")
        if font_str:
            font = QFont()
            font.fromString(font_str)
            self.output_area.setFont(font)
            self.input_line.setFont(font)

    def _load_settings(self):
        self._apply_color_scheme()

    def show_settings_dialog(self):
        """ДИАЛОГ НАСТРОЙКИ ЦВЕТОВ И ШРИФТА"""
        settings = QSettings("MyIDE", "Terminal")
        current_bg = settings.value("bg_color", "#1e1e1e")
        current_text = settings.value("text_color", "#d4d4d4")
        current_font = self.output_area.font()

        dialog = QDialog(self)
        dialog.setWindowTitle("Настройки терминала")
        layout = QVBoxLayout(dialog)

        # КНОПКИ ВЫБОРА ЦВЕТА
        btn_bg = QPushButton("Цвет фона")
        btn_text = QPushButton("Цвет текста")
        btn_font = QPushButton("Шрифт")

        def choose_bg():
            color = QColorDialog.getColor(QColor(current_bg), self)
            if color.isValid():
                settings.setValue("bg_color", color.name())
                self._apply_color_scheme()
        def choose_text():
            color = QColorDialog.getColor(QColor(current_text), self)
            if color.isValid():
                settings.setValue("text_color", color.name())
                self._apply_color_scheme()
        def choose_font():
            ok, font = QFontDialog.getFont(current_font, self)
            if ok:
                settings.setValue("font", font.toString())
                self._apply_color_scheme()

        btn_bg.clicked.connect(choose_bg)
        btn_text.clicked.connect(choose_text)
        btn_font.clicked.connect(choose_font)

        layout.addWidget(btn_bg)
        layout.addWidget(btn_text)
        layout.addWidget(btn_font)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)
        dialog.exec()

    # ------------------------------------------------------------------
    # ПОИСК
    # ------------------------------------------------------------------
    def show_search_dialog(self):
        """ОТКРЫВАЕТ ДИАЛОГ ПОИСКА ПО ВЫВОДУ"""
        if self.search_dialog is None:
            self.search_dialog = QDialog(self)
            self.search_dialog.setWindowTitle("Поиск")
            layout = QVBoxLayout(self.search_dialog)
            self.search_edit = QLineEdit()
            self.search_edit.setPlaceholderText("Введите текст для поиска...")
            btn_find = QPushButton("Найти")
            btn_close = QPushButton("Закрыть")
            layout.addWidget(self.search_edit)
            layout.addWidget(btn_find)
            layout.addWidget(btn_close)
            btn_find.clicked.connect(self._find_text)
            btn_close.clicked.connect(self.search_dialog.accept)
        self.search_dialog.show()

    def _find_text(self):
        text = self.search_edit.text()
        if not text:
            return
        # ИЩЕМ В ОБЛАСТИ ВЫВОДА
        cursor = self.output_area.textCursor()
        cursor = self.output_area.document().find(text, cursor)
        if not cursor.isNull():
            self.output_area.setTextCursor(cursor)
        else:
            # НАЧИНАЕМ С НАЧАЛА
            cursor = self.output_area.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor = self.output_area.document().find(text, cursor)
            if not cursor.isNull():
                self.output_area.setTextCursor(cursor)
            else:
                self.append_output("[Текст не найден]\n")

    # ------------------------------------------------------------------
    # ИСТОРИЯ КОМАНД
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj == self.input_line and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up:
                self._history_prev()
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._history_next()
                return True
        return super().eventFilter(obj, event)

    def _history_prev(self):
        if self.history_index > 0:
            self.history_index -= 1
        elif self.history_index == -1 and self.command_history:
            self.history_index = len(self.command_history) - 1
        if self.history_index >= 0 and self.command_history:
            self.input_line.setText(self.command_history[self.history_index])

    def _history_next(self):
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.input_line.setText(self.command_history[self.history_index])
        else:
            self.history_index = -1
            self.input_line.clear()

    # ------------------------------------------------------------------
    # ЗАКЛАДКИ ПАПОК
    # ------------------------------------------------------------------
    def _on_bookmark_selected(self, index):
        if index <= 0:
            return
        path = self.bookmark_combo.itemData(index)
        if path and os.path.isdir(path):
            self._change_directory(path)
        self.bookmark_combo.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # ЭКСПОРТ В ФАЙЛ
    # ------------------------------------------------------------------
    def export_output(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить вывод", "", "Текстовые файлы (*.txt)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.output_area.toPlainText())
            self.append_output(f"[Вывод сохранён в {file_path}]\n")

    # ------------------------------------------------------------------
    # ВЫПОЛНЕНИЕ КОМАНД
    # ------------------------------------------------------------------
    @Slot()
    def execute_command(self):
        command = self.input_line.text().strip()
        if not command:
            return

        # ДОБАВЛЯЕМ В ИСТОРИЮ
        self.command_history.append(command)
        self.history_index = -1

        self.append_output(f"\n{command}\n")
        self.input_line.clear()

        if command.startswith("cd "):
            self._change_directory(command[3:].strip())
            self._show_prompt()
            return
        if command == "exit":
            self.append_output("Используйте кнопку 'Развернуть' или закройте вкладку.\n")
            return

        self.last_command_output = ""
        self.process.setWorkingDirectory(self.current_dir)
        self.command_start_time = time.time()
        self.process.start(self.shell_path, self.shell_args + [command])

    def _change_directory(self, path: str):
        if os.path.isabs(path):
            new_path = path
        else:
            new_path = os.path.join(self.current_dir, path)
        new_path = os.path.normpath(new_path)
        if os.path.isdir(new_path):
            self.current_dir = new_path
            self.append_output(f"Директория изменена на: {self.current_dir}\n")
        else:
            self.append_output(f"cd: {path}: Нет такой директории\n")
        self._show_prompt()

    @Slot()
    def _on_stdout(self):
        data = self.process.readAllStandardOutput()
        encoding = self._get_system_encoding()
        text = bytes(data).decode(encoding, errors='replace')
        if text:
            self.last_command_output += text
            self.append_output(text)

    @Slot()
    def _on_stderr(self):
        data = self.process.readAllStandardError()
        encoding = self._get_system_encoding()
        text = bytes(data).decode(encoding, errors='replace')
        if text:
            self.last_command_output += text
            self.append_output(text)

    @Slot()
    def _on_finished(self, exit_code, exit_status):
        elapsed = time.time() - self.command_start_time if self.command_start_time else 0
        self.append_output(f"\n[Завершено за {elapsed:.2f} с, код {exit_code}]\n")
        self._show_prompt()

    # ------------------------------------------------------------------
    # КНОПКИ
    # ------------------------------------------------------------------
    @Slot()
    def copy_last_output(self):
        if self.last_command_output:
            QApplication.clipboard().setText(self.last_command_output)
            self.append_output("[Скопирован вывод последней команды]\n")
        else:
            self.append_output("[Нет вывода последней команды]\n")

    @Slot()
    def paste_to_input(self):
        text = QApplication.clipboard().text()
        if text:
            self.input_line.insert(text)

    @Slot()
    def clear_output(self):
        self.output_area.clear()

    @Slot()
    def open_expanded_terminal(self):
        expanded_dialog = QDialog(self)
        expanded_dialog.setWindowTitle("Терминал (развёрнутый)")
        expanded_dialog.setWindowFlags(expanded_dialog.windowFlags() | Qt.WindowMaximizeButtonHint)
        expanded_dialog.resize(1200, 800)
        terminal_copy = terminal_tab_t(self.shell_path, self.shell_args, self.shell_name)
        terminal_copy.current_dir = self.current_dir
        terminal_copy.append_output("--- Развёрнутый терминал ---\n")
        layout = QVBoxLayout(expanded_dialog)
        layout.addWidget(terminal_copy)
        expanded_dialog.exec()