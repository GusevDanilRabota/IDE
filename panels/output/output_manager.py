from PySide6.QtWidgets import QTabWidget, QMenu, QWidget
from PySide6.QtCore import Signal, Qt
from .base_output_tab import BaseOutputTab
from .output_data_tab import output_data_tab_t
from .terminal_tab import InteractiveTerminal

class OutputManager(QTabWidget):
    """Управляет вкладками панели вывода. Позволяет добавлять/удалять вкладки."""
    tab_closed = Signal(QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Создаём вкладки по умолчанию
        self.output_tab = output_data_tab_t()
        self.add_tab(self.output_tab, "Output")
        self.terminal_tab = InteractiveTerminal(shell_name="Terminal")
        self.add_tab(self.terminal_tab, "Terminal")
    
    def add_tab(self, tab: BaseOutputTab, title: str):
        """Добавляет новую вкладку."""
        index = self.addTab(tab, title)
        self.setCurrentIndex(index)
        # Если вкладка поддерживает сигнал closed, подключаем
        if hasattr(tab, 'closed'):
            tab.closed.connect(lambda: self._close_tab(self.indexOf(tab)))
        return index
    
    def _close_tab(self, index):
        widget = self.widget(index)
        if widget:
            # Спрашиваем подтверждение, если нужно (можно опционально)
            self.removeTab(index)
            widget.deleteLater()
            self.tab_closed.emit(widget)
    
    def _show_context_menu(self, pos):
        menu = QMenu()
        menu.addAction("Закрыть", lambda: self._close_tab(self.currentIndex()))
        menu.addAction("Закрыть все", self._close_all_tabs)
        menu.addSeparator()
        menu.addAction("Новая вкладка вывода", self._new_output_tab)
        menu.addAction("Новый терминал", self._new_terminal_tab)
        menu.exec_(self.mapToGlobal(pos))
    
    def _close_all_tabs(self):
        # Оставляем хотя бы одну вкладку? Можно оставить по желанию
        for i in reversed(range(self.count())):
            self._close_tab(i)
    
    def _new_output_tab(self):
        tab = output_data_tab_t()
        name = f"Output {self.count()+1}"
        self.add_tab(tab, name)
    
    def _new_terminal_tab(self):
        tab = InteractiveTerminal(shell_name=f"Terminal {self.count()+1}")
        self.add_tab(tab, tab.windowTitle())