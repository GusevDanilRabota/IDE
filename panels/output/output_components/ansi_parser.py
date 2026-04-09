import re
from PySide6.QtGui import QTextCharFormat, QColor

# Простейший парсер ANSI escape codes (только цвета SGR)
# Поддерживает: \033[ ... m
class AnsiParser:
    def __init__(self):
        # Сброс формата
        self.reset_format = QTextCharFormat()
        self.reset_format.setForeground(QColor("#d4d4d4"))
        self.reset_format.setBackground(QColor("#1e1e1e"))

    def parse(self, text: str) -> list:
        """
        Разбивает текст на фрагменты (str, QTextCharFormat).
        Возвращает список кортежей (фрагмент_текста, формат).
        """
        fragments = []
        current_format = QTextCharFormat(self.reset_format)
        pos = 0
        # Ищем CSI последовательности вида \033[ ... m
        pattern = re.compile(r'\x1b\[([0-9;]*)m')
        for match in pattern.finditer(text):
            start, end = match.span()
            # текст до последовательности
            if start > pos:
                fragments.append((text[pos:start], current_format))
            # обрабатываем код
            codes = match.group(1)
            if codes == '' or codes == '0':
                current_format = QTextCharFormat(self.reset_format)
            else:
                for code in codes.split(';'):
                    try:
                        code = int(code)
                    except:
                        continue
                    if code == 1:  # bold
                        # в QTextCharFormat нет прямого bold, можно через weight
                        current_format.setFontWeight(700)
                    elif code == 30: current_format.setForeground(QColor("black"))
                    elif code == 31: current_format.setForeground(QColor("red"))
                    elif code == 32: current_format.setForeground(QColor("green"))
                    elif code == 33: current_format.setForeground(QColor("yellow"))
                    elif code == 34: current_format.setForeground(QColor("blue"))
                    elif code == 35: current_format.setForeground(QColor("magenta"))
                    elif code == 36: current_format.setForeground(QColor("cyan"))
                    elif code == 37: current_format.setForeground(QColor("white"))
                    elif code == 90: current_format.setForeground(QColor("gray"))
                    elif code == 91: current_format.setForeground(QColor("lightcoral"))
                    elif code == 92: current_format.setForeground(QColor("lightgreen"))
                    elif code == 93: current_format.setForeground(QColor("lightyellow"))
                    elif code == 94: current_format.setForeground(QColor("lightblue"))
                    elif code == 95: current_format.setForeground(QColor("lightmagenta"))
                    elif code == 96: current_format.setForeground(QColor("lightcyan"))
                    elif code == 97: current_format.setForeground(QColor("white"))
            pos = end
        # остаток текста
        if pos < len(text):
            fragments.append((text[pos:], current_format))
        return fragments