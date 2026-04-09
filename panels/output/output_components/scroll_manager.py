from PySide6.QtCore import QObject, QTimer

class ScrollManager(QObject):
    def __init__(self, output_area):
        super().__init__()
        self.output_area = output_area
        self.auto_scroll_enabled = True
        self._was_at_bottom = True
        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._check_scroll)
        self.output_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

    def _on_scroll_changed(self, value):
        if not self.auto_scroll_enabled:
            return
        sb = self.output_area.verticalScrollBar()
        at_bottom = value >= sb.maximum() - sb.pageStep()
        if not at_bottom and self._was_at_bottom:
            # пользователь ушел вверх – отключаем автоскролл
            self.auto_scroll_enabled = False
            self.output_area.parent().parent().parent().status_label.showMessage(
                "Автопрокрутка приостановлена (прокрутите вниз для возобновления)", 2000
            )
        elif at_bottom and not self._was_at_bottom:
            self.auto_scroll_enabled = True
        self._was_at_bottom = at_bottom

    def scroll_to_bottom(self):
        if self.auto_scroll_enabled:
            sb = self.output_area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def force_auto_scroll(self):
        self.auto_scroll_enabled = True
        self.scroll_to_bottom()

    def _check_scroll(self):
        self._on_scroll_changed(self.output_area.verticalScrollBar().value())