# multi_terminal_tab.py
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QPushButton, QDialog, QComboBox, QLabel, QLineEdit,
    QDialogButtonBox, QMessageBox, QSplitter, QMenu, QInputDialog
)
from PySide6.QtCore import Qt
from .terminal_tab import terminal_tab_t   # изменён импорт

class multi_terminal_dialog_t(QDialog):
    # ... (без изменений, как в предыдущей версии) ...
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новый терминал")
        self.setModal(True)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Выберите командную оболочку:"))
        self.shell_combo = QComboBox()
        if platform.system() == "Windows":
            self.shell_combo.addItem("CMD", ("cmd", [], "CMD"))
            self.shell_combo.addItem("PowerShell", ("powershell", ["-Command"], "PowerShell"))
        else:
            self.shell_combo.addItem("Bash", ("/bin/bash", ["-i"], "Bash"))
            self.shell_combo.addItem("Sh", ("/bin/sh", ["-c"], "Sh"))
            if platform.system() == "Darwin":
                self.shell_combo.addItem("Zsh", ("/bin/zsh", ["-i"], "Zsh"))
        self.shell_combo.addItem("Пользовательская...", (None, None, None))
        self.shell_combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self.shell_combo)

        self.custom_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_widget)
        custom_layout.addWidget(QLabel("Путь к оболочке:"))
        self.custom_path = QLineEdit()
        custom_layout.addWidget(self.custom_path)
        custom_layout.addWidget(QLabel("Аргументы (через пробел):"))
        self.custom_args = QLineEdit()
        custom_layout.addWidget(self.custom_args)
        custom_layout.addWidget(QLabel("Отображаемое имя:"))
        self.custom_name = QLineEdit()
        custom_layout.addWidget(self.custom_name)
        layout.addWidget(self.custom_widget)
        self.custom_widget.setVisible(False)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_selection_changed(self, index):
        data = self.shell_combo.currentData()
        is_custom = (data[0] is None)
        self.custom_widget.setVisible(is_custom)

    def get_shell_config(self):
        data = self.shell_combo.currentData()
        if data[0] is not None:
            return data
        else:
            path = self.custom_path.text().strip()
            args_str = self.custom_args.text().strip()
            args = args_str.split() if args_str else []
            name = self.custom_name.text().strip() or path
            return (path, args, name)


class multi_terminal_panel_t(QWidget):
    # ... (без изменений, но импорт terminal_tab_t теперь корректен) ...
    def __init__(self, parent=None):
        super().__init__(parent)
        splitter = QSplitter(Qt.Horizontal)
        layout = QHBoxLayout(self)
        layout.addWidget(splitter)
        layout.setContentsMargins(0, 0, 0, 0)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.terminal_list = QListWidget()
        self.terminal_list.currentRowChanged.connect(self._on_current_terminal_changed)
        self.terminal_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.terminal_list.customContextMenuRequested.connect(self._show_context_menu)
        right_layout.addWidget(self.terminal_list)
        self.new_terminal_btn = QPushButton("+ Новый терминал")
        self.new_terminal_btn.clicked.connect(self._create_new_terminal)
        right_layout.addWidget(self.new_terminal_btn)

        self.terminal_stack = QStackedWidget()
        splitter.addWidget(self.terminal_stack)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 200])

        self._create_default_terminal()

    def _show_context_menu(self, pos):
        menu = QMenu()
        rename_action = menu.addAction("Переименовать")
        close_action = menu.addAction("Закрыть терминал")
        action = menu.exec(self.terminal_list.mapToGlobal(pos))
        if action == rename_action:
            self._rename_current_terminal()
        elif action == close_action:
            self._close_current_terminal()

    def _rename_current_terminal(self):
        current_row = self.terminal_list.currentRow()
        if current_row < 0:
            return
        item = self.terminal_list.item(current_row)
        old_name = item.text()
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=old_name)
        if ok and new_name:
            item.setText(new_name)
            terminal = self.terminal_stack.widget(item.data(Qt.UserRole))
            if terminal:
                terminal.shell_name = new_name

    def _close_current_terminal(self):
        current_row = self.terminal_list.currentRow()
        if current_row < 0:
            return
        if self.terminal_list.count() == 1:
            QMessageBox.warning(self, "Предупреждение", "Нельзя закрыть последний терминал.")
            return
        item = self.terminal_list.takeItem(current_row)
        index = item.data(Qt.UserRole)
        widget = self.terminal_stack.widget(index)
        self.terminal_stack.removeWidget(widget)
        widget.deleteLater()
        if self.terminal_list.count() > 0:
            self.terminal_list.setCurrentRow(0)

    def _create_default_terminal(self):
        if platform.system() == "Windows":
            shell_path = "cmd"
            shell_args = []
            shell_name = "CMD (по умолчанию)"
        else:
            shell_path = "/bin/bash"
            shell_args = ["-i"]
            shell_name = "Bash (по умолчанию)"
        self._add_terminal(shell_path, shell_args, shell_name)

    def _create_new_terminal(self):
        dialog = multi_terminal_dialog_t(self)
        if dialog.exec() == QDialog.Accepted:
            shell_path, shell_args, shell_name = dialog.get_shell_config()
            if not shell_path:
                QMessageBox.warning(self, "Ошибка", "Не указан путь к оболочке")
                return
            self._add_terminal(shell_path, shell_args, shell_name)

    def _add_terminal(self, shell_path: str, shell_args: list, shell_name: str):
        terminal = terminal_tab_t(shell_path, shell_args, shell_name, self)
        index = self.terminal_stack.addWidget(terminal)
        item = QListWidgetItem(shell_name)
        item.setData(Qt.UserRole, index)
        self.terminal_list.addItem(item)
        self.terminal_list.setCurrentItem(item)

    def _on_current_terminal_changed(self, row):
        if row < 0:
            return
        item = self.terminal_list.item(row)
        index = item.data(Qt.UserRole)
        self.terminal_stack.setCurrentIndex(index)