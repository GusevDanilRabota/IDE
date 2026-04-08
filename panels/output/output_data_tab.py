# -*- coding: utf-8 -*-

import re
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLineEdit, QCheckBox, QFileDialog,
    QApplication, QDialog, QLabel, QComboBox
)
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QKeySequence, QShortcut


class output_data_tab_t(QWidget):
    """
    ВИДЖЕТ ДЛЯ ОТОБРАЖЕНИЯ ВЫВОДА ДАННЫХ (ЛОГИ, ОШИБКИ, ПРЕДУПРЕЖДЕНИЯ).
    ОСОБЕННОСТИ:
    - РАЗЛИЧНЫЕ ТИПЫ СООБЩЕНИЙ (INFO, ERROR, WARNING) С ЦВЕТОВОЙ МАРКИРОВКОЙ
    - ФИЛЬТРАЦИЯ ПО ТИПАМ СООБЩЕНИЙ
    - ПОИСК ПО ТЕКСТУ (CTRL+F)
    - АВТОПРОКРУТКА ВНИЗ ПРИ ДОБАВЛЕНИИ
    - СОХРАНЕНИЕ ВЫВОДА В ФАЙЛ
    - КОПИРОВАНИЕ ВЫДЕЛЕННОГО ТЕКСТА
    - ОЧИСТКА ВСЕГО ВЫВОДА
    - ОТОБРАЖЕНИЕ ВРЕМЕНИ ДОБАВЛЕНИЯ (ОПЦИОНАЛЬНО)
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # НАСТРОЙКИ ПО УМОЛЧАНИЮ
        self.show_timestamp = True   # ПОКАЗЫВАТЬ ВРЕМЯ
        self.auto_scroll = True      # АВТОПРОКРУТКА ВНИЗ
        self.current_filter = "ALL"  # ТЕКУЩИЙ ФИЛЬТР (ALL, INFO, ERROR, WARNING)

        # ЦВЕТА ДЛЯ РАЗНЫХ ТИПОВ СООБЩЕНИЙ
        self.color_info = QColor("#d4d4d4")    # СВЕТЛО-СЕРЫЙ
        self.color_error = QColor("#f14c4c")   # КРАСНЫЙ
        self.color_warning = QColor("#e5c07b") # ЖЁЛТЫЙ

        # ПОЛНЫЙ ТЕКСТ (С ХРАНЕНИЕМ ТИПОВ ДЛЯ ФИЛЬТРАЦИИ)
        self.messages = []   # КАЖДЫЙ ЭЛЕМЕНТ: (текст, тип, время)

        # ОСНОВНАЯ ОБЛАСТЬ ВЫВОДА
        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(self._get_mono_font())
        self._apply_default_style()

        # ПАНЕЛЬ ИНСТРУМЕНТОВ
        self.clear_btn = QPushButton("ОЧИСТИТЬ")
        self.copy_btn = QPushButton("КОПИРОВАТЬ")
        self.save_btn = QPushButton("СОХРАНИТЬ")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["ВСЕ", "ИНФО", "ОШИБКИ", "ПРЕДУПРЕЖДЕНИЯ"])
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        self.timestamp_cb = QCheckBox("ПОКАЗЫВАТЬ ВРЕМЯ")
        self.timestamp_cb.setChecked(self.show_timestamp)
        self.timestamp_cb.stateChanged.connect(self._toggle_timestamp)
        self.autoscroll_cb = QCheckBox("АВТОПРОКРУТКА")
        self.autoscroll_cb.setChecked(self.auto_scroll)
        self.autoscroll_cb.stateChanged.connect(self._toggle_autoscroll)

        # ПОЛЕ ПОИСКА
        self.search_line = QLineEdit()
        self.search_line.setPlaceholderText("ПОИСК (CTRL+F)...")
        self.search_line.returnPressed.connect(self._find_next)
        self.search_btn = QPushButton("НАЙТИ")
        self.search_btn.clicked.connect(self._find_next)

        # КОМПОНОВКА
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

        # ГОРЯЧИЕ КЛАВИШИ
        self.copy_shortcut = QShortcut(QKeySequence.Copy, self.output_area)
        self.copy_shortcut.activated.connect(self.copy_selected)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self._focus_search)

        # ПОДКЛЮЧЕНИЕ КНОПОК
        self.clear_btn.clicked.connect(self.clear_output)
        self.copy_btn.clicked.connect(self.copy_selected)
        self.save_btn.clicked.connect(self.save_to_file)

        # ЗАГРУЗКА НАСТРОЕК (ЦВЕТА И ШРИФТ ИЗ QSETTINGS, ОБЩИЕ ДЛЯ ВСЕЙ IDE)
        self._load_settings()

        # ПРИВЕТСТВЕННОЕ СООБЩЕНИЕ
        self.append_message("ПАНЕЛЬ ВЫВОДА ДАННЫХ ГОТОВА.", "INFO")

    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------
    def _get_mono_font(self):
        from PySide6.QtGui import QFont
        import platform
        if platform.system() == "Windows":
            return QFont("Consolas", 9)
        else:
            return QFont("Monospace", 9)

    def _apply_default_style(self):
        """ПРИМЕНЯЕТ СТИЛЬ ПО УМОЛЧАНИЮ (ТЁМНАЯ ТЕМА)"""
        self.output_area.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                selection-background-color: #264f78;
            }
        """)

    def _load_settings(self):
        """ЗАГРУЖАЕТ НАСТРОЙКИ ИЗ QSETTINGS (НАПРИМЕР, ЦВЕТА)"""
        settings = QSettings("MyIDE", "OutputData")
        bg_color = settings.value("bg_color", "#1e1e1e")
        text_color = settings.value("text_color", "#d4d4d4")
        self.output_area.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg_color};
                color: {text_color};
                selection-background-color: #264f78;
            }}
        """)
        # ЦВЕТА ТИПОВ СООБЩЕНИЙ (ЕСЛИ СОХРАНЕНЫ)
        self.color_info = QColor(settings.value("info_color", "#d4d4d4"))
        self.color_error = QColor(settings.value("error_color", "#f14c4c"))
        self.color_warning = QColor(settings.value("warning_color", "#e5c07b"))

    def _save_settings(self):
        """СОХРАНЯЕТ НАСТРОЙКИ (ЦВЕТА)"""
        settings = QSettings("MyIDE", "OutputData")
        settings.setValue("info_color", self.color_info.name())
        settings.setValue("error_color", self.color_error.name())
        settings.setValue("warning_color", self.color_warning.name())

    def _get_timestamp(self):
        """ВОЗВРАЩАЕТ ТЕКУЩЕЕ ВРЕМЯ В ФОРМАТЕ [ЧЧ:ММ:СС]"""
        return datetime.now().strftime("[%H:%M:%S]")

    def _append_formatted_text(self, text: str, color: QColor):
        """ВСТАВЛЯЕТ ТЕКСТ В ОБЛАСТЬ ВЫВОДА С ЗАДАННЫМ ЦВЕТОМ"""
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.insertText(text, fmt)
        if self.auto_scroll:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.output_area.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # ПУБЛИЧНЫЕ МЕТОДЫ ДЛЯ ДОБАВЛЕНИЯ СООБЩЕНИЙ
    # ------------------------------------------------------------------
    def append_message(self, text: str, msg_type: str = "INFO"):
        """
        ДОБАВЛЯЕТ СООБЩЕНИЕ С УКАЗАНИЕМ ТИПА.
        msg_type: "INFO", "ERROR", "WARNING" (РЕГИСТР НЕ ВАЖЕН)
        """
        msg_type_upper = msg_type.upper()
        # ОПРЕДЕЛЯЕМ ЦВЕТ
        if msg_type_upper == "ERROR":
            color = self.color_error
            type_label = "[ERROR]"
        elif msg_type_upper == "WARNING":
            color = self.color_warning
            type_label = "[WARNING]"
        else:
            color = self.color_info
            type_label = "[INFO]"

        # ФОРМИРУЕМ СТРОКУ
        timestamp = self._get_timestamp() if self.show_timestamp else ""
        full_text = f"{timestamp}{type_label} {text}\n"
        # СОХРАНЯЕМ В СПИСОК ДЛЯ ФИЛЬТРАЦИИ
        self.messages.append((full_text, msg_type_upper, timestamp))

        # ЕСЛИ ТЕКУЩИЙ ФИЛЬТР ПОДХОДИТ, ВЫВОДИМ
        if self._should_display(msg_type_upper):
            self._append_formatted_text(full_text, color)

    def clear_output(self):
        """ОЧИЩАЕТ ВЕСЬ ВЫВОД И ИСТОРИЮ СООБЩЕНИЙ"""
        self.output_area.clear()
        self.messages.clear()

    def copy_selected(self):
        """КОПИРУЕТ ВЫДЕЛЕННЫЙ ТЕКСТ В БУФЕР ОБМЕНА"""
        cursor = self.output_area.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())

    def save_to_file(self):
        """СОХРАНЯЕТ ВЕСЬ ТЕКУЩИЙ ВЫВОД В ФАЙЛ"""
        file_path, _ = QFileDialog.getSaveFileName(self, "СОХРАНИТЬ ВЫВОД", "", "ТЕКСТОВЫЕ ФАЙЛЫ (*.txt)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.output_area.toPlainText())
            self.append_message(f"ВЫВОД СОХРАНЁН В {file_path}", "INFO")

    # ------------------------------------------------------------------
    # ФИЛЬТРАЦИЯ
    # ------------------------------------------------------------------
    def _should_display(self, msg_type: str) -> bool:
        if self.current_filter == "ALL":
            return True
        if self.current_filter == "INFO" and msg_type == "INFO":
            return True
        if self.current_filter == "ERROR" and msg_type == "ERROR":
            return True
        if self.current_filter == "WARNING" and msg_type == "WARNING":
            return True
        return False

    def _apply_filter(self, filter_text: str):
        """ПРИМЕНЯЕТ ФИЛЬТР ПО ТИПУ СООБЩЕНИЙ И ПЕРЕСТРАИВАЕТ ВЫВОД"""
        # СОХРАНЯЕМ ТЕКУЩУЮ ПОЗИЦИЮ ПРОКРУТКИ
        scrollbar = self.output_area.verticalScrollBar()
        scroll_pos = scrollbar.value() if scrollbar else 0

        self.output_area.clear()
        # ОПРЕДЕЛЯЕМ ТИП ФИЛЬТРА
        if filter_text == "ВСЕ":
            self.current_filter = "ALL"
        elif filter_text == "ИНФО":
            self.current_filter = "INFO"
        elif filter_text == "ОШИБКИ":
            self.current_filter = "ERROR"
        elif filter_text == "ПРЕДУПРЕЖДЕНИЯ":
            self.current_filter = "WARNING"
        else:
            self.current_filter = "ALL"

        # ВЫВОДИМ СООБЩЕНИЯ, ПРОХОДЯ ФИЛЬТР
        for full_text, msg_type, timestamp in self.messages:
            if self._should_display(msg_type):
                color = self._get_color_for_type(msg_type)
                self._append_formatted_text(full_text, color)

        # ВОССТАНАВЛИВАЕМ ПОЗИЦИЮ ПРОКРУТКИ
        if scrollbar:
            QTimer.singleShot(10, lambda: scrollbar.setValue(scroll_pos))

    def _get_color_for_type(self, msg_type: str) -> QColor:
        if msg_type == "ERROR":
            return self.color_error
        elif msg_type == "WARNING":
            return self.color_warning
        else:
            return self.color_info

    # ------------------------------------------------------------------
    # НАСТРОЙКИ (ВРЕМЯ, АВТОПРОКРУТКА)
    # ------------------------------------------------------------------
    def _toggle_timestamp(self, state):
        self.show_timestamp = (state == Qt.CheckState.Checked.value)
        self._apply_filter(self.filter_combo.currentText())  # ПЕРЕСТРОИТЬ ВЫВОД

    def _toggle_autoscroll(self, state):
        self.auto_scroll = (state == Qt.CheckState.Checked.value)

    # ------------------------------------------------------------------
    # ПОИСК
    # ------------------------------------------------------------------
    def _focus_search(self):
        self.search_line.setFocus()
        self.search_line.selectAll()

    def _find_next(self):
        text = self.search_line.text()
        if not text:
            return
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
                self.append_message(f"ТЕКСТ '{text}' НЕ НАЙДЕН.", "WARNING")

    # ------------------------------------------------------------------
    # ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ДЛЯ СОВМЕСТИМОСТИ
    # ------------------------------------------------------------------
    def insertPlainText(self, text: str):
        """
        МЕТОД ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ СО СТАРЫМ КОДОМ.
        ПРОСТО ДОБАВЛЯЕТ ТЕКСТ КАК СООБЩЕНИЕ ТИПА INFO.
        """
        self.append_message(text, "INFO")

    def setReadOnly(self, readonly: bool):
        """СОВМЕСТИМОСТЬ: УСТАНАВЛИВАЕТ ТОЛЬКО ЧТЕНИЕ (ВСЕГДА TRUE)"""
        self.output_area.setReadOnly(readonly)