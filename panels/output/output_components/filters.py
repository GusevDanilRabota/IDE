import re
from PySide6.QtCore import QObject

class FilterManager(QObject):
    def __init__(self):
        super().__init__()
        self.type_filter = "ALL"   # ALL, INFO, ERROR, WARNING
        self.regex_pattern = None
        self.regex_obj = None

    def set_type_filter(self, filter_type: str):
        self.type_filter = filter_type
        self._update_regex()

    def set_regex(self, pattern: str):
        if pattern:
            try:
                self.regex_obj = re.compile(pattern, re.IGNORECASE)
                self.regex_pattern = pattern
            except re.error:
                self.regex_obj = None
                self.regex_pattern = None
        else:
            self.regex_obj = None
            self.regex_pattern = None
        self._update_regex()

    def _update_regex(self):
        # комбинированный фильтр (тип + regex) будет применяться в OutputTab
        pass

    def should_display(self, msg_type: str, text: str) -> bool:
        if self.type_filter != "ALL" and msg_type != self.type_filter:
            return False
        if self.regex_obj:
            return bool(self.regex_obj.search(text))
        return True