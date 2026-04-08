"""
Модель дерева для отображения структуры файла.
"""
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from .parser import OutlineNode

class OutlineModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_nodes = []  # список корневых OutlineNode

    def set_nodes(self, nodes):
        """Обновляет модель новым списком корневых узлов"""
        self.beginResetModel()
        self.root_nodes = nodes
        self.endResetModel()

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            parent_node = None
        else:
            parent_node = parent.internalPointer()
        
        if parent_node is None:
            if row < len(self.root_nodes):
                return self.createIndex(row, column, self.root_nodes[row])
        else:
            if row < len(parent_node.children):
                return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        parent_node = node.parent
        if parent_node is None:
            return QModelIndex()
        # Найти родителя среди корневых узлов или внутри другого узла
        if parent_node.parent is None:
            # родитель - корневой
            row = self.root_nodes.index(parent_node)
            return self.createIndex(row, 0, parent_node)
        else:
            # родитель - не корневой, найти его среди детей своего родителя
            grandparent = parent_node.parent
            row = grandparent.children.index(parent_node)
            return self.createIndex(row, 0, parent_node)

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self.root_nodes)
        node = parent.internalPointer()
        return len(node.children)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == Qt.DisplayRole:
            # Отображаем имя и вид
            if node.kind == 'class':
                return f"📦 {node.name}"
            elif node.kind == 'function':
                return f"⚙️ {node.name}"
            elif node.kind == 'method':
                return f"🔧 {node.name}"
            return node.name
        elif role == Qt.ToolTipRole:
            return f"{node.kind.capitalize()} на строке {node.line}"
        return None