from PySide6.QtWidgets import QMenu, QApplication
from PySide6.QtCore import QPoint
from PySide6.QtGui import QTextCursor

class OutputContextMenu:
    def __init__(self, output_area, parent_widget):
        self.output_area = output_area
        self.parent = parent_widget

    def show(self, position: QPoint):
        cursor = self.output_area.cursorForPosition(position)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line_text = cursor.selectedText()
        menu = QMenu()
        copy_line = menu.addAction("Копировать строку")
        copy_all = menu.addAction("Копировать всё")
        menu.addSeparator()
        filter_by = menu.addAction("Показать только строки, содержащие...")
        menu.addSeparator()
        clear_action = menu.addAction("Очистить")
        action = menu.exec_(self.output_area.viewport().mapToGlobal(position))
        if action == copy_line:
            QApplication.clipboard().setText(line_text)
        elif action == copy_all:
            QApplication.clipboard().setText(self.output_area.toPlainText())
        elif action == filter_by:
            # Вызываем диалог для фильтрации по тексту (regex)
            self.parent._show_regex_filter_dialog(line_text.strip())
        elif action == clear_action:
            self.parent.clear_output()