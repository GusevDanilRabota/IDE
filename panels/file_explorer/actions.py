"""
Действия, доступные в панели файлов (создать папку, удалить, переименовать).
"""
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QInputDialog, QMessageBox
from PySide6.QtCore import QDir


class FileExplorerActions:
    """Контейнер для действий, связанных с файловой системой"""
    def __init__(self, model, tree_view):
        self.model = model
        self.tree = tree_view

        self.action_new_folder = QAction("Создать папку")
        self.action_delete = QAction("Удалить")
        self.action_rename = QAction("Переименовать")

        # Подключаем действия к слотам
        self.action_new_folder.triggered.connect(self._new_folder)
        self.action_delete.triggered.connect(self._delete)
        self.action_rename.triggered.connect(self._rename)

    def _current_path(self):
        """Возвращает путь к выбранному элементу"""
        index = self.tree.currentIndex()
        if index.isValid():
            return self.model.filePath(index)
        return None

    def _new_folder(self):
        """Создаёт новую папку в текущей директории"""
        parent_path = self._current_path()
        if not parent_path:
            return
        # Если выбран файл, берём его родительскую папку
        if not self.model.isDir(self.tree.currentIndex()):
            parent_path = QDir(parent_path).absolutePath()

        name, ok = QInputDialog.getText(self.tree, "Новая папка",
                                        "Имя папки:")
        if ok and name:
            new_dir = QDir(parent_path)
            if new_dir.mkdir(name):
                # Обновляем модель (она сама подхватит изменения)
                pass
            else:
                QMessageBox.warning(self.tree, "Ошибка",
                                    f"Не удалось создать папку {name}")

    def _delete(self):
        """Удаляет выбранный файл или папку"""
        path = self._current_path()
        if not path:
            return
        reply = QMessageBox.question(self.tree, "Подтверждение",
                                     f"Удалить '{path}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if QDir().removeRecursively(path):
                pass  # модель обновится автоматически
            else:
                QMessageBox.warning(self.tree, "Ошибка",
                                    "Не удалось удалить элемент")

    def _rename(self):
        """Переименовывает выбранный файл/папку"""
        path = self._current_path()
        if not path:
            return
        old_name = QDir(path).dirName()
        new_name, ok = QInputDialog.getText(self.tree, "Переименовать",
                                            "Новое имя:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = QDir(path).absolutePath().replace(old_name, new_name)
            if QDir().rename(path, new_path):
                pass
            else:
                QMessageBox.warning(self.tree, "Ошибка",
                                    "Не удалось переименовать")