import os
from PySide6.QtCore import QSettings, Signal, Qt, QSize
from PySide6.QtWidgets import (
    QDockWidget, QTreeView, QVBoxLayout, QWidget, QLineEdit,
    QMenu, QToolBar, QComboBox, QLabel, QPushButton, QHBoxLayout
)
from .model import FileSystemModel, FileSystemProxyModel
from .actions import FileExplorerActions

class FileExplorerPanel(QDockWidget):
    file_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Файлы", parent)
        self.setObjectName("FileExplorerPanel")
        self.setFeatures(QDockWidget.DockWidgetClosable |
                         QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Панель инструментов
        toolbar = QToolBar()
        icon_size = self.style().pixelMetric(self.style().PixelMetric.PM_SmallIconSize)
        toolbar.setIconSize(QSize(icon_size, icon_size))

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Все файлы", "")
        self.filter_combo.addItem("Python (*.py)", ".py")
        self.filter_combo.addItem("JavaScript (*.js)", ".js")
        self.filter_combo.addItem("C/C++ (*.c,*.cpp,*.h)", ".c.cpp.h")
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(QLabel("Фильтр:"))
        toolbar.addWidget(self.filter_combo)
        toolbar.addSeparator()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Поиск файлов...")
        self.search_bar.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_bar)
        layout.addWidget(toolbar)

        # Дерево
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(12)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.AscendingOrder)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setSelectionMode(self.tree.SelectionMode.ExtendedSelection)

        self.model = FileSystemModel(self)
        self.proxy_model = FileSystemProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.tree.setModel(self.proxy_model)
        self.tree.setRootIndex(self.proxy_model.mapFromSource(self.model.rootIndex()))

        self.actions = FileExplorerActions(self.model, self.proxy_model, self.tree, self)

        layout.addWidget(self.tree)
        self.setWidget(main_widget)

        # Сигналы
        self.tree.doubleClicked.connect(self._on_double_click)

        # Настройки
        self._show_hidden = False
        self._pinned_folders = []
        self._load_settings()

    def _on_double_click(self, index):
        src = self.proxy_model.mapToSource(index)
        path = self.model.filePath(src)
        if not self.model.isDir(src):
            self.file_activated.emit(path)

    def _show_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if index.isValid():
            self.tree.setCurrentIndex(index)
        menu = QMenu()
        menu.addAction(self.actions.action_new_file)
        menu.addAction(self.actions.action_new_folder)
        menu.addSeparator()
        menu.addAction(self.actions.action_delete)
        menu.addAction(self.actions.action_move_to_trash)
        menu.addAction(self.actions.action_rename)
        menu.addSeparator()
        menu.addAction(self.actions.action_copy_path)
        menu.addAction(self.actions.action_open_in_explorer)
        menu.addSeparator()
        if index.isValid():
            path = self.actions._current_path()
            if path in self._pinned_folders:
                menu.addAction(self.actions.action_remove_from_pinned)
            else:
                menu.addAction(self.actions.action_add_to_pinned)
        menu.addSeparator()
        menu.addAction(self.actions.action_collapse_all)
        menu.addAction(self.actions.action_expand_all)
        menu.addSeparator()
        menu.addAction(self.actions.action_refresh)
        menu.addAction(self.actions.action_show_hidden)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _on_search_changed(self, text):
        self.proxy_model.set_filter_text(text)

    def _on_filter_changed(self, idx):
        data = self.filter_combo.itemData(idx)
        if data:
            extensions = data.split('.')
            self.proxy_model.set_extension_filter(extensions)
        else:
            self.proxy_model.set_extension_filter([])

    def set_show_hidden(self, show):
        self._show_hidden = show
        self.proxy_model.set_show_hidden(show)
        self.actions.action_show_hidden.setChecked(show)
        self._save_settings()

    def add_pinned_folder(self, path):
        if path not in self._pinned_folders:
            self._pinned_folders.append(path)
            self.proxy_model.set_pinned_folders(self._pinned_folders)
            self._save_settings()

    def remove_pinned_folder(self, path):
        if path in self._pinned_folders:
            self._pinned_folders.remove(path)
            self.proxy_model.set_pinned_folders(self._pinned_folders)
            self._save_settings()

    def reveal_file(self, file_path):
        if not os.path.exists(file_path):
            return
        src_index = self.model.index(file_path)
        if src_index.isValid():
            proxy_index = self.proxy_model.mapFromSource(src_index)
            self.tree.setCurrentIndex(proxy_index)
            self.tree.scrollTo(proxy_index)
            self.tree.expand(proxy_index.parent())

    def _load_settings(self):
        settings = QSettings()
        self._show_hidden = settings.value("file_explorer/show_hidden", False, type=bool)
        self.set_show_hidden(self._show_hidden)
        self._pinned_folders = settings.value("file_explorer/pinned_folders", [], type=list)
        self.proxy_model.set_pinned_folders(self._pinned_folders)

    def _save_settings(self):
        settings = QSettings()
        settings.setValue("file_explorer/show_hidden", self._show_hidden)
        settings.setValue("file_explorer/pinned_folders", self._pinned_folders)

    def refresh(self):
        self.actions._refresh()