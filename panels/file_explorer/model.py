"""
Модель файловой системы, наследующая QFileSystemModel.
Добавляет дополнительную логику (например, фильтрацию файлов).
"""
from PySide6.QtCore import QDir
from PySide6.QtWidgets import QFileSystemModel


class FileSystemModel(QFileSystemModel):
    """Расширенная модель файловой системы"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Устанавливаем корневую директорию (текущая рабочая папка)
        self.setRootPath(QDir.currentPath())

    def rootIndex(self):
        """Возвращает индекс корневого элемента для отображения в дереве"""
        return self.index(self.rootPath())

    def isDir(self, index):
        """Проверяет, является ли элемент папкой"""
        return self.fileInfo(index).isDir()

    def filePath(self, index):
        """Возвращает полный путь к файлу/папке по индексу"""
        return self.fileInfo(index).absoluteFilePath()