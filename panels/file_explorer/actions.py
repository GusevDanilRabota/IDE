# actions.py
import os
import shutil
import subprocess
import platform
from PySide6.QtCore import QDir, QMimeData, QUrl, Qt
from PySide6.QtGui import QAction, QDrag
from PySide6.QtWidgets import QInputDialog, QMessageBox, QFileDialog, QApplication

class FileExplorerActions:
    def __init__(self, model, proxy_model, tree_view, panel):
        self.model = model
        self.proxy_model = proxy_model
        self.tree = tree_view
        self.panel = panel

        # Существующие действия
        self.action_new_file = QAction("Новый файл")
        self.action_new_folder = QAction("Новая папка")
        self.action_delete = QAction("Удалить")
        self.action_rename = QAction("Переименовать")
        self.action_refresh = QAction("Обновить")
        self.action_show_hidden = QAction("Показывать скрытые файлы")
        self.action_show_hidden.setCheckable(True)
        self.action_open_in_explorer = QAction("Открыть в проводнике")

        # Новые действия
        self.action_add_to_pinned = QAction("Добавить в избранное")
        self.action_remove_from_pinned = QAction("Убрать из избранного")
        self.action_collapse_all = QAction("Свернуть всё")
        self.action_expand_all = QAction("Развернуть всё")
        self.action_copy_path = QAction("Копировать путь")
        self.action_move_to_trash = QAction("Переместить в корзину")

        self.action_new_file.triggered.connect(self._new_file)
        self.action_new_folder.triggered.connect(self._new_folder)
        self.action_delete.triggered.connect(self._delete)
        self.action_rename.triggered.connect(self._rename)
        self.action_refresh.triggered.connect(self._refresh)
        self.action_show_hidden.toggled.connect(self._toggle_hidden)
        self.action_open_in_explorer.triggered.connect(self._open_in_explorer)
        self.action_add_to_pinned.triggered.connect(self._add_to_pinned)
        self.action_remove_from_pinned.triggered.connect(self._remove_from_pinned)
        self.action_collapse_all.triggered.connect(self._collapse_all)
        self.action_expand_all.triggered.connect(self._expand_all)
        self.action_copy_path.triggered.connect(self._copy_path)
        self.action_move_to_trash.triggered.connect(self._move_to_trash)

        # Настройка Drag & Drop
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDragDropMode(self.tree.DragDropMode.InternalMove)
        self.tree.viewport().setAcceptDrops(True)

    def _current_path(self):
        index = self.tree.currentIndex()
        if index.isValid():
            source_index = self.proxy_model.mapToSource(index)
            return self.model.filePath(source_index)
        return self.model.rootPath()

    def _current_paths(self):
        """Возвращает список путей для множественного выбора."""
        paths = []
        for index in self.tree.selectedIndexes():
            if index.column() == 0:  # только первый столбец
                source_index = self.proxy_model.mapToSource(index)
                paths.append(self.model.filePath(source_index))
        return paths

    def _new_file(self):
        parent = self._current_path()
        if not os.path.isdir(parent):
            parent = os.path.dirname(parent)
        name, ok = QInputDialog.getText(self.tree, "Новый файл", "Имя файла:")
        if ok and name:
            path = os.path.join(parent, name)
            try:
                with open(path, 'w', encoding='utf-8'): pass
                self._refresh()
            except Exception as e:
                QMessageBox.warning(self.tree, "Ошибка", str(e))

    def _new_folder(self):
        parent = self._current_path()
        if not os.path.isdir(parent):
            parent = os.path.dirname(parent)
        name, ok = QInputDialog.getText(self.tree, "Новая папка", "Имя папки:")
        if ok and name:
            path = os.path.join(parent, name)
            try:
                os.mkdir(path)
                self._refresh()
            except Exception as e:
                QMessageBox.warning(self.tree, "Ошибка", str(e))

    def _delete(self):
        paths = self._current_paths()
        if not paths:
            return
        msg = f"Удалить {len(paths)} элемент(ов)?" if len(paths) > 1 else f"Удалить '{os.path.basename(paths[0])}'?"
        reply = QMessageBox.question(self.tree, "Подтверждение", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for path in paths:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except Exception as e:
                    QMessageBox.warning(self.tree, "Ошибка", str(e))
            self._refresh()

    def _move_to_trash(self):
        paths = self._current_paths()
        if not paths:
            return
        for path in paths:
            if not QDir.moveToTrash(path):
                QMessageBox.warning(self.tree, "Ошибка", f"Не удалось переместить в корзину: {path}")

    def _rename(self):
        path = self._current_path()
        if not path:
            return
        old = os.path.basename(path)
        new, ok = QInputDialog.getText(self.tree, "Переименовать", "Новое имя:", text=old)
        if ok and new and new != old:
            new_path = os.path.join(os.path.dirname(path), new)
            try:
                os.rename(path, new_path)
                self._refresh()
            except Exception as e:
                QMessageBox.warning(self.tree, "Ошибка", str(e))

    def _refresh(self):
        root = self.model.rootPath()
        self.model.setRootPath("")
        self.model.setRootPath(root)

    def _toggle_hidden(self, checked):
        self.panel.set_show_hidden(checked)

    def _open_in_explorer(self):
        path = self._current_path()
        if not path:
            return
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _add_to_pinned(self):
        path = self._current_path()
        if path and os.path.isdir(path):
            self.panel.add_pinned_folder(path)

    def _remove_from_pinned(self):
        path = self._current_path()
        if path:
            self.panel.remove_pinned_folder(path)

    def _collapse_all(self):
        self.tree.collapseAll()

    def _expand_all(self):
        self.tree.expandAll()

    def _copy_path(self):
        path = self._current_path()
        if path:
            QApplication.clipboard().setText(path)

    # Drag & Drop поддержка
    def startDrag(self, index):
        paths = self._current_paths()
        if not paths:
            return
        drag = QDrag(self.tree)
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(p) for p in paths]
        mime_data.setUrls(urls)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.CopyAction | Qt.MoveAction)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            target_index = self.tree.indexAt(event.pos())
            target_path = self._current_path() if target_index.isValid() else self.model.rootPath()
            if not os.path.isdir(target_path):
                target_path = os.path.dirname(target_path)
            for url in event.mimeData().urls():
                src = url.toLocalFile()
                if src and os.path.exists(src):
                    dst = os.path.join(target_path, os.path.basename(src))
                    try:
                        shutil.move(src, dst)
                    except:
                        shutil.copy2(src, dst)
            self._refresh()
            event.accept()