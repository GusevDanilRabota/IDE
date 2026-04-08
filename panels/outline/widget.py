"""
Панель структуры файла (Outline) - отображает классы, функции, методы.
"""
from PySide6.QtWidgets import QDockWidget, QTreeView, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt, Signal
from .model import OutlineModel
from .parser import parse_python

class OutlinePanel(QDockWidget):
    """Панель для отображения структуры текущего файла"""
    def __init__(self, parent=None):
        super().__init__("Структура", parent)
        self.setObjectName("OutlinePanel")
        self.setFeatures(QDockWidget.DockWidgetClosable |
                         QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        
        self.model = OutlineModel(self)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setAnimated(True)
        
        self.setWidget(self.tree)
        
    def update_from_code(self, code: str, file_extension: str = ".py"):
        """Парсит код и обновляет дерево"""
        if file_extension == ".py":
            nodes = parse_python(code)
        else:
            nodes = []  # для других расширений пока пусто
        self.model.set_nodes(nodes)
        self.tree.expandAll()
    
    def clear(self):
        """Очищает дерево"""
        self.model.set_nodes([])

    def update_from_code(self, code: str, file_extension: str = ".py"):
        """Парсит код и обновляет дерево в зависимости от расширения файла."""
        nodes = []
        if file_extension == ".py":
            nodes = parse_python(code)
        elif file_extension in [".c", ".h"]:
            nodes = parse_c(code)
        elif file_extension in [".asm", ".s"]:
            nodes = parse_assembly(code)
        # Можно добавить обработку других расширений
        self.model.set_nodes(nodes)
        self.tree.expandAll()