# widget.py
from PySide6.QtWidgets import QDockWidget, QTabWidget, QWidget, QVBoxLayout, QTreeView, QPushButton, QLineEdit, QTextEdit, QHBoxLayout, QLabel, QComboBox
from PySide6.QtCore import Signal, Qt
from .model import OutlineModel
from .parser import parse_python, parse_c, parse_assembly
from core.vcs import VCSRepository
import os

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
        self.vcs_status_tree = QTreeView()
        self.vcs_status_model = None  # будет заполняться
        vcs_layout.addWidget(QLabel("Изменённые файлы:"))
        vcs_layout.addWidget(self.vcs_status_tree)
        self.commit_msg = QTextEdit()
        self.commit_msg.setPlaceholderText("Сообщение коммита...")
        self.commit_msg.setMaximumHeight(80)
        vcs_layout.addWidget(self.commit_msg)
        btn_layout = QHBoxLayout()
        self.commit_btn = QPushButton("Коммит")
        self.refresh_btn = QPushButton("Обновить")
        self.branch_combo = QComboBox()
        self.new_branch_btn = QPushButton("+ Ветка")
        btn_layout.addWidget(self.commit_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(QLabel("Ветка:"))
        btn_layout.addWidget(self.branch_combo)
        btn_layout.addWidget(self.new_branch_btn)
        vcs_layout.addLayout(btn_layout)
        self.history_list = QTreeView()
        vcs_layout.addWidget(QLabel("История коммитов:"))
        vcs_layout.addWidget(self.history_list)
        self.tabs.addTab(self.vcs_widget, "Контроль версий")

        self.vcs = None
        self.current_project_path = None

        # вкладка VCS (дополнить)
        self.staged_tree = QTreeView()
        self.unstaged_tree = QTreeView()
        # кнопки: Stage (>>), Unstage (<<), Diff, Discard

        # Сигналы
        self.commit_btn.clicked.connect(self._commit)
        self.refresh_btn.clicked.connect(self._refresh_vcs)
        self.new_branch_btn.clicked.connect(self._new_branch)
        self.branch_combo.currentTextChanged.connect(self._switch_branch)

    def set_project_root(self, path):
        """Устанавливает корень проекта и инициализирует VCS."""
        self.current_project_path = path
        self.vcs = VCSRepository(path)
        self._refresh_vcs()

    def update_from_code(self, code: str, file_extension: str = ".py"):
        """Обновляет вкладку структуры."""
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

    def _refresh_vcs(self):
        if not self.vcs:
            return
        status = self.vcs.get_status()
        # Обновляем дерево статусов (упрощённо – просто список)
        # В реальности используем QStandardItemModel
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Файл", "Статус"])
        for path, st in status.items():
            item_file = QStandardItem(path)
            item_status = QStandardItem(st)
            model.appendRow([item_file, item_status])
        self.vcs_status_tree.setModel(model)
        self.vcs_status_tree.resizeColumnToContents(0)

        # Обновляем историю
        history = self.vcs.get_history()
        hist_model = QStandardItemModel()
        hist_model.setHorizontalHeaderLabels(["Хэш", "Сообщение", "Дата", "Автор"])
        for commit in history:
            item_hash = QStandardItem(commit['hash'][:8])
            item_msg = QStandardItem(commit['message'])
            item_date = QStandardItem(commit['date'])
            item_author = QStandardItem(commit['author'])
            hist_model.appendRow([item_hash, item_msg, item_date, item_author])
        self.history_list.setModel(hist_model)
        self.history_list.resizeColumnToContents(0)

        # Обновляем список веток
        branches = self.vcs.get_branches()
        self.branch_combo.clear()
        self.branch_combo.addItems(branches)
        if self.vcs.current_branch:
            idx = self.branch_combo.findText(self.vcs.current_branch)
            if idx >= 0:
                self.branch_combo.setCurrentIndex(idx)

    def _commit(self):
        msg = self.commit_msg.toPlainText().strip()
        if not msg:
            msg = "Без сообщения"
        try:
            self.vcs.add_all()
            self.vcs.commit(msg)
            self.commit_msg.clear()
            self._refresh_vcs()
        except Exception as e:
            print(f"Ошибка коммита: {e}")

    def _new_branch(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Новая ветка", "Имя ветки:")
        if ok and name:
            self.vcs.create_branch(name)
            self._refresh_vcs()

    def _switch_branch(self, branch):
        if branch and self.vcs and branch != self.vcs.current_branch:
            try:
                self.vcs.checkout(branch)
                self._refresh_vcs()
            except Exception as e:
                print(f"Ошибка переключения: {e}")