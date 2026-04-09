import os
import json
import hashlib
import zlib
import shutil
import time
import fnmatch
import struct
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal


class VCSRepository(QObject):
    status_changed = Signal()

    def __init__(self, repo_path: str):
        super().__init__()
        self.repo_path = os.path.abspath(repo_path)
        self.vcs_dir = os.path.join(self.repo_path, ".myvcs")
        self.objects_dir = os.path.join(self.vcs_dir, "objects")
        self.packs_dir = os.path.join(self.vcs_dir, "packs")
        self.refs_dir = os.path.join(self.vcs_dir, "refs")
        self.heads_dir = os.path.join(self.refs_dir, "heads")
        self.tags_dir = os.path.join(self.refs_dir, "tags")
        self.index_file = os.path.join(self.vcs_dir, "index.json")
        self.ignore_file = os.path.join(self.repo_path, ".myvcsignore")
        self.config_file = os.path.join(self.vcs_dir, "config")
        self.current_branch = None
        self.ignore_patterns = []
        self.staging = {}
        self._init_repo()

    # ------------------------------------------------------------------
    # Инициализация
    # ------------------------------------------------------------------
    def _init_repo(self):
        os.makedirs(self.objects_dir, exist_ok=True)
        os.makedirs(self.packs_dir, exist_ok=True)
        os.makedirs(self.heads_dir, exist_ok=True)
        os.makedirs(self.tags_dir, exist_ok=True)

        if not os.path.exists(self.vcs_dir):
            self.current_branch = "main"
            with open(os.path.join(self.vcs_dir, "HEAD"), "w") as f:
                f.write(f"ref: refs/heads/{self.current_branch}")
            self._save_branch_ref(self.current_branch, None)
            self._save_staging({})
            self._save_config()
        else:
            head_file = os.path.join(self.vcs_dir, "HEAD")
            if os.path.exists(head_file):
                with open(head_file, "r") as f:
                    ref = f.read().strip()
                    if ref.startswith("ref:"):
                        self.current_branch = ref.split("/")[-1]
            if os.path.exists(self.index_file):
                with open(self.index_file, "r") as f:
                    self.staging = json.load(f)
        self._load_ignore_patterns()

    def _save_config(self):
        config = {"version": 1, "compression": "zlib", "pack_version": 1, "hash_algorithm": "sha256"}
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def _load_ignore_patterns(self):
        if os.path.exists(self.ignore_file):
            with open(self.ignore_file, "r") as f:
                self.ignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        else:
            self.ignore_patterns = []

    def _is_ignored(self, rel_path: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                return True
        return False

    # ------------------------------------------------------------------
    # Работа с объектами
    # ------------------------------------------------------------------
    def _hash_data_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _store_blob(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            data = f.read()
        compressed = zlib.compress(data)
        blob_hash = self._hash_data_sha256(data)
        blob_path = os.path.join(self.objects_dir, blob_hash)
        if not os.path.exists(blob_path):
            with open(blob_path, "wb") as f:
                f.write(compressed)
        return blob_hash

    def _store_commit(self, commit_data: dict) -> str:
        commit_str = json.dumps(commit_data, sort_keys=True)
        compressed = zlib.compress(commit_str.encode())
        commit_hash = self._hash_data_sha256(commit_str.encode())
        commit_path = os.path.join(self.objects_dir, commit_hash)
        if not os.path.exists(commit_path):
            with open(commit_path, "wb") as f:
                f.write(compressed)
        return commit_hash

    def _read_object(self, obj_hash: str) -> Optional[bytes]:
        if obj_hash is None:
            return None
        obj_path = os.path.join(self.objects_dir, obj_hash)
        if os.path.exists(obj_path):
            with open(obj_path, "rb") as f:
                compressed = f.read()
            try:
                return zlib.decompress(compressed)
            except zlib.error:
                return None
        return None

    def _load_blob(self, blob_hash: str, target_path: str):
        if blob_hash is None:
            raise ValueError("blob_hash is None")
        data = self._read_object(blob_hash)
        if data is None:
            raise FileNotFoundError(f"Blob {blob_hash} not found")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(data)

    def _load_commit(self, commit_hash: str) -> Optional[dict]:
        if commit_hash is None:
            return None
        data = self._read_object(commit_hash)
        if data is None:
            return None
        try:
            return json.loads(data.decode())
        except:
            return None

    # ------------------------------------------------------------------
    # Ветки, staging
    # ------------------------------------------------------------------
    def _get_branch_ref(self, branch: str) -> Optional[str]:
        if branch is None:
            return None
        branch_file = os.path.join(self.heads_dir, branch)
        if os.path.exists(branch_file):
            with open(branch_file, "r") as f:
                return f.read().strip()
        return None

    def _save_branch_ref(self, branch: str, commit_hash: Optional[str]):
        if branch is None:
            return
        branch_file = os.path.join(self.heads_dir, branch)
        if commit_hash is None:
            if os.path.exists(branch_file):
                os.remove(branch_file)
        else:
            with open(branch_file, "w") as f:
                f.write(commit_hash)

    def _save_staging(self, staging_data: dict):
        self.staging = staging_data
        with open(self.index_file, "w") as f:
            json.dump(self.staging, f, indent=2)

    def add(self, rel_path: str):
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
        if not self.staging:
            raise ValueError("Нет изменений для коммита (staging area пуст)")
        parent_hash = self._get_branch_ref(self.current_branch) if self.current_branch else None
        commit_data = {
            "message": message,
            "author": author,
            "timestamp": time.time(),
            "parents": [parent_hash] if parent_hash else [],
            "tree": self.staging.copy()
        }
        commit_hash = self._store_commit(commit_data)
        self._save_branch_ref(self.current_branch, commit_hash)
        self.staging = {}
        self._save_staging(self.staging)
        self.status_changed.emit()
        return commit_hash

    def unstage(self, rel_path: str):
        if rel_path in self.staging:
            del self.staging[rel_path]
            self._save_staging(self.staging)
            self.status_changed.emit()

    def discard_changes(self, rel_path: str):
        full_path = os.path.join(self.repo_path, rel_path)
        if rel_path in self.staging:
            blob_hash = self.staging[rel_path]
            self._load_blob(blob_hash, full_path)
        else:
            commit_hash = self._get_branch_ref(self.current_branch) if self.current_branch else None
            if commit_hash:
                commit = self._load_commit(commit_hash)
                if commit and rel_path in commit['tree']:
                    blob_hash = commit['tree'][rel_path]
                    self._load_blob(blob_hash, full_path)
                else:
                    if os.path.exists(full_path):
                        os.remove(full_path)
        self.status_changed.emit()

    def get_status(self) -> Dict[str, str]:
        status = {}
        for rel_path, blob_hash in self.staging.items():
            full_path = os.path.join(self.repo_path, rel_path)
            if not os.path.exists(full_path):
                status[rel_path] = 'deleted'
            else:
                with open(full_path, "rb") as f:
                    current_hash = self._hash_data_sha256(f.read())
                if current_hash == blob_hash:
                    status[rel_path] = 'staged'
                else:
                    status[rel_path] = 'modified'
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
        if branch_or_hash is None:
            raise ValueError("Не указана ветка или коммит для переключения")
        commit_hash = self._get_branch_ref(branch_or_hash)
        if commit_hash is None:
            if self._load_commit(branch_or_hash):
                commit_hash = branch_or_hash
            else:
                raise ValueError(f"Неизвестная ветка или коммит: {branch_or_hash}")
        commit = self._load_commit(commit_hash)
        if not commit:
            raise ValueError(f"Не удалось загрузить коммит {commit_hash}")

        tree = commit.get("tree", {})
        # Получаем текущий статус файлов
        current_status = self.get_status()

        for root, dirs, files in os.walk(self.repo_path):
            if self.vcs_dir in root:
                continue
            rel_root = os.path.relpath(root, self.repo_path)
            if rel_root == '.':
                rel_root = ''
            for f in files:
                rel_path = os.path.join(rel_root, f).replace('\\', '/')
                # Удаляем только те файлы, которые находятся под контролем версий
                # и отсутствуют в новом дереве
                if rel_path not in tree:
                    if rel_path in current_status and current_status[rel_path] not in ('untracked', 'ignored'):
                        os.remove(os.path.join(root, f))

        for rel_path, blob_hash in tree.items():
            target_path = os.path.join(self.repo_path, rel_path)
            self._load_blob(blob_hash, target_path)

        self.staging = tree.copy()
        self._save_staging(self.staging)

        if self._get_branch_ref(branch_or_hash) is not None:
            self.current_branch = branch_or_hash
            with open(os.path.join(self.vcs_dir, "HEAD"), "w") as f:
                f.write(f"ref: refs/heads/{self.current_branch}")
        else:
            self.current_branch = None
            with open(os.path.join(self.vcs_dir, "HEAD"), "w") as f:
                f.write(commit_hash)
        self.status_changed.emit()

    def create_branch(self, branch_name: str):
        if branch_name is None:
            return
        current_commit = self._get_branch_ref(self.current_branch) if self.current_branch else None
        self._save_branch_ref(branch_name, current_commit)

    def get_branches(self) -> List[str]:
        if not os.path.exists(self.heads_dir):
            return []
        return [f for f in os.listdir(self.heads_dir) if os.path.isfile(os.path.join(self.heads_dir, f))]

    def get_history(self) -> List[Dict]:
        history = []
        commit_hash = self._get_branch_ref(self.current_branch) if self.current_branch else None
        while commit_hash:
            commit = self._load_commit(commit_hash)
            if not commit:
                break
            commit["hash"] = commit_hash
            commit["date"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(commit["timestamp"]))
            history.append(commit)
            parents = commit.get("parents", [])
            commit_hash = parents[0] if parents else None
        return history

    def merge(self, branch_name: str, commit_message: str):
        if branch_name is None:
            raise ValueError("Не указана ветка для слияния")
        current_commit = self._get_branch_ref(self.current_branch) if self.current_branch else None
        other_commit = self._get_branch_ref(branch_name)
        if not current_commit or not other_commit:
            raise ValueError("Нет коммитов для слияния")
        ancestor = self._find_common_ancestor(current_commit, other_commit)
        if ancestor == other_commit:
            return
        if ancestor == current_commit:
            self._save_branch_ref(self.current_branch, other_commit)
            self.checkout(self.current_branch)
            return
        merged_tree = self._merge_trees(ancestor, current_commit, other_commit)
        merge_commit = {
            "message": commit_message,
            "author": "user",
            "timestamp": time.time(),
            "parents": [current_commit, other_commit],
            "tree": merged_tree
        }
        new_hash = self._store_commit(merge_commit)
        self._save_branch_ref(self.current_branch, new_hash)
        self.status_changed.emit()

    def _find_common_ancestor(self, commit_a: str, commit_b: str) -> Optional[str]:
        if commit_a is None or commit_b is None:
            return None
        ancestors_a = set()
        cur = commit_a
        while cur:
            ancestors_a.add(cur)
            commit = self._load_commit(cur)
            if not commit:
                break
            parents = commit.get("parents", [])
            cur = parents[0] if parents else None
        cur = commit_b
        while cur:
            if cur in ancestors_a:
                return cur
            commit = self._load_commit(cur)
            if not commit:
                break
            parents = commit.get("parents", [])
            cur = parents[0] if parents else None
        return None

    def _merge_trees(self, ancestor: str, branch1: str, branch2: str) -> Dict[str, str]:
        commit1 = self._load_commit(branch1)
        commit2 = self._load_commit(branch2)
        ancestor_commit = self._load_commit(ancestor) if ancestor else None
        tree1 = commit1["tree"]
        tree2 = commit2["tree"]
        ancestor_tree = ancestor_commit["tree"] if ancestor_commit else {}
        result = {}
        all_keys = set(tree1.keys()) | set(tree2.keys())
        for key in all_keys:
            blob1 = tree1.get(key)
            blob2 = tree2.get(key)
            blob_anc = ancestor_tree.get(key)
            if blob1 == blob2:
                result[key] = blob1
            elif blob1 == blob_anc:
                result[key] = blob2
            elif blob2 == blob_anc:
                result[key] = blob1
            else:
                result[key] = blob1 if blob1 else blob2
        return result

    def create_tag(self, tag_name: str, commit_hash: str = None):
        if tag_name is None:
            return
        if commit_hash is None:
            commit_hash = self._get_branch_ref(self.current_branch) if self.current_branch else None
        if commit_hash is None:
            return
        tag_file = os.path.join(self.tags_dir, tag_name)
        with open(tag_file, "w") as f:
            f.write(commit_hash)

    def get_tags(self) -> List[str]:
        if not os.path.exists(self.tags_dir):
            return []
        return [f for f in os.listdir(self.tags_dir) if os.path.isfile(os.path.join(self.tags_dir, f))]

    def diff(self, rel_path: str) -> str:
        full_path = os.path.join(self.repo_path, rel_path)
        if not os.path.exists(full_path):
            return "Файл удалён"
        current_hash = self._hash_data_sha256(open(full_path, "rb").read())
        staged_hash = self.staging.get(rel_path)
        if staged_hash is None:
            return "Файл не в staging area"
        if current_hash == staged_hash:
            return "Нет изменений"
        return f"Файл изменён (staging: {staged_hash[:8]}, current: {current_hash[:8]})"
    
    def change_root(self, new_path: str):
        """Изменяет корень репозитория (переинициализирует)."""
        self.repo_path = os.path.abspath(new_path)
        self.vcs_dir = os.path.join(self.repo_path, ".myvcs")
        self.objects_dir = os.path.join(self.vcs_dir, "objects")
        self.packs_dir = os.path.join(self.vcs_dir, "packs")
        self.refs_dir = os.path.join(self.vcs_dir, "refs")
        self.heads_dir = os.path.join(self.refs_dir, "heads")
        self.tags_dir = os.path.join(self.refs_dir, "tags")
        self.index_file = os.path.join(self.vcs_dir, "index.json")
        self.ignore_file = os.path.join(self.repo_path, ".myvcsignore")
        self.config_file = os.path.join(self.vcs_dir, "config")
        self._init_repo()   # заново инициализирует, прочитает HEAD, staging и т.д.
        self.status_changed.emit()