# terminal_tab.py – кроссплатформенный интерактивный терминал
import os
import platform
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                               QLineEdit, QPushButton, QApplication, QFileDialog, QDialog)
from PySide6.QtCore import QProcess, Slot, Qt, QSettings, QTimer, Signal
from PySide6.QtGui import QTextCursor, QKeySequence, QShortcut, QFont

class InteractiveTerminal(QWidget):
    """Терминал с одной долгоживущей оболочкой. Работает на Windows/Linux/macOS."""
    navigate_to = Signal(str, int)  # для навигации по ошибкам

    def __init__(self, shell_path=None, shell_args=None, shell_name="Shell", parent=None):
        super().__init__(parent)
        self.shell_name = shell_name
        self.process = None
        self.current_dir = os.path.expanduser("~")
        
        # Определяем оболочку по умолчанию в зависимости от ОС
        if shell_path is None:
            if platform.system() == "Windows":
                self.shell_path = "cmd.exe"
                self.shell_args = []
                self.default_prompt = "> "
            else:
                # Linux / macOS
                self.shell_path = "/bin/bash"
                self.shell_args = ["-i"]   # интерактивный режим
                self.default_prompt = "$ "
        else:
            self.shell_path = shell_path
            self.shell_args = shell_args or []
        
        self._init_ui()
        self._init_history()
        self.start_shell()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(self._get_mono_font())
        self._apply_style()
        
        self.input_line = QLineEdit()
        self.input_line.setFont(self._get_mono_font())
        self.input_line.returnPressed.connect(self.send_command)
        
        # Кнопки
        self.clear_btn = QPushButton("Очистить")
        self.copy_btn = QPushButton("Копировать")
        self.save_btn = QPushButton("Сохранить")
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.input_line, stretch=2)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.save_btn)
        
        layout.addWidget(self.output_area, stretch=1)
        layout.addLayout(btn_layout)
        
        self.clear_btn.clicked.connect(self.clear)
        self.copy_btn.clicked.connect(self.copy_selected)
        self.save_btn.clicked.connect(self.save_to_file)
    
    def _init_history(self):
        self.history = []
        self.history_index = -1
        self.input_line.installEventFilter(self)
    
    def _get_mono_font(self):
        if platform.system() == "Windows":
            return QFont("Consolas", 9)
        elif platform.system() == "Darwin":  # macOS
            return QFont("Menlo", 11)
        else:
            return QFont("Monospace", 9)
    
    def _apply_style(self):
        self.output_area.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                selection-background-color: #264f78;
            }
        """)
    
    def start_shell(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_output)
        self.process.finished.connect(self._on_finished)
        self.process.setWorkingDirectory(self.current_dir)
        
        self.process.start(self.shell_path, self.shell_args)
        if not self.process.waitForStarted(1000):
            self.append_output(f"Ошибка запуска {self.shell_path}\n")
        else:
            self.append_output(f"Терминал [{self.shell_name}] запущен. Директория: {self.current_dir}\n")
    
    def send_command(self):
        cmd = self.input_line.text().strip()
        if not cmd:
            return
        self.history.append(cmd)
        self.history_index = len(self.history)
        self.input_line.clear()
        
        # Обработка cd (меняем директорию процесса)
        if cmd.startswith("cd "):
            self._change_directory(cmd[3:].strip())
            return
        
        self.append_output(cmd + "\n")
        # Отправляем команду в процесс с правильной кодировкой
        data = (cmd + "\n").encode(self._get_encoding(), errors='replace')
        self.process.write(data)
    
    def _change_directory(self, path):
        if os.path.isabs(path):
            new_path = path
        else:
            new_path = os.path.join(self.current_dir, path)
        new_path = os.path.normpath(new_path)
        if os.path.isdir(new_path):
            self.current_dir = new_path
            self.process.setWorkingDirectory(self.current_dir)
            self.append_output(f"Директория изменена: {self.current_dir}\n")
        else:
            self.append_output(f"cd: {path}: Нет такой директории\n")
    
    def _on_output(self):
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode(self._get_encoding(), errors='replace')
        self.append_output(text)
    
    def _on_finished(self, exit_code, exit_status):
        self.append_output(f"\n[Процесс завершён, код {exit_code}]\n")
        QTimer.singleShot(1000, self.start_shell)
    
    def _get_encoding(self):
        if platform.system() == "Windows":
            return 'cp866'
        else:
            return 'utf-8'
    
    def append_output(self, text: str):
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output_area.setTextCursor(cursor)
        self.output_area.insertPlainText(text)
        self.output_area.verticalScrollBar().setValue(
            self.output_area.verticalScrollBar().maximum()
        )
    
    def clear(self):
        self.output_area.clear()
    
    def copy_selected(self):
        cursor = self.output_area.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())
    
    def save_to_file(self, file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить вывод", "", "*.txt")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.output_area.toPlainText())
    
    # История команд
    def eventFilter(self, obj, event):
        if obj == self.input_line and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Up:
                self._history_prev()
                return True
            elif event.key() == Qt.Key_Down:
                self._history_next()
                return True
        return super().eventFilter(obj, event)
    
    def _history_prev(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.input_line.setText(self.history[self.history_index])
    
    def _history_next(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.input_line.setText(self.history[self.history_index])
        else:
            self.history_index = len(self.history)
            self.input_line.clear()
    
    def closeEvent(self, event):
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()
            self.process.waitForFinished(1000)
        super().closeEvent(event)

# Сохраняем старое имя для совместимости с multi_terminal_tab.py
terminal_tab_t = InteractiveTerminal