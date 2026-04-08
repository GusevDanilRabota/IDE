"""
Центральный виджет редактора кода на базе QPlainTextEdit с поддержкой
подсветки синтаксиса и сигналом открытия файла.
"""
import os
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtCore import Signal

from .syntax import SyntaxHighlighter
from core.signals import global_signals


class CentralEditor(QPlainTextEdit):
    """Редактор с возможностью открытия файлов и базовой подсветкой"""
    file_opened = Signal(str)   # новый сигнал: путь к открытому файлу
    content_changed = Signal()  # сигнал об изменении содержимого

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Откройте файл из панели 'Файлы' двойным кликом...")
        self.highlighter = SyntaxHighlighter(self.document())
        self.current_file_path = None

        # Подключаем сигнал изменения текста
        self.textChanged.connect(self._on_text_changed)

    def open_file(self, file_path: str):
        """Загружает содержимое файла в редактор"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.setPlainText(content)
            self.current_file_path = file_path
            self.setWindowTitle(f"Редактор - {file_path}")
            global_signals.message_to_output.emit(f"Файл открыт: {file_path}")

            # Определяем язык по расширению
            ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
            self.highlighter.set_language(ext)
            
            # Сигнал об открытии файла
            self.file_opened.emit(file_path)
            
        except Exception as e:
            global_signals.message_to_output.emit(f"Ошибка открытия: {str(e)}")

    def get_code(self) -> str:
        """Возвращает текущий текст редактора"""
        return self.toPlainText()

    def _on_text_changed(self):
        """Слот при изменении текста"""
        self.content_changed.emit()

    def get_file_extension(self) -> str:
        """Возвращает расширение текущего файла (с точкой) или пустую строку"""
        if self.current_file_path:
            _, ext = os.path.splitext(self.current_file_path)
            return ext.lower()
        return ""