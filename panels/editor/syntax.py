"""
Простая подсветка синтаксиса для нескольких языков.
Использует QSyntaxHighlighter и набор правил.
"""
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression


class SyntaxHighlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса для Python, JavaScript, HTML и др."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []  # список (pattern, format)
        self._setup_python_rules()

    def set_language(self, language: str):
        """Сменить язык подсветки (расширение файла)"""
        self.rules.clear()
        if language in ('py', 'python'):
            self._setup_python_rules()
        elif language in ('js', 'javascript'):
            self._setup_javascript_rules()
        elif language in ('html', 'htm'):
            self._setup_html_rules()
        else:
            self._setup_default_rules()
        self.rehighlight()

    def _setup_python_rules(self):
        """Правила для Python"""
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(0, 0, 255))
        keyword_format.setFontWeight(QFont.Bold)

        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True',
            'try', 'while', 'with', 'yield'
        ]
        for kw in keywords:
            pattern = QRegularExpression(r'\b' + kw + r'\b')
            self.rules.append((pattern, keyword_format))

        # Строки
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(0, 128, 0))
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))

        # Комментарии
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(128, 128, 128))
        comment_format.setFontItalic(True)
        self.rules.append((QRegularExpression(r'#.*'), comment_format))

    def _setup_javascript_rules(self):
        """Заглушка для JavaScript"""
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor(0, 0, 255))
        keywords = ['function', 'var', 'let', 'const', 'if', 'else', 'return', 'for', 'while']
        for kw in keywords:
            self.rules.append((QRegularExpression(r'\b' + kw + r'\b'), kw_format))

    def _setup_html_rules(self):
        """Заглушка для HTML"""
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor(128, 0, 128))
        self.rules.append((QRegularExpression(r'<[^>]+>'), tag_format))

    def _setup_default_rules(self):
        """Правила по умолчанию (никакой подсветки)"""
        pass

    def highlightBlock(self, text):
        """Переопределённый метод: применяет все правила к блоку текста"""
        for pattern, format_ in self.rules:
            match = pattern.globalMatch(text)
            while match.hasNext():
                m = match.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), format_)