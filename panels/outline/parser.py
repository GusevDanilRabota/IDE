# panels/outline/parser.py
import re
from typing import List

# Импортируем pycparser только если он установлен
try:
    from pycparser import c_parser, c_ast
    PYPARSER_AVAILABLE = True
except ImportError:
    PYPARSER_AVAILABLE = False
    c_parser = None
    c_ast = None
    print("pycparser не установлен. Поддержка C отключена.")

# --- Вспомогательный класс для парсинга C ---
class OutlineNode:
    def __init__(self, name: str, line: int, kind: str, parent=None):
        self.name = name
        self.line = line
        self.kind = kind   # 'class', 'function', 'method', 'label'
        self.parent = parent
        self.children = []

    def add_child(self, node):
        node.parent = self
        self.children.append(node)

# --- Парсер для Python ---
def parse_python(source_code: str) -> List[OutlineNode]:
    """Парсит Python код и возвращает список корневых узлов."""
    lines = source_code.splitlines()
    root_nodes = []
    stack = []  # для отслеживания вложенности: список (indent_level, node)

    class_re = re.compile(r'^\s*class\s+(\w+)\s*(?:\(|:)')
    func_re = re.compile(r'^\s*def\s+(\w+)\s*\(')

    for line_num, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Проверяем, не закончилась ли вложенность
        while stack and indent <= stack[-1][0]:
            stack.pop()

        class_match = class_re.match(line)
        if class_match:
            class_name = class_match.group(1)
            node = OutlineNode(class_name, line_num, 'class')
            if stack:
                stack[-1][1].add_child(node)
            else:
                root_nodes.append(node)
            stack.append((indent, node))
            continue

        func_match = func_re.match(line)
        if func_match:
            func_name = func_match.group(1)
            kind = 'method' if stack else 'function'
            node = OutlineNode(func_name, line_num, kind)
            if stack:
                stack[-1][1].add_child(node)
            else:
                root_nodes.append(node)
            # Функции не создают вложенности, поэтому не добавляем в стек
    return root_nodes


# --- Парсер для C (с использованием pycparser) ---
if PYPARSER_AVAILABLE:
    class _CFuncVisitor(c_ast.NodeVisitor):
        """Внутренний класс для обхода AST и сбора функций C."""
        def __init__(self):
            self.functions = []

        def visit_FuncDef(self, node):
            """Вызывается при обнаружении определения функции."""
            func_name = node.decl.name
            func_line = node.coord.line if node.coord else -1
            self.functions.append(OutlineNode(func_name, func_line, 'function'))

def parse_c(source_code: str) -> List[OutlineNode]:
    """
    Парсит C код, извлекая определения функций.
    Требует установки pycparser.
    """
    if not PYPARSER_AVAILABLE:
        return []

    parser = c_parser.CParser()
    root_nodes = []
    try:
        # Парсим код. Для корректной работы могут потребоваться заглушки для системных заголовков.
        ast = parser.parse(source_code)
        visitor = _CFuncVisitor()
        visitor.visit(ast)
        root_nodes = visitor.functions
    except Exception as e:
        # Если pycparser не может разобрать код (например, из-за отсутствия заголовков), просто возвращаем пустой список
        print(f"Ошибка парсинга C: {e}")
        return []
    return root_nodes


# --- Парсер для ассемблера ---
def parse_assembly(source_code: str) -> List[OutlineNode]:
    """
    Парсит ассемблерный код (x86/x64), извлекая метки.
    Метка определяется как слово в начале строки, за которым следует двоеточие.
    """
    root_nodes = []
    for line_num, line in enumerate(source_code.splitlines(), start=1):
        stripped = line.strip()
        # Ищем метку: слово в начале строки, за которым сразу идёт двоеточие
        match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):', stripped)
        if match:
            label = match.group(1)
            node = OutlineNode(label, line_num, 'label')
            root_nodes.append(node)
    return root_nodes