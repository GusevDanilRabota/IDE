import re
import os
from typing import Optional, Tuple

class ErrorParser:
    """Парсит строки вывода в поисках ссылок на файлы и строки."""
    
    # Регулярные выражения для разных форматов
    PATTERNS = [
        # Python: File "path", line 42
        re.compile(r'File "([^"]+)", line (\d+)'),
        # GCC/Clang: path:line:col: error
        re.compile(r'^([^:]+):(\d+):\d*:'),
        # MSVC: path(line) : error
        re.compile(r'^([^(]+)\((\d+)\)\s*:'),
        # Дополнительно: просто path:line
        re.compile(r'([a-zA-Z]:[^:]+|\.[/\\][^:]+|[^:]+):(\d+)'),
    ]
    
    @classmethod
    def parse_line(cls, text: str) -> Optional[Tuple[str, int]]:
        """
        Возвращает (file_path, line_number) или None.
        file_path нормализуется в абсолютный путь, если существует.
        """
        for pattern in cls.PATTERNS:
            match = pattern.search(text)
            if match:
                file_path, line_str = match.groups()
                try:
                    line = int(line_str)
                except ValueError:
                    continue
                # Преобразуем относительный путь в абсолютный, если файл существует
                if not os.path.isabs(file_path):
                    # Пробуем относительно текущей рабочей директории IDE
                    cwd = os.getcwd()
                    abs_path = os.path.abspath(os.path.join(cwd, file_path))
                    if os.path.exists(abs_path):
                        return abs_path, line
                    # Иначе возвращаем как есть (редактор попробует найти)
                    return file_path, line
                else:
                    return file_path, line
        return None