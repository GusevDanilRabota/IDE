# panels/output/output_tab.py
import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

from core.theme import Theme

from .output_components.ansi_parser import AnsiParser
from .output_components.buffer_manager import BufferManager
from .output_components.export_html import HtmlExporter
from .output_components.filters import FilterManager
from .output_components.scroll_manager import ScrollManager
from .output_components.search import SearchManager
from .output_components.stats_label import StatsLabel


class OutputTab(QWidget):
    # Сигнал для открытия файла по клику (навигация)
    navigate_to = Signal(str, int)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.show_timestamp = True
        self.ansi_parser = AnsiParser()
        self.buffer = BufferManager(max_lines=10000)
        self.filter_mgr = FilterManager()
        self._setup_ui()
        self.scroll_mgr = ScrollManager(self.output_area)
        self.search_mgr = SearchManager(self.output_area)
        self.buffer.buffer_cleared.connect(self._on_buffer_cleared)
        self._setup_shortcuts()
        self._apply_theme()
        self._apply_font()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setContextMenuPolicy(Qt.CustomContextMenu)
        self.output_area.customContextMenuRequested.connect(self._show_context_menu)
        self.output_area.cursorPositionChanged.connect(self._check_for_error_link)
        layout.addWidget(self.output_area)

        # Нижняя панель фильтров и статистики
        toolbar = QHBoxLayout()
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(["Все", "Инфо", "Ошибки", "Предупреждения"])
        self.filter_type_combo.currentTextChanged.connect(self._on_type_filter_changed)
        self.regex_input = QLineEdit()
        self.regex_input.setPlaceholderText("Фильтр по регулярному выражению...")
        self.regex_input.returnPressed.connect(self._on_regex_changed)
        self.stats_label = StatsLabel()
        toolbar.addWidget(QLabel("Тип:"))
        toolbar.addWidget(self.filter_type_combo)
        toolbar.addWidget(QLabel("Regex:"))
        toolbar.addWidget(self.regex_input)
        toolbar.addStretch()
        toolbar.addWidget(self.stats_label)
        layout.addLayout(toolbar)

    def _apply_theme(self):
        self.output_area.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Theme.BACKGROUND};
                color: {Theme.TEXT};
                selection-background-color: {Theme.SELECTION_BG};
                border: none;
            }}
        """)

    def _apply_font(self):
        # Шрифт можно вынести в настройки
        font = QFont("Consolas" if os.name == "nt" else "Monospace", 9)
        self.output_area.setFont(font)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self, self.clear_output)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+G"), self, self._goto_line)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)

    def _focus_search(self):
        self.regex_input.setFocus()
        self.regex_input.selectAll()

    def _goto_line(self):
        # можно реализовать диалог перехода к строке
        pass

    def append_message(self, text: str, msg_type: str = "INFO"):
        timestamp = (
            datetime.now().strftime("[%H:%M:%S] ") if self.show_timestamp else ""
        )
        prefix = {"ERROR": "[ERROR] ", "WARNING": "[WARNING] ", "INFO": "[INFO] "}.get(
            msg_type, "[INFO] "
        )
        full_text = f"{timestamp}{prefix}{text}\n"
        self.buffer.append(full_text, msg_type, timestamp)
        if self.filter_mgr.should_display(msg_type, full_text):
            self._display_message(full_text, msg_type)
        self.stats_label.add_message(msg_type)
        self.scroll_mgr.scroll_to_bottom()

    def _display_message(self, text: str, msg_type: str):
        color = Theme.get_message_color(msg_type)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)

    def _on_type_filter_changed(self, text):
        mapping = {
            "Все": "ALL",
            "Инфо": "INFO",
            "Ошибки": "ERROR",
            "Предупреждения": "WARNING",
        }
        self.filter_mgr.set_type_filter(mapping.get(text, "ALL"))
        self.refresh_display()

    def _on_regex_changed(self):
        self.filter_mgr.set_regex(self.regex_input.text())
        self.refresh_display()

    def refresh_display(self):
        self.output_area.clear()
        for full_text, msg_type, timestamp in self.buffer.get_all():
            if self.filter_mgr.should_display(msg_type, full_text):
                self._display_message(full_text, msg_type)
        self.scroll_mgr.scroll_to_bottom()

    def _on_buffer_cleared(self):
        self.refresh_display()
        self.stats_label.clear()

    def clear_output(self):
        self.buffer.clear()

    def save_to_html(self, path: str):
        HtmlExporter.export(self.buffer.get_all(), path)

    def save_to_text(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.output_area.toPlainText())

    def _show_context_menu(self, pos):
        menu = QMenu()
        copy_action = menu.addAction("Копировать")
        copy_all_action = menu.addAction("Копировать всё")
        menu.addSeparator()
        clear_action = menu.addAction("Очистить")
        save_action = menu.addAction("Сохранить...")
        menu.addSeparator()
        filter_action = menu.addAction("Фильтровать по выделенному")
        action = menu.exec_(self.output_area.viewport().mapToGlobal(pos))
        if action == copy_action:
            self.output_area.copy()
        elif action == copy_all_action:
            self.output_area.selectAll()
            self.output_area.copy()
        elif action == clear_action:
            self.clear_output()
        elif action == save_action:
            from PySide6.QtWidgets import QFileDialog

            path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить вывод", "", "Текстовые файлы (*.txt);;HTML (*.html)"
            )
            if path:
                if path.endswith(".html"):
                    self.save_to_html(path)
                else:
                    self.save_to_text(path)
        elif action == filter_action:
            cursor = self.output_area.textCursor()
            if cursor.hasSelection():
                selected = cursor.selectedText()
                self.regex_input.setText(selected)
                self._on_regex_changed()

    def _check_for_error_link(self):
        cursor = self.output_area.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line_text = cursor.selectedText()
        info = self._parse_error_line(line_text)
        if info:
            self.output_area.viewport().setCursor(Qt.PointingHandCursor)
            self.output_area.setProperty("nav_info", info)
        else:
            self.output_area.viewport().setCursor(Qt.ArrowCursor)
            self.output_area.setProperty("nav_info", None)

    def _parse_error_line(self, text: str):
        import re

        patterns = [
            re.compile(r'File "([^"]+)", line (\d+)'),
            re.compile(r"^([^:]+):(\d+):\d*:"),
            re.compile(r"^([^(]+)\((\d+)\)\s*:"),
        ]
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                file_path, line_str = match.groups()
                try:
                    line = int(line_str)
                    return file_path, line
                except ValueError:
                    continue
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            info = self.output_area.property("nav_info")
            if info:
                file_path, line = info
                self.navigate_to.emit(file_path, line)
                return
        super().mousePressEvent(event)


class OutputTab(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.show_timestamp = True  # по умолчанию показываем время
        self.ansi_parser = AnsiParser()
        self.buffer = BufferManager(max_lines=10000)
        self.filter_mgr = FilterManager()
        self.setup_ui()
        # Теперь создаём context_menu после того, как output_area создан
        self.context_menu = OutputContextMenu(self.output_area, self)
        self.output_area.customContextMenuRequested.connect(self.context_menu.show)
        self.scroll_mgr = ScrollManager(self.output_area)
        self.search_mgr = SearchManager(self.output_area)
        self.buffer.buffer_cleared.connect(self._on_buffer_cleared)
        self._setup_shortcuts()
        self._apply_font()
        self._apply_styles()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setContextMenuPolicy(Qt.CustomContextMenu)
        layout.addWidget(self.output_area)

        # Нижняя панель инструментов
        toolbar = QHBoxLayout()
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(["Все", "Инфо", "Ошибки", "Предупреждения"])
        self.filter_type_combo.currentTextChanged.connect(self._on_type_filter_changed)
        self.regex_input = QLineEdit()
        self.regex_input.setPlaceholderText("Фильтр по регулярному выражению...")
        self.regex_input.returnPressed.connect(self._on_regex_changed)
        self.stats_label = StatsLabel()
        toolbar.addWidget(QLabel("Тип:"))
        toolbar.addWidget(self.filter_type_combo)
        toolbar.addWidget(QLabel("Regex:"))
        toolbar.addWidget(self.regex_input)
        toolbar.addStretch()
        toolbar.addWidget(self.stats_label)
        layout.addLayout(toolbar)

    def _apply_styles(self):
        self.output_area.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                selection-background-color: #264f78;
            }
        """)

    def _apply_font(self):
        if os.name == "nt":
            font = QFont("Consolas", 9)
        else:
            font = QFont("Monospace", 9)
        self.output_area.setFont(font)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self, self.clear_output)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+G"), self, self._goto_line)

    def _focus_search(self):
        self.regex_input.setFocus()
        self.regex_input.selectAll()

    def _goto_line(self):
        # можно реализовать диалог перехода к строке
        pass

    def append_message(self, text: str, msg_type: str = "INFO"):
        timestamp = (
            datetime.now().strftime("[%H:%M:%S] ") if self.show_timestamp else ""
        )
        prefix = {"ERROR": "[ERROR] ", "WARNING": "[WARNING] ", "INFO": "[INFO] "}.get(
            msg_type, "[INFO] "
        )
        full_text = f"{timestamp}{prefix}{text}\n"
        self.buffer.append(full_text, msg_type, timestamp)
        if self.filter_mgr.should_display(msg_type, full_text):
            self._display_message(full_text, msg_type)
        self.stats_label.add_message(msg_type)
        self.scroll_mgr.scroll_to_bottom()

    def _display_message(self, text: str, msg_type: str):
        fragments = self.ansi_parser.parse(text)
        cursor = self.output_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        for frag, fmt in fragments:
            cursor.insertText(frag, fmt)
        self.output_area.setTextCursor(cursor)

    def _on_type_filter_changed(self, text):
        mapping = {
            "Все": "ALL",
            "Инфо": "INFO",
            "Ошибки": "ERROR",
            "Предупреждения": "WARNING",
        }
        self.filter_mgr.set_type_filter(mapping.get(text, "ALL"))
        self.refresh_display()

    def _on_regex_changed(self):
        self.filter_mgr.set_regex(self.regex_input.text())
        self.refresh_display()

    def refresh_display(self):
        self.output_area.clear()
        for full_text, msg_type, timestamp in self.buffer.get_all():
            if self.filter_mgr.should_display(msg_type, full_text):
                self._display_message(full_text, msg_type)
        self.scroll_mgr.scroll_to_bottom()

    def _on_buffer_cleared(self):
        self.refresh_display()
        self.stats_label.clear()

    def clear_output(self):
        self.buffer.clear()

    def save_to_html(self, path: str):
        HtmlExporter.export(self.buffer.get_all(), path)

    def _show_regex_filter_dialog(self, initial_text: str):
        # вызывается из контекстного меню
        self.regex_input.setText(initial_text)
        self._on_regex_changed()
