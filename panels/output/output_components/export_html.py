import html
from datetime import datetime
from PySide6.QtCore import QObject

class HtmlExporter(QObject):
    @staticmethod
    def export(messages, output_path: str):
        """
        messages: список (full_text, msg_type, timestamp)
        """
        rows = []
        for full_text, msg_type, timestamp in messages:
            color = "#d4d4d4"
            if msg_type == "ERROR":
                color = "#f14c4c"
            elif msg_type == "WARNING":
                color = "#e5c07b"
            escaped = html.escape(full_text).replace('\n', '<br>')
            rows.append(f'<span style="color:{color};">{escaped}</span>')
        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Вывод IDE Collective</title>
<style>body {{ background:#1e1e1e; color:#d4d4d4; font-family: monospace; }}</style>
</head><body>
{' '.join(rows)}
</body></html>"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)