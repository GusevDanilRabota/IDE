# model.py
import os
import hashlib
from PySide6.QtCore import QDir, Qt, QSortFilterProxyModel, QTimer
from PySide6.QtWidgets import QFileSystemModel, QFileIconProvider
from PySide6.QtGui import QColor

class FileSystemModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRootPath(QDir.currentPath())
        self.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.icon_provider = QFileIconProvider()
        self.icon_cache = {}  # кэш иконок по расширению

    def rootIndex(self):
        return self.index(self.rootPath())

    def isDir(self, index):
        return self.fileInfo(index).isDir()

    def filePath(self, index):
        return self.fileInfo(index).absoluteFilePath()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DecorationRole:
            info = self.fileInfo(index)
            ext = os.path.splitext(info.fileName())[1].lower()
            if ext in self.icon_cache:
                return self.icon_cache[ext]
            icon = self.icon_provider.icon(info)
            self.icon_cache[ext] = icon
            return icon
        elif role == Qt.ForegroundRole:
            # Статус VCS можно будет добавить позже через дополнительную модель
            pass
        return super().data(index, role)


class FileSystemProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._show_hidden = False
        self._filter_text = ""
        self._extension_filter = []   # список расширений (например, ['.py', '.txt'])
        self._pinned_folders = []     # список избранных путей

    def set_show_hidden(self, show):
        self._show_hidden = show
        self.invalidateFilter()

    def set_filter_text(self, text):
        self._filter_text = text.strip().lower()
        self.invalidateFilter()

    def set_extension_filter(self, extensions):
        self._extension_filter = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]
        self.invalidateFilter()

    def set_pinned_folders(self, folders):
        self._pinned_folders = folders
        self.invalidate()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        file_name = model.fileName(index)
        file_path = model.filePath(index)

        # Скрытые файлы
        if not self._show_hidden:
            if file_name.startswith('.'):
                return False
            info = model.fileInfo(index)
            if info.isHidden():
                return False

        # Поиск по имени
        if self._filter_text:
            if self._filter_text not in file_name.lower():
                return False

        # Фильтр по расширению (только для файлов)
        if self._extension_filter and not model.isDir(index):
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in self._extension_filter:
                return False

        return True

    def lessThan(self, left, right):
        """Сортировка: избранные папки, потом папки, потом файлы, затем по имени."""
        model = self.sourceModel()
        left_idx = self.mapToSource(left)
        right_idx = self.mapToSource(right)
        left_path = model.filePath(left_idx)
        right_path = model.filePath(right_idx)
        left_is_dir = model.isDir(left_idx)
        right_is_dir = model.isDir(right_idx)

        # Избранные папки всегда сверху
        left_pinned = left_path in self._pinned_folders
        right_pinned = right_path in self._pinned_folders
        if left_pinned != right_pinned:
            return left_pinned

        if left_is_dir and not right_is_dir:
            return True
        if not left_is_dir and right_is_dir:
            return False

        left_name = model.fileName(left_idx)
        right_name = model.fileName(right_idx)
        return left_name.lower() < right_name.lower()