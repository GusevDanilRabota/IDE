# core/theme.py


class Theme:
    # Тёмная тема (VS Code)
    BACKGROUND = "#1E1E1E"
    PANEL_BG = "#252526"
    PANEL_TITLE_BG = "#2D2D30"
    TEXT = "#CCCCCC"
    SELECTION_BG = "#264F78"
    HOVER_BG = "#2A2D2E"
    ACTIVE_BG = "#3E3E42"
    ACCENT = "#007ACC"

    # Цвета сообщений
    INFO_COLOR = "#D4D4D4"  # светло-серый
    ERROR_COLOR = "#F14C4C"  # красный
    WARNING_COLOR = "#E5C07B"  # жёлтый

    # Терминал (можно переопределить)
    TERMINAL_BG = "#1E1E1E"
    TERMINAL_TEXT = "#CCCCCC"

    @classmethod
    def get_message_color(cls, msg_type: str) -> str:
        return {
            "ERROR": cls.ERROR_COLOR,
            "WARNING": cls.WARNING_COLOR,
            "INFO": cls.INFO_COLOR,
        }.get(msg_type, cls.INFO_COLOR)
