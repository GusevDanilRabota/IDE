# widget.py (панель структуры / VCS)
import os
from PySide6.QtWidgets import (
    QDockWidget, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeView, QPushButton, QLineEdit, QTextEdit, QLabel, QComboBox,
    QSplitter, QMessageBox, QInputDialog
)
from PySide6.QtCore import Signal, Qt
from .model import OutlineModel
from .parser import parse_python, parse_c, parse_assembly


class OutlinePanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Структура / Контроль версий", parent)
        self.setObjectName("OutlinePanel")
        self.setFeatures(QDockWidget.DockWidgetClosable |
                         QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

        self.tabs = QTabWidget()
        self.setWidget(self.tabs)

        # Вкладка структуры
        self.outline_widget = QWidget()
        outline_layout = QVBoxLayout(self.outline_widget)
        self.outline_tree = QTreeView()
        self.outline_model = OutlineModel(self)
        self.outline_tree.setModel(self.outline_model)
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.setAlternatingRowColors(True)
        outline_layout.addWidget(self.outline_tree)
        self.tabs.addTab(self.outline_widget, "Структура")

        # Вкладка VCS
        self.vcs_widget = QWidget()
        vcs_layout = QVBoxLayout(self.vcs_widget)

        # Сплиттер для staged/unstaged
        splitter = QSplitter(Qt.Vertical)

        # Staged files
        staged_widget = QWidget()
        staged_layout = QVBoxLayout(staged_widget)
        staged_layout.addWidget(QLabel("Изменения, подготовленные к коммиту (staged):"))
        self.staged_tree = QTreeView()
        self.staged_model = None
        staged_layout.addWidget(self.staged_tree)
        btn_unstage = QPushButton("<< Убрать из индекса")
        btn_unstage.clicked.connect(self._unstage_selected)
        staged_layout.addWidget(btn_unstage)
        splitter.addWidget(staged_widget)

        # Unstaged files
        unstaged_widget = QWidget()
        unstaged_layout = QVBoxLayout(unstaged_widget)
        unstaged_layout.addWidget(QLabel("Изменения, не добавленные в индекс:"))
        self.unstaged_tree = QTreeView()
        self.unstaged_model = None
        unstaged_layout.addWidget(self.unstaged_tree)
        btn_stage = QPushButton("Добавить в индекс >>")
        btn_stage.clicked.connect(self._stage_selected)
        unstaged_layout.addWidget(btn_stage)
        splitter.addWidget(unstaged_widget)

        vcs_layout.addWidget(splitter)

        # Сообщение коммита
        vcs_layout.addWidget(QLabel("Сообщение коммита:"))
        self.commit_msg = QTextEdit()
        self.commit_msg.setMaximumHeight(80)
        vcs_layout.addWidget(self.commit_msg)
        btn_commit = QPushButton("Создать коммит")
        btn_commit.clicked.connect(self._commit)
        vcs_layout.addWidget(btn_commit)

        # Ветки и теги
        branch_layout = QHBoxLayout()
        branch_layout.addWidget(QLabel("Ветка:"))
        self.branch_combo = QComboBox()
        self.branch_combo.currentTextChanged.connect(self._switch_branch)
        branch_layout.addWidget(self.branch_combo)
        btn_new_branch = QPushButton("+ Новая ветка")
        btn_new_branch.clicked.connect(self._new_branch)
        branch_layout.addWidget(btn_new_branch)
        btn_merge = QPushButton("Слияние...")
        btn_merge.clicked.connect(self._merge_branch)
        branch_layout.addWidget(btn_merge)
        vcs_layout.addLayout(branch_layout)

        tag_layout = QHBoxLayout()
        tag_layout.addWidget(QLabel("Теги:"))
        self.tag_combo = QComboBox()
        tag_layout.addWidget(self.tag_combo)
        btn_new_tag = QPushButton("Создать тег")
        btn_new_tag.clicked.connect(self._new_tag)
        tag_layout.addWidget(btn_new_tag)
        vcs_layout.addLayout(tag_layout)

        # История
        vcs_layout.addWidget(QLabel("История коммитов:"))
        self.history_tree = QTreeView()
        vcs_layout.addWidget(self.history_tree)

        self.tabs.addTab(self.vcs_widget, "Контроль версий")

        self.vcs = None

    def set_vcs(self, vcs):
        self.vcs = vcs
        self.vcs.status_changed.connect(self._refresh_all)
        self._refresh_all()

    def _refresh_all(self):
        if not self.vcs:
            return
        status = self.vcs.get_status()
        # Разделяем на staged и unstaged
        staged = {k: v for k, v in status.items() if v == 'staged'}
        unstaged = {k: v for k, v in status.items() if v in ('modified', 'deleted', 'untracked')}
        self._update_tree_model(self.staged_tree, staged)
        self._update_tree_model(self.unstaged_tree, unstaged)

        # Ветки
        branches = self.vcs.get_branches()
        self.branch_combo.clear()
        self.branch_combo.addItems(branches)
        if self.vcs.current_branch:
            idx = self.branch_combo.findText(self.vcs.current_branch)
            if idx >= 0:
                self.branch_combo.setCurrentIndex(idx)

        # Теги
        tags = self.vcs.get_tags()
        self.tag_combo.clear()
        self.tag_combo.addItems(tags)

        # История
        history = self.vcs.get_history()
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        hist_model = QStandardItemModel()
        hist_model.setHorizontalHeaderLabels(["Хэш", "Сообщение", "Дата", "Автор"])
        for commit in history:
            item_hash = QStandardItem(commit['hash'][:8])
            item_msg = QStandardItem(commit['message'])
            item_date = QStandardItem(commit['date'])
            item_author = QStandardItem(commit['author'])
            hist_model.appendRow([item_hash, item_msg, item_date, item_author])
        self.history_tree.setModel(hist_model)
        self.history_tree.resizeColumnToContents(0)

    def _update_tree_model(self, tree_view, data: dict):
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Файл", "Статус"])
        for path, st in data.items():
            item_file = QStandardItem(path)
            item_status = QStandardItem(st)
            model.appendRow([item_file, item_status])
        tree_view.setModel(model)
        tree_view.resizeColumnToContents(0)

    def _stage_selected(self):
        idx = self.unstaged_tree.currentIndex()
        if idx.isValid():
            path = idx.sibling(idx.row(), 0).data()
            if path:
                self.vcs.add(path)
                self._refresh_all()

    def _unstage_selected(self):
        idx = self.staged_tree.currentIndex()
        if idx.isValid():
            path = idx.sibling(idx.row(), 0).data()
            if path:
                self.vcs.unstage(path)
                self._refresh_all()

    def _commit(self):
        msg = self.commit_msg.toPlainText().strip()
        if not msg:
            msg = "Без сообщения"
        try:
            self.vcs.commit(msg)
            self.commit_msg.clear()
            self._refresh_all()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка коммита", str(e))

    def _new_branch(self):
        name, ok = QInputDialog.getText(self, "Новая ветка", "Имя ветки:")
        if ok and name:
            self.vcs.create_branch(name)
            self._refresh_all()

    def _merge_branch(self):
        branches = self.vcs.get_branches()
        branch, ok = QInputDialog.getItem(self, "Слияние", "Выберите ветку для слияния:", branches, 0, False)
        if ok and branch:
            msg, ok = QInputDialog.getText(self, "Сообщение слияния", "Введите сообщение для merge-коммита:")
            if ok:
                self.vcs.merge(branch, msg)
                self._refresh_all()

    def _new_tag(self):
        name, ok = QInputDialog.getText(self, "Новый тег", "Имя тега:")
        if ok and name:
            self.vcs.create_tag(name)
            self._refresh_all()

    def _switch_branch(self, branch):
        if branch and self.vcs and branch != self.vcs.current_branch:
            try:
                self.vcs.checkout(branch)
                self._refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка переключения", str(e))

    # Методы для структуры (без изменений)
    def update_from_code(self, code: str, file_extension: str = ".py"):
        if file_extension == ".py":
            nodes = parse_python(code)
        elif file_extension in [".c", ".h"]:
            nodes = parse_c(code)
        elif file_extension in [".asm", ".s"]:
            nodes = parse_assembly(code)
        else:
            nodes = []
        self.outline_model.set_nodes(nodes)
        self.outline_tree.expandAll()

    def clear(self):
        self.outline_model.set_nodes([])