# core/vcs.py
import os
import json
import hashlib
import shutil
import time
import fnmatch
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal


class VCSRepository(QObject):
    """Полноценная система контроля версий с staging area, ветками, blobs, .myvcsignore."""
    status_changed = Signal()

    def __init__(self, repo_path: str):
        super().__init__()
        self.repo_path = os.path.abspath(repo_path)
        self.vcs_dir = os.path.join(self.repo_path, ".myvcs")
        self.objects_dir = os.path.join(self.vcs_dir, "objects")
        self.refs_dir = os.path.join(self.vcs_dir, "refs", "heads")
        self.head_file = os.path.join(self.vcs_dir, "HEAD")
        self.index_file = os.path.join(self.vcs_dir, "index.json")      # staging area
        self.ignore_file = os.path.join(self.repo_path, ".myvcsignore")
        self.current_branch = None
        self.ignore_patterns = []
        self._init_repo()

    def _init_repo(self):
        """Инициализирует репозиторий, загружает настройки."""
        if not os.path.exists(self.vcs_dir):
            os.makedirs(self.objects_dir)
            os.makedirs(self.refs_dir)
            self.current_branch = "main"
            with open(self.head_file, "w") as f:
                f.write(f"ref: refs/heads/{self.current_branch}")
            self._save_branch_ref(self.current_branch, None)
            self._save_staging({})
        else:
            # Загрузка текущей ветки
            if os.path.exists(self.head_file):
                with open(self.head_file, "r") as f:
                    ref = f.read().strip()
                    if ref.startswith("ref:"):
                        self.current_branch = ref.split("/")[-1]
            # Загрузка staging area
            if os.path.exists(self.index_file):
                with open(self.index_file, "r") as f:
                    self.staging = json.load(f)
            else:
                self.staging = {}
        # Загрузка .myvcsignore
        self._load_ignore_patterns()

    def _load_ignore_patterns(self):
        if os.path.exists(self.ignore_file):
            with open(self.ignore_file, "r") as f:
                self.ignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        else:
            self.ignore_patterns = []

    def _is_ignored(self, rel_path: str) -> bool:
        """Проверяет, игнорируется ли файл/папка."""
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                return True
        return False

    def _hash_file_sha256(self, file_path: str) -> str:
        """Вычисляет SHA256 хэш содержимого файла."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _store_blob(self, file_path: str) -> str:
        """Сохраняет содержимое файла как blob-объект в objects/ под SHA256 хэшем."""
        blob_hash = self._hash_file_sha256(file_path)
        blob_path = os.path.join(self.objects_dir, blob_hash)
        if not os.path.exists(blob_path):
            shutil.copy2(file_path, blob_path)
        return blob_hash

    def _load_blob(self, blob_hash: str, target_path: str):
        """Восстанавливает файл из blob-объекта."""
        src = os.path.join(self.objects_dir, blob_hash)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(src, target_path)

    def _store_commit(self, commit_data: dict) -> str:
        """Сохраняет коммит (JSON) в objects/ под SHA256 хэшем содержимого."""
        commit_str = json.dumps(commit_data, sort_keys=True)
        commit_hash = hashlib.sha256(commit_str.encode()).hexdigest()
        commit_path = os.path.join(self.objects_dir, commit_hash)
        if not os.path.exists(commit_path):
            with open(commit_path, "w", encoding="utf-8") as f:
                f.write(commit_str)
        return commit_hash

    def _load_commit(self, commit_hash: str) -> Optional[dict]:
        commit_path = os.path.join(self.objects_dir, commit_hash)
        if os.path.exists(commit_path):
            with open(commit_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _save_branch_ref(self, branch: str, commit_hash: Optional[str]):
        branch_file = os.path.join(self.refs_dir, branch)
        if commit_hash is None:
            if os.path.exists(branch_file):
                os.remove(branch_file)
        else:
            with open(branch_file, "w") as f:
                f.write(commit_hash)

    def _get_branch_ref(self, branch: str) -> Optional[str]:
        branch_file = os.path.join(self.refs_dir, branch)
        if os.path.exists(branch_file):
            with open(branch_file, "r") as f:
                return f.read().strip()
        return None

    def _save_staging(self, staging_data: dict):
        self.staging = staging_data
        with open(self.index_file, "w") as f:
            json.dump(self.staging, f, indent=2)

    def add(self, rel_path: str):
        """Добавляет конкретный файл в staging area."""
        full_path = os.path.join(self.repo_path, rel_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Файл не существует: {rel_path}")
        if self._is_ignored(rel_path):
            return
        blob_hash = self._store_blob(full_path)
        self.staging[rel_path] = blob_hash
        self._save_staging(self.staging)
        self.status_changed.emit()

    def add_all(self):
        """Добавляет все неигнорируемые файлы в staging area."""
        new_staging = {}
        for root, dirs, files in os.walk(self.repo_path):
            if self.vcs_dir in root:
                continue
            rel_root = os.path.relpath(root, self.repo_path)
            if rel_root == '.':
                rel_root = ''
            for f in files:
                rel_path = os.path.join(rel_root, f).replace('\\', '/')
                if self._is_ignored(rel_path):
                    continue
                full_path = os.path.join(root, f)
                new_staging[rel_path] = self._store_blob(full_path)
        self.staging = new_staging
        self._save_staging(self.staging)
        self.status_changed.emit()

    def commit(self, message: str, author: str = "user") -> str:
        """Создаёт коммит из текущего staging area."""
        if not self.staging:
            raise ValueError("Нет изменений для коммита (staging area пуст)")
        parent_hash = self._get_branch_ref(self.current_branch) if self.current_branch else None
        commit_data = {
            "message": message,
            "author": author,
            "timestamp": time.time(),
            "parent": parent_hash,
            "tree": self.staging.copy()   # ссылки на blob-объекты
        }
        commit_hash = self._store_commit(commit_data)
        self._save_branch_ref(self.current_branch, commit_hash)
        # После коммита staging area очищается (опционально, можно оставить)
        self.staging = {}
        self._save_staging(self.staging)
        self.status_changed.emit()
        return commit_hash

    def get_status(self) -> Dict[str, str]:
        """
        Возвращает статус для каждого файла в рабочей директории и staging.
        Статусы: 'staged' (в staging), 'modified' (изменён относительно staging),
                 'deleted' (удалён из ФС, но в staging), 'untracked' (не в staging),
                 'ignored' (игнорируемый).
        """
        status = {}
        # Сначала все файлы из staging считаем потенциально изменёнными/удалёнными
        for rel_path, blob_hash in self.staging.items():
            full_path = os.path.join(self.repo_path, rel_path)
            if not os.path.exists(full_path):
                status[rel_path] = 'deleted'
            else:
                current_hash = self._hash_file_sha256(full_path)
                if current_hash == blob_hash:
                    status[rel_path] = 'staged'
                else:
                    status[rel_path] = 'modified'

        # Проходим по рабочей директории, добавляем untracked/ignored
        for root, dirs, files in os.walk(self.repo_path):
            if self.vcs_dir in root:
                continue
            rel_root = os.path.relpath(root, self.repo_path)
            if rel_root == '.':
                rel_root = ''
            for f in files:
                rel_path = os.path.join(rel_root, f).replace('\\', '/')
                if rel_path in status:
                    continue
                if self._is_ignored(rel_path):
                    status[rel_path] = 'ignored'
                else:
                    status[rel_path] = 'untracked'
        return status

    def checkout(self, branch_or_hash: str):
        """Переключает на ветку или коммит (detached HEAD) и восстанавливает рабочую директорию."""
        # Определяем целевой коммит
        commit_hash = self._get_branch_ref(branch_or_hash)
        if commit_hash is None:
            # Возможно, это хэш коммита
            if self._load_commit(branch_or_hash):
                commit_hash = branch_or_hash
            else:
                raise ValueError(f"Неизвестная ветка или коммит: {branch_or_hash}")

        # Загружаем коммит
        commit = self._load_commit(commit_hash)
        if not commit:
            raise ValueError(f"Не удалось загрузить коммит {commit_hash}")

        tree = commit.get("tree", {})

        # Удаляем все файлы, не входящие в коммит (и не в .myvcs)
        for root, dirs, files in os.walk(self.repo_path):
            if self.vcs_dir in root:
                continue
            rel_root = os.path.relpath(root, self.repo_path)
            if rel_root == '.':
                rel_root = ''
            for f in files:
                rel_path = os.path.join(rel_root, f).replace('\\', '/')
                if rel_path not in tree:
                    os.remove(os.path.join(root, f))

        # Восстанавливаем файлы из blobs
        for rel_path, blob_hash in tree.items():
            target_path = os.path.join(self.repo_path, rel_path)
            self._load_blob(blob_hash, target_path)

        # Обновляем staging area (становится точной копией коммита)
        self.staging = tree.copy()
        self._save_staging(self.staging)

        # Обновляем HEAD
        if self._get_branch_ref(branch_or_hash) is not None:
            # Это ветка
            self.current_branch = branch_or_hash
            with open(self.head_file, "w") as f:
                f.write(f"ref: refs/heads/{self.current_branch}")
        else:
            # Detached HEAD
            self.current_branch = None
            with open(self.head_file, "w") as f:
                f.write(commit_hash)

        self.status_changed.emit()

    def create_branch(self, branch_name: str):
        """Создаёт новую ветку от текущего коммита."""
        current_commit = self._get_branch_ref(self.current_branch) if self.current_branch else None
        if current_commit is None and self.current_branch is not None:
            # Пустая ветка (нет коммитов)
            self._save_branch_ref(branch_name, None)
        else:
            self._save_branch_ref(branch_name, current_commit)

    def get_branches(self) -> List[str]:
        branches = []
        if os.path.exists(self.refs_dir):
            branches = [f for f in os.listdir(self.refs_dir)]
        return branches

    def get_history(self) -> List[Dict]:
        history = []
        commit_hash = self._get_branch_ref(self.current_branch) if self.current_branch else None
        while commit_hash:
            commit = self._load_commit(commit_hash)
            if not commit:
                break
            commit["hash"] = commit_hash
            commit["date"] = datetime.fromtimestamp(commit["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            history.append(commit)
            commit_hash = commit.get("parent")
        return history

    def diff(self, rel_path: str) -> str:
        """Возвращает различия между текущей версией файла и версией в staging area."""
        full_path = os.path.join(self.repo_path, rel_path)
        if not os.path.exists(full_path):
            return "Файл удалён"
        current_hash = self._hash_file_sha256(full_path)
        staged_hash = self.staging.get(rel_path)
        if staged_hash is None:
            return "Файл не в staging area"
        if current_hash == staged_hash:
            return "Нет изменений"
        # Здесь можно реализовать настоящий diff (difflib.unified_diff)
        # Для краткости – заглушка
        return f"Файл изменён (хэши: staging={staged_hash[:8]}, current={current_hash[:8]})"

    def unstage(self, rel_path: str):
        """Убирает файл из staging area (без удаления из ФС)."""
        if rel_path in self.staging:
            del self.staging[rel_path]
            self._save_staging(self.staging)
            self.status_changed.emit()

    def discard_changes(self, rel_path: str):
        """Откатывает изменения в файле до версии из staging area."""
        if rel_path in self.staging:
            blob_hash = self.staging[rel_path]
            target_path = os.path.join(self.repo_path, rel_path)
            self._load_blob(blob_hash, target_path)
            self.status_changed.emit()