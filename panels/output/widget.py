# widget.py
from PySide6.QtWidgets import QDockWidget, QTabWidget
from .output_data_tab import output_data_tab_t
from .multi_terminal_tab import multi_terminal_panel_t

class interaction_panel_t(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Вывод", parent)
        self.setObjectName("interaction_panel")
        self.setFeatures(
            QDockWidget.DockWidgetClosable |
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable
        )

        self.tabs = QTabWidget()
        self.output_data_tab = output_data_tab_t()
        self.terminal_panel = multi_terminal_panel_t()

        self.tabs.addTab(self.output_data_tab, "Вывод данных")
        self.tabs.addTab(self.terminal_panel, "Терминал")

        self.setWidget(self.tabs)

    def append_message(self, text: str, msg_type: str = "INFO"):
        self.output_data_tab.append_message(text, msg_type)