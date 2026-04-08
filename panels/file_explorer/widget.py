"""
Виджет панели файлов (QDockWidget), содержащий дерево файловой системы.
"""
from PySide6.QtWidgets import QDockWidget, QTreeView, QMenu
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction

from .model import FileSystemModel
from .actions import FileExplorerActions


class FileExplorerPanel(QDockWidget):
    """Панель с деревом каталогов и контекстным меню"""
    file_activated = Signal(str)   # испускается при двойном клике по файлу

    def __init__(self, parent=None):
        super().__init__("Файлы", parent)
        self.setObjectName("FileExplorerPanel")
        self.setFeatures(QDockWidget.DockWidgetClosable |
                         QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

        # Модель и представление
        self.model = FileSystemModel(self)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.rootIndex())
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)

        self.setWidget(self.tree)

        # Действия (создание папки, удаление и т.д.)
        self.actions = FileExplorerActions(self.model, self.tree)

        # Подключаем сигналы
        self.tree.doubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

    def _on_double_click(self, index):
        path = self.model.filePath(index)
        if not self.model.isDir(index):
            self.file_activated.emit(path)

    def _show_context_menu(self, position):
        """Показывает контекстное меню для текущего элемента"""
        index = self.tree.indexAt(position)
        if not index.isValid():
            return

        menu = QMenu()
        menu.addAction(self.actions.action_new_folder)
        menu.addAction(self.actions.action_delete)
        menu.addSeparator()
        menu.addAction(self.actions.action_rename)
        menu.exec_(self.tree.viewport().mapToGlobal(position))