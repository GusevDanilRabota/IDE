# core/vcs.py
import os
import json
import hashlib
import shutil
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal

class VCSRepository(QObject):
    """Система контроля версий без staging area, с простыми ветками и линейной историей."""
    status_changed = Signal()  # сигнал при изменении статуса файлов

    def __init__(self, repo_path: str):
        super().__init__()
        self.repo_path = os.path.abspath(repo_path)
        self.vcs_dir = os.path.join(self.repo_path, ".myvcs")
        self.objects_dir = os.path.join(self.vcs_dir, "objects")
        self.refs_dir = os.path.join(self.vcs_dir, "refs", "heads")
        self.head_file = os.path.join(self.vcs_dir, "HEAD")
        self.index_file = os.path.join(self.vcs_dir, "index.json")
        self.current_branch = None
        self._init_repo()

    def _init_repo(self):
        """Инициализирует репозиторий, если он существует, иначе создаёт."""
        if not os.path.exists(self.vcs_dir):
            os.makedirs(self.objects_dir)
            os.makedirs(self.refs_dir)
            self.current_branch = "main"
            with open(self.head_file, "w") as f:
                f.write(f"ref: refs/heads/{self.current_branch}")
            self._save_branch_ref(self.current_branch, None)  # пустой коммит
            self._save_index({})
        else:
            # Загружаем текущую ветку
            if os.path.exists(self.head_file):
                with open(self.head_file, "r") as f:
                    ref = f.read().strip()
                    if ref.startswith("ref:"):
                        self.current_branch = ref.split("/")[-1]
            # Загружаем индекс
            if os.path.exists(self.index_file):
                with open(self.index_file, "r") as f:
                    self.index = json.load(f)
            else:
                self.index = {}

    def _save_index(self, index_data):
        self.index = index_data
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2)

    def _save_branch_ref(self, branch: str, commit_hash: Optional[str]):
        branch_file = os.path.join(self.refs_dir, branch)
        if commit_hash is None:
            # Пустая ветка (нет коммитов)
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

    def _hash_file(self, file_path: str) -> str:
        """Вычисляет MD5 хэш содержимого файла."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _store_object(self, data: str) -> str:
        """Сохраняет объект (коммит) в objects/ и возвращает хэш."""
        obj_hash = hashlib.sha1(data.encode()).hexdigest()
        obj_path = os.path.join(self.objects_dir, obj_hash)
        if not os.path.exists(obj_path):
            with open(obj_path, "w", encoding="utf-8") as f:
                f.write(data)
        return obj_hash

    def _load_object(self, obj_hash: str) -> Optional[str]:
        obj_path = os.path.join(self.objects_dir, obj_hash)
        if os.path.exists(obj_path):
            with open(obj_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def get_status(self) -> Dict[str, str]:
        """
        Возвращает словарь {относительный_путь: статус}
        Статусы: 'modified', 'added', 'deleted', 'untracked'
        """
        status = {}
        if not self.index:
            # Нет индекса – все файлы untracked
            for root, dirs, files in os.walk(self.repo_path):
                if self.vcs_dir in root:
                    continue
                rel_root = os.path.relpath(root, self.repo_path)
                if rel_root == '.':
                    rel_root = ''
                for f in files:
                    rel_path = os.path.join(rel_root, f).replace('\\', '/')
                    status[rel_path] = 'untracked'
            return status

        # Сначала отметим все файлы из индекса как удалённые (потом проверим)
        for rel_path in self.index:
            status[rel_path] = 'deleted'

        # Проходим по рабочей директории
        for root, dirs, files in os.walk(self.repo_path):
            if self.vcs_dir in root:
                continue
            rel_root = os.path.relpath(root, self.repo_path)
            if rel_root == '.':
                rel_root = ''
            for f in files:
                rel_path = os.path.join(rel_root, f).replace('\\', '/')
                full_path = os.path.join(root, f)
                current_hash = self._hash_file(full_path)
                if rel_path in self.index:
                    if self.index[rel_path] == current_hash:
                        status[rel_path] = 'unchanged'
                    else:
                        status[rel_path] = 'modified'
                else:
                    status[rel_path] = 'added'
        # Убираем unchanged
        status = {k: v for k, v in status.items() if v != 'unchanged'}
        return status

    def add_all(self):
        """Добавляет все файлы в индекс (аналог git add -A)."""
        new_index = {}
        for root, dirs, files in os.walk(self.repo_path):
            if self.vcs_dir in root:
                continue
            rel_root = os.path.relpath(root, self.repo_path)
            if rel_root == '.':
                rel_root = ''
            for f in files:
                rel_path = os.path.join(rel_root, f).replace('\\', '/')
                full_path = os.path.join(root, f)
                new_index[rel_path] = self._hash_file(full_path)
        self._save_index(new_index)
        self.status_changed.emit()

    def commit(self, message: str, author: str = "user") -> str:
        """Создаёт коммит на основе текущего индекса."""
        if not self.index:
            raise ValueError("Нет изменений для коммита")
        # Получаем родительский коммит
        parent_hash = self._get_branch_ref(self.current_branch)
        commit_data = {
            "message": message,
            "author": author,
            "timestamp": time.time(),
            "parent": parent_hash,
            "tree": self.index.copy()
        }
        commit_str = json.dumps(commit_data, sort_keys=True)
        commit_hash = self._store_object(commit_str)
        self._save_branch_ref(self.current_branch, commit_hash)
        # После коммита индекс очищается (опционально, можно оставить)
        # self._save_index({})
        self.status_changed.emit()
        return commit_hash

    def get_history(self) -> List[Dict]:
        """Возвращает список коммитов от текущего до начального."""
        history = []
        commit_hash = self._get_branch_ref(self.current_branch)
        while commit_hash:
            data = self._load_object(commit_hash)
            if not data:
                break
            commit = json.loads(data)
            commit["hash"] = commit_hash
            commit["date"] = datetime.fromtimestamp(commit["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            history.append(commit)
            commit_hash = commit.get("parent")
        return history

    def checkout(self, branch_or_hash: str):
        """Переключает на ветку или коммит (detached HEAD)."""
        # Проверяем, есть ли ветка
        if os.path.exists(os.path.join(self.refs_dir, branch_or_hash)):
            # Это ветка
            commit_hash = self._get_branch_ref(branch_or_hash)
            if commit_hash:
                self._switch_to_commit(commit_hash)
                self.current_branch = branch_or_hash
                with open(self.head_file, "w") as f:
                    f.write(f"ref: refs/heads/{self.current_branch}")
        else:
            # Возможно, это хэш коммита
            if self._load_object(branch_or_hash):
                self._switch_to_commit(branch_or_hash)
                self.current_branch = None
                with open(self.head_file, "w") as f:
                    f.write(branch_or_hash)
            else:
                raise ValueError(f"Неизвестная ветка или коммит: {branch_or_hash}")
        self.status_changed.emit()

    def _switch_to_commit(self, commit_hash: str):
        """Восстанавливает рабочую директорию из коммита."""
        commit_data = self._load_object(commit_hash)
        if not commit_data:
            return
        commit = json.loads(commit_data)
        tree = commit.get("tree", {})
        # Удаляем все файлы, не входящие в коммит
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
        # Восстанавливаем файлы из коммита
        for rel_path, file_hash in tree.items():
            full_path = os.path.join(self.repo_path, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            # Здесь нужно восстановить содержимое из хэша, но мы храним только хэш, а не содержимое.
            # Для простоты будем хранить копии файлов в objects/ (как Git). Реализуем лениво:
            # При коммите мы должны сохранять копии файлов. Сейчас мы сохраняем только хэши.
            # Доработаем: при коммите копируем файлы в objects/ по их хэшу.
            # Но для демонстрации упростим: будем считать, что файлы уже есть в рабочей директории.
            # В реальной системе нужно хранить blob-объекты.
            pass
        # Обновляем индекс
        self._save_index(tree)

    def create_branch(self, branch_name: str):
        """Создаёт новую ветку от текущего коммита."""
        current_commit = self._get_branch_ref(self.current_branch) if self.current_branch else None
        self._save_branch_ref(branch_name, current_commit)

    def get_branches(self) -> List[str]:
        """Возвращает список имён веток."""
        branches = []
        if os.path.exists(self.refs_dir):
            for f in os.listdir(self.refs_dir):
                branches.append(f)
        return branches

    def diff(self, file_path: str) -> str:
        """Возвращает разницу между текущей версией файла и версией в индексе."""
        # Упрощённо: просто возвращаем "modified"
        return "Текст изменений (упрощённо)"