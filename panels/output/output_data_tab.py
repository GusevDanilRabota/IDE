import re
import platform
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLineEdit, QCheckBox, QFileDialog,
    QApplication, QComboBox
)
from PySide6.QtCore import Qt, QSettings, QTimer, Signal
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QKeySequence, QShortcut, QFont

class output_data_tab_t(QWidget):
    navigate_to = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_timestamp = True
        self.auto_scroll = True
        self.current_filter = "ALL"
        self.messages = []

        # Цвета для разных типов
        self.color_info = QColor("#d4d4d4")
        self.color_error = QColor("#f14c4c")
        self.color_warning = QColor("#e5c07b")

        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(self._get_mono_font())
        self._apply_default_style()

        # Панель инструментов
        self.clear_btn = QPushButton("Очистить")
        self.copy_btn = QPushButton("Копировать")
        self.save_btn = QPushButton("Сохранить")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все", "Инфо", "Ошибки", "Предупреждения"])
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        self.timestamp_cb = QCheckBox("Время")
        self.timestamp_cb.setChecked(self.show_timestamp)
        self.timestamp_cb.stateChanged.connect(self._toggle_timestamp)
        self.autoscroll_cb = QCheckBox("Автопрокрутка")
        self.autoscroll_cb.setChecked(self.auto_scroll)
        self.autoscroll_cb.stateChanged.connect(self._toggle_autoscroll)

        self.search_line = QLineEdit()
        self.search_line.setPlaceholderText("Поиск (Ctrl+F)...")
        self.search_line.returnPressed.connect(self._find_next)
        self.search_btn = QPushButton("Найти")
        self.search_btn.clicked.connect(self._find_next)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.clear_btn)
        top_layout.addWidget(self.copy_btn)
        top_layout.addWidget(self.save_btn)
        top_layout.addWidget(self.filter_combo)
        top_layout.addWidget(self.timestamp_cb)
        top_layout.addWidget(self.autoscroll_cb)
        top_layout.addStretch()
        top_layout.addWidget(self.search_line)
        top_layout.addWidget(self.search_btn)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.output_area)

        self.clear_btn.clicked.connect(self.clear_output)
        self.copy_btn.clicked.connect(self.copy_selected)
        self.save_btn.clicked.connect(self.save_to_file)
        QShortcut(QKeySequence.Copy, self.output_area, self.copy_selected)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)

        self.append_message("Панель вывода готова (кроссплатформенная).", "INFO")

    def _get_mono_font(self):
        if platform.system() == "Windows":
            return QFont("Consolas", 9)
        elif platform.system() == "Darwin":
            return QFont("Menlo", 11)
        else:
            return QFont("Monospace", 9)

    def _apply_default_style(self):
        self.output_area.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                selection-background-color: #264f78;
            }
        """)

    def append_message(self, text: str, msg_type: str = "INFO"):
        msg_type = msg_type.upper()
        timestamp = datetime.now().strftime("[%H:%M:%S] ") if self.show_timestamp else ""
        prefix = {"ERROR": "[ERROR] ", "WARNING": "[WARNING] ", "INFO": "[INFO] "}.get(msg_type, "[INFO] ")
        full_text = f"{timestamp}{prefix}{text}\n"

        color = self.color_info
        if msg_type == "ERROR":
            color = self.color_error
        elif msg_type == "WARNING":
            color = self.color_warning

        self.messages.append((full_text, msg_type, timestamp))

        if self._should_display(msg_type):
            self._append_colored_text(full_text, color)
            if self.auto_scroll:
                self._scroll_to_bottom()

    def _append_colored_text(self, text: str, color: QColor):
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.insertText(text, fmt)

    def _scroll_to_bottom(self):
        scrollbar = self.output_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _should_display(self, msg_type):
        filter_map = {"Все": "ALL", "Инфо": "INFO", "Ошибки": "ERROR", "Предупреждения": "WARNING"}
        current = filter_map.get(self.filter_combo.currentText(), "ALL")
        return current == "ALL" or current == msg_type

    def _apply_filter(self):
        self.output_area.clear()
        for full_text, msg_type, _ in self.messages:
            if self._should_display(msg_type):
                color = self.color_info
                if msg_type == "ERROR":
                    color = self.color_error
                elif msg_type == "WARNING":
                    color = self.color_warning
                self._append_colored_text(full_text, color)
        self._scroll_to_bottom()

    def _toggle_timestamp(self, state):
        self.show_timestamp = (state == Qt.CheckState.Checked)
        self._apply_filter()

    def _toggle_autoscroll(self, state):
        self.auto_scroll = (state == Qt.CheckState.Checked)

    def clear_output(self):
        self.output_area.clear()
        self.messages.clear()

    def copy_selected(self):
        cursor = self.output_area.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())

    def save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить вывод", "", "Текстовые файлы (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.output_area.toPlainText())
            self.append_message(f"Вывод сохранён в {path}", "INFO")

    def _focus_search(self):
        self.search_line.setFocus()
        self.search_line.selectAll()

    def _find_next(self):
        text = self.search_line.text()
        if not text:
            return
        cursor = self.output_area.textCursor()
        cursor = self.output_area.document().find(text, cursor)
        if cursor.isNull():
            cursor = self.output_area.document().find(text, 0)
        if not cursor.isNull():
            self.output_area.setTextCursor(cursor)
        else:
            self.append_message(f"Текст '{text}' не найден.", "WARNING")