from PySide6.QtCore import QObject, Signal, QRegularExpression
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor

class SearchManager(QObject):
    def __init__(self, output_area):
        super().__init__()
        self.output_area = output_area
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor("#ffcc00"))
        self.highlight_format.setForeground(QColor("#000000"))
        self.current_match = 0
        self.matches = []  # список QTextCursor

    def find_all(self, pattern: str, use_regex: bool = False):
        """Находит все совпадения и подсвечивает их."""
        self.clear_highlights()
        self.matches.clear()
        if not pattern:
            return 0
        doc = self.output_area.document()
        cursor = QTextCursor(doc)
        if use_regex:
            regex = QRegularExpression(pattern)
            if not regex.isValid():
                return 0
            while not cursor.isNull():
                cursor = doc.find(regex, cursor)
                if not cursor.isNull():
                    self.matches.append(QTextCursor(cursor))
                    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
        else:
            while not cursor.isNull():
                cursor = doc.find(pattern, cursor)
                if not cursor.isNull():
                    self.matches.append(QTextCursor(cursor))
                    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
        # Подсветка всех
        for match in self.matches:
            self.output_area.setTextCursor(match)
            self.output_area.textCursor().mergeCharFormat(self.highlight_format)
        self.current_match = 0 if not self.matches else -1
        return len(self.matches)

    def clear_highlights(self):
        # Сбрасываем формат для всего документа
        cursor = QTextCursor(self.output_area.document())
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.clearBackground()
        cursor.mergeCharFormat(fmt)
        # Переприменяем цветовую раскраску (вызываем refresh у родителя)
        # Просто перезагружаем вывод
        parent = self.output_area.parent()
        if hasattr(parent, 'refresh_display'):
            parent.refresh_display()

    def next_match(self):
        if not self.matches:
            return False
        self.current_match = (self.current_match + 1) % len(self.matches)
        cursor = self.matches[self.current_match]
        self.output_area.setTextCursor(cursor)
        self.output_area.centerCursor()
        return True

    def prev_match(self):
        if not self.matches:
            return False
        self.current_match = (self.current_match - 1) % len(self.matches)
        cursor = self.matches[self.current_match]
        self.output_area.setTextCursor(cursor)
        self.output_area.centerCursor()
        return True