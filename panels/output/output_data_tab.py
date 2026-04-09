from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QPushButton, QInputDialog
from PySide6.QtCore import Signal
from .output_tab import OutputTab

class output_data_tab_t(QWidget):
    navigate_to = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        layout.addWidget(self.tabs)

        # Кнопка добавления новой вкладки
        self.add_tab_btn = QPushButton("+ Новая вкладка")
        self.add_tab_btn.clicked.connect(self._add_new_tab)
        layout.addWidget(self.add_tab_btn)

        # Создаём стандартные вкладки
        self._add_tab("Общий")
        self._add_tab("Сборка")
        self._add_tab("Отладка")
        self._add_tab("Тесты")

    def _add_tab(self, title: str):
        tab = OutputTab(title)
        self.tabs.addTab(tab, title)
        return tab

    def _add_new_tab(self):
        name, ok = QInputDialog.getText(self, "Новая вкладка", "Имя вкладки:")
        if ok and name:
            self._add_tab(name)

    def _close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.append_message("Нельзя закрыть последнюю вкладку", "WARNING")

    def append_message(self, text: str, msg_type: str = "INFO", tab_name: str = None):
        """Добавляет сообщение в указанную вкладку (или текущую)"""
        if tab_name:
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == tab_name:
                    tab = self.tabs.widget(i)
                    tab.append_message(text, msg_type)
                    return
        # если вкладка не найдена или tab_name не задан – используем текущую
        current = self.tabs.currentWidget()
        if current:
            current.append_message(text, msg_type)
        else:
            # на всякий случай
            self._add_tab("Общий")
            self.tabs.currentWidget().append_message(text, msg_type)

    def clear_output(self):
        current = self.tabs.currentWidget()
        if current:
            current.clear_output()

    def set_show_timestamp(self, show: bool):
        for i in range(self.tabs.count()):
            self.tabs.widget(i).show_timestamp = show
            self.tabs.widget(i).refresh_display()

    # Проброс остальных методов для совместимости (фильтры, поиск и т.д.)
    # Они делегируются активной вкладке
    def _on_type_filter_changed(self, text):
        self.tabs.currentWidget().filter_type_combo.setCurrentText(text)