import os
from PySide6.QtCore import QSettings, Signal, Qt, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget, QTreeView, QVBoxLayout, QWidget, QLineEdit,
    QMenu, QToolBar, QComboBox, QLabel, QFileDialog
)
from .model import FileSystemModel, FileSystemProxyModel
from .actions import FileExplorerActions
from core.signals import global_signals

class FileExplorerPanel(QDockWidget):
    file_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Файлы", parent)
        self.setObjectName("FileExplorerPanel")
        self.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Панель инструментов (поиск, фильтр)
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

        self.action_change_root = QAction("Сменить корень")
        self.action_change_root.triggered.connect(self._choose_root)
        toolbar.addAction(self.action_change_root)

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
        self._vcs = None
        self._load_settings()

        settings = QSettings()
        saved_root = settings.value("file_explorer/root_path", "")
        if saved_root and os.path.isdir(saved_root):
            self.model.setRootPath(saved_root)
            self.tree.setRootIndex(self.proxy_model.mapFromSource(self.model.rootIndex()))

    def set_vcs(self, vcs):
        self._vcs = vcs
        self.update_vcs_status()
        self._vcs.status_changed.connect(self.update_vcs_status)

    def update_vcs_status(self):
        if self._vcs:
            status = self._vcs.get_status()
            self.model.set_vcs_status(status)

    def _on_double_click(self, index):
        src = self.proxy_model.mapToSource(index)
        path = self.model.filePath(src)
        if not self.model.isDir(src):
            self.file_activated.emit(path)

    def _show_context_menu(self, position):
        index = self.tree.indexAt(position)
        if index.isValid():
            self.tree.setCurrentIndex(index)
        menu = QMenu()

        # Базовые действия с файлами
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

        # Избранное (pinned folders)
        if index.isValid():
            path = self.actions._current_path()
            if path in self._pinned_folders:
                menu.addAction(self.actions.action_remove_from_pinned)
            else:
                menu.addAction(self.actions.action_add_to_pinned)
            menu.addSeparator()

        # Действия контроля версий (если VCS активна)
        if self._vcs and index.isValid():
            path = self.actions._current_path()
            try:
                rel_path = os.path.relpath(path, self.model.rootPath()).replace('\\', '/')
            except ValueError:
                rel_path = path
            status_map = self._vcs.get_status()
            status = status_map.get(rel_path)

            vcs_menu = menu.addMenu("Контроль версий")
            if status == 'untracked':
                vcs_menu.addAction("Добавить в индекс (add)", lambda: self._vcs.add(rel_path))
            elif status == 'modified':
                vcs_menu.addAction("Добавить в индекс (add)", lambda: self._vcs.add(rel_path))
                vcs_menu.addAction("Откатить изменения (discard)", lambda: self._vcs.discard_changes(rel_path))
            elif status == 'staged':
                vcs_menu.addAction("Убрать из индекса (unstage)", lambda: self._vcs.unstage(rel_path))
            if status and status != 'ignored':
                vcs_menu.addSeparator()
                vcs_menu.addAction("Показать изменения (diff)", lambda: self._show_diff(rel_path))

        # Сделать корневой папкой (добавленная функциональность)
        if index.isValid():
            src = self.proxy_model.mapToSource(index)
            if self.model.isDir(src):
                menu.addSeparator()
                menu.addAction("Сделать корневой", self._make_current_root)

        # Навигация по дереву
        menu.addAction(self.actions.action_collapse_all)
        menu.addAction(self.actions.action_expand_all)
        menu.addSeparator()
        menu.addAction(self.actions.action_refresh)
        menu.addAction(self.actions.action_show_hidden)

        # Показываем меню в глобальных координатах
        menu.exec_(self.tree.viewport().mapToGlobal(position))

    def _show_diff(self, rel_path):
        # Показать diff в отдельном окне или в панели вывода
        diff_text = self._vcs.diff(rel_path)
        from PySide6.QtWidgets import QTextEdit, QDialog, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Diff: {rel_path}")
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setPlainText(diff_text)
        layout.addWidget(text_edit)
        dlg.exec()

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

    def set_root_path(self, new_path: str):
        """Устанавливает новую корневую директорию для файлового дерева."""
        if not os.path.isdir(new_path):
            return
        # Сохраняем старый путь для сравнения
        old_path = self.model.rootPath()
        if os.path.samefile(old_path, new_path):
            return

        # Обновляем модель
        self.model.setRootPath(new_path)
        self.tree.setRootIndex(self.proxy_model.mapFromSource(self.model.rootIndex()))

        # Обновляем VCS, если он привязан
        if self._vcs:
            self._vcs.repo_path = os.path.abspath(new_path)
            self._vcs.vcs_dir = os.path.join(self._vcs.repo_path, ".myvcs")
            self._vcs._init_repo()   # переинициализируем репозиторий (создаст, если нет)
            self.update_vcs_status()

        # Сохраняем в настройках
        settings = QSettings()
        settings.setValue("file_explorer/root_path", new_path)

        # Оповещаем другие компоненты (например, центральный редактор)
        global_signals.message_to_output.emit(f"Корневая папка изменена: {new_path}")

        # Обновляем заголовок окна или статус-бар (опционально)
        main_window = self.window()
        if hasattr(main_window, 'setWindowTitle'):
            main_window.setWindowTitle(f"IDE COLLECTIVE - {new_path}")
        global_signals.root_path_changed.emit(new_path)

    def _choose_root(self):
        """Открывает диалог выбора папки и устанавливает её как корневую."""
        new_root = QFileDialog.getExistingDirectory(self, "Выбрать корневую папку", self.model.rootPath())
        if new_root:
            self.set_root_path(new_root)

    def _make_current_root(self):
        """Устанавливает текущую выбранную папку как корневую."""
        path = self.actions._current_path()
        if path and os.path.isdir(path):
            self.set_root_path(path)