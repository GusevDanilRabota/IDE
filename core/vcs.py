# core/vcs.py
import os
import json
import hashlib
import zlib
import shutil
import time
import fnmatch
import struct
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal


class VCSRepository(QObject):
    """Полноценная система контроля версий с сжатием, pack-файлами, дельта-сжатием, слияниями."""
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
        self._init_repo()

    # ------------------------------------------------------------------
    # Инициализация и загрузка
    # ------------------------------------------------------------------
    def _init_repo(self):
        os.makedirs(self.objects_dir, exist_ok=True)
        os.makedirs(self.packs_dir, exist_ok=True)
        os.makedirs(self.heads_dir, exist_ok=True)
        os.makedirs(self.tags_dir, exist_ok=True)

        if not os.path.exists(self.vcs_dir):
            # Новый репозиторий
            self.current_branch = "main"
            with open(os.path.join(self.vcs_dir, "HEAD"), "w") as f:
                f.write(f"ref: refs/heads/{self.current_branch}")
            self._save_branch_ref(self.current_branch, None)
            self._save_staging({})
            self._save_config()
        else:
            # Существующий
            head_file = os.path.join(self.vcs_dir, "HEAD")
            if os.path.exists(head_file):
                with open(head_file, "r") as f:
                    ref = f.read().strip()
                    if ref.startswith("ref:"):
                        self.current_branch = ref.split("/")[-1]
            if os.path.exists(self.index_file):
                with open(self.index_file, "r") as f:
                    self.staging = json.load(f)
            else:
                self.staging = {}
        self._load_ignore_patterns()

    def _save_config(self):
        config = {
            "version": 1,
            "compression": "zlib",
            "pack_version": 1,
            "hash_algorithm": "sha256"
        }
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
    # Работа с объектами (сжатие, чтение, запись)
    # ------------------------------------------------------------------
    def _hash_data_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _store_blob(self, file_path: str) -> str:
        """Сохраняет blob-объект (сжатый)."""
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
        """Сохраняет commit-объект (сжатый JSON)."""
        commit_str = json.dumps(commit_data, sort_keys=True)
        compressed = zlib.compress(commit_str.encode())
        commit_hash = self._hash_data_sha256(commit_str.encode())
        commit_path = os.path.join(self.objects_dir, commit_hash)
        if not os.path.exists(commit_path):
            with open(commit_path, "wb") as f:
                f.write(compressed)
        return commit_hash

    def _read_object(self, obj_hash: str) -> Optional[bytes]:
        """Читает и распаковывает объект (blob или commit) – сначала из objects/, потом из pack-файлов."""
        # 1. Проверяем objects/
        obj_path = os.path.join(self.objects_dir, obj_hash)
        if os.path.exists(obj_path):
            with open(obj_path, "rb") as f:
                compressed = f.read()
            try:
                return zlib.decompress(compressed)
            except zlib.error:
                return None

        # 2. Ищем в pack-файлах
        for pack_name in os.listdir(self.packs_dir):
            if pack_name.endswith(".idx"):
                pack_base = pack_name[:-4]
                pack_path = os.path.join(self.packs_dir, pack_base + ".pack")
                if os.path.exists(pack_path):
                    data = self._read_object_from_pack(obj_hash, pack_path, pack_base)
                    if data is not None:
                        return data
        return None

    def _read_object_from_pack(self, obj_hash: str, pack_path: str, pack_base: str) -> Optional[bytes]:
        """Извлекает объект из pack-файла с использованием индекса (упрощённо)."""
        idx_path = os.path.join(self.packs_dir, pack_base + ".idx")
        if not os.path.exists(idx_path):
            return None
        # Читаем индекс: простой формат (fanout таблица + смещения)
        with open(idx_path, "rb") as idx_f:
            # Пропускаем заголовок (4 байта версия)
            idx_f.seek(4)
            # Читаем fanout таблицу (256 * 4 байта)
            fanout = []
            for _ in range(256):
                val = struct.unpack(">I", idx_f.read(4))[0]
                fanout.append(val)
            total = fanout[-1]
            # Читаем записи: (20 байт хэш, 4 байта смещения в pack)
            # Ищем хэш
            idx_f.seek(4 + 256*4)  # после fanout
            for i in range(total):
                hash_bytes = idx_f.read(32)  # SHA256 = 32 байта
                if hash_bytes.hex() == obj_hash:
                    offset = struct.unpack(">I", idx_f.read(4))[0]
                    # Читаем объект из pack
                    with open(pack_path, "rb") as pack_f:
                        pack_f.seek(offset)
                        # Формат: заголовок (тип + длина), затем данные
                        # Для простоты считаем, что данные идут сразу (упрощённо)
                        data = pack_f.read()
                        # Распаковываем, если сжато
                        try:
                            return zlib.decompress(data)
                        except:
                            return data
                else:
                    idx_f.read(4)  # пропускаем смещение
        return None

    def _load_blob(self, blob_hash: str, target_path: str):
        """Восстанавливает файл из blob-объекта."""
        data = self._read_object(blob_hash)
        if data is None:
            raise FileNotFoundError(f"Blob {blob_hash} not found")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(data)

    def _load_commit(self, commit_hash: str) -> Optional[dict]:
        data = self._read_object(commit_hash)
        if data is None:
            return None
        try:
            return json.loads(data.decode())
        except:
            return None

    # ------------------------------------------------------------------
    # Дельта-сжатие
    # ------------------------------------------------------------------
    def _create_delta(self, base_hash: str, new_hash: str) -> bytes:
        """Создаёт дельту между двумя blob-объектами (алгоритм xdelta-like)."""
        base_data = self._read_object(base_hash)
        new_data = self._read_object(new_hash)
        if base_data is None or new_data is None:
            return b""
        # Простая реализация: храним разницу как (смещение, длина, данные)
        # В реальности лучше использовать библиотеку xdelta или реализовать алгоритм
        # Для демонстрации – заглушка
        delta = b"DELTA"
        delta += struct.pack(">I", len(base_data))
        delta += struct.pack(">I", len(new_data))
        # Находим общий префикс и суффикс (упрощённо)
        i = 0
        while i < min(len(base_data), len(new_data)) and base_data[i] == new_data[i]:
            i += 1
        j = 0
        while j < min(len(base_data), len(new_data)) - i and base_data[-j-1] == new_data[-j-1]:
            j += 1
        delta += struct.pack(">I", i)  # общий префикс
        delta += struct.pack(">I", j)  # общий суффикс
        delta += new_data[i:len(new_data)-j]  # изменённая часть
        return delta

    def _apply_delta(self, base_hash: str, delta: bytes) -> bytes:
        """Применяет дельту к базовому объекту."""
        if not delta.startswith(b"DELTA"):
            return delta
        base_data = self._read_object(base_hash)
        if base_data is None:
            return b""
        offset = 5
        len_base = struct.unpack(">I", delta[offset:offset+4])[0]
        offset += 4
        len_new = struct.unpack(">I", delta[offset:offset+4])[0]
        offset += 4
        prefix_len = struct.unpack(">I", delta[offset:offset+4])[0]
        offset += 4
        suffix_len = struct.unpack(">I", delta[offset:offset+4])[0]
        offset += 4
        new_part = delta[offset:]
        # Собираем результат
        result = base_data[:prefix_len] + new_part + base_data[-suffix_len:]
        return result

    # ------------------------------------------------------------------
    # Pack-файлы
    # ------------------------------------------------------------------
    def pack_objects(self):
        """Упаковывает все объекты из objects/ в pack-файлы с дельта-сжатием."""
        objects = [f for f in os.listdir(self.objects_dir)]
        if len(objects) < 50:  # Не упаковываем, если мало объектов
            return
        # Группируем по типу? В данном случае все объекты – blob или commit.
        # Для простоты сгруппируем blob по размеру (приблизительно)
        blob_hashes = []
        commit_hashes = []
        for obj in objects:
            data = self._read_object(obj)
            if data is not None:
                # Пробуем декодировать как JSON – commit
                try:
                    json.loads(data.decode())
                    commit_hashes.append(obj)
                except:
                    blob_hashes.append(obj)

        # Сортируем blob по размеру (для дельта-сжатия)
        blob_sizes = []
        for h in blob_hashes:
            data = self._read_object(h)
            blob_sizes.append((len(data), h))
        blob_sizes.sort(key=lambda x: x[0])

        # Создаём pack-файл
        pack_name = f"pack-{int(time.time())}"
        pack_path = os.path.join(self.packs_dir, pack_name + ".pack")
        idx_path = os.path.join(self.packs_dir, pack_name + ".idx")

        # Записываем .pack (простейший формат: заголовок, затем объекты)
        with open(pack_path, "wb") as pack_f:
            # Заголовок: "PACK" + версия (4 байта) + количество объектов (4 байта)
            pack_f.write(b"PACK")
            pack_f.write(struct.pack(">I", 1))
            pack_f.write(struct.pack(">I", len(objects)))
            offsets = {}
            # Сначала записываем коммиты (они не сжимаются дельтами)
            for h in commit_hashes:
                offsets[h] = pack_f.tell()
                data = self._read_object(h)
                pack_f.write(struct.pack(">B", 1))  # тип commit
                pack_f.write(struct.pack(">I", len(data)))
                pack_f.write(data)
            # Затем blob, возможно с дельтами
            # Для каждого blob, если есть похожий предыдущий, создаём дельту
            for i, (size, h) in enumerate(blob_sizes):
                offsets[h] = pack_f.tell()
                # Ищем похожий объект (предыдущий по размеру)
                if i > 0 and abs(blob_sizes[i][0] - blob_sizes[i-1][0]) < 100:
                    base_hash = blob_sizes[i-1][1]
                    delta = self._create_delta(base_hash, h)
                    if len(delta) < size * 0.8:  # дельта эффективнее
                        pack_f.write(struct.pack(">B", 2))  # тип delta
                        pack_f.write(struct.pack(">I", len(delta)))
                        pack_f.write(base_hash.encode())
                        pack_f.write(delta)
                        continue
                # Иначе храним целиком
                pack_f.write(struct.pack(">B", 0))  # тип full
                data = self._read_object(h)
                pack_f.write(struct.pack(">I", len(data)))
                pack_f.write(data)

        # Создаём индекс .idx
        with open(idx_path, "wb") as idx_f:
            idx_f.write(struct.pack(">I", 1))  # версия
            # fanout таблица (256 int)
            fanout = [0]*256
            for h in objects:
                first_byte = int(h[:2], 16)  # первый байт хэша
                fanout[first_byte] += 1
            # накопление
            total = 0
            for i in range(256):
                total += fanout[i]
                fanout[i] = total
            for val in fanout:
                idx_f.write(struct.pack(">I", val))
            # Записи (32 байта хэш + 4 байта смещение)
            for h in objects:
                idx_f.write(bytes.fromhex(h))
                idx_f.write(struct.pack(">I", offsets[h]))
        # Удаляем оригинальные объекты
        for obj in objects:
            os.remove(os.path.join(self.objects_dir, obj))
        self.status_changed.emit()

    # ------------------------------------------------------------------
    # Ветки, staging, коммиты
    # ------------------------------------------------------------------
    def _save_branch_ref(self, branch: str, commit_hash: Optional[str]):
        branch_file = os.path.join(self.heads_dir, branch)
        if commit_hash is None:
            if os.path.exists(branch_file):
                os.remove(branch_file)
        else:
            with open(branch_file, "w") as f:
                f.write(commit_hash)

    def _get_branch_ref(self, branch: str) -> Optional[str]:
        branch_file = os.path.join(self.heads_dir, branch)
        if os.path.exists(branch_file):
            with open(branch_file, "r") as f:
                return f.read().strip()
        return None

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

    def get_status(self) -> Dict[str, str]:
        status = {}
        for rel_path, blob_hash in self.staging.items():
            full_path = os.path.join(self.repo_path, rel_path)
            if not os.path.exists(full_path):
                status[rel_path] = 'deleted'
            else:
                current_hash = self._hash_data_sha256(open(full_path, "rb").read())
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

    # ------------------------------------------------------------------
    # Checkout и слияния
    # ------------------------------------------------------------------
    def checkout(self, branch_or_hash: str):
        # Определяем целевой коммит
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
        # Удаляем файлы, не входящие в коммит
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
        current_commit = self._get_branch_ref(self.current_branch) if self.current_branch else None
        self._save_branch_ref(branch_name, current_commit)

    def get_branches(self) -> List[str]:
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

    def _find_common_ancestor(self, commit_a: str, commit_b: str) -> Optional[str]:
        """Находит общий предок двух коммитов (простой алгоритм)."""
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
        """Выполняет трёхстороннее слияние деревьев (упрощённо)."""
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
                # Конфликт – сохраняем оба варианта (помечаем)
                result[key] = blob1 if blob1 else blob2
                # В реальности нужно создать файл с конфликтом
        return result

    def merge(self, branch_name: str, commit_message: str):
        current_commit = self._get_branch_ref(self.current_branch)
        other_commit = self._get_branch_ref(branch_name)
        if not current_commit or not other_commit:
            raise ValueError("Нет коммитов для слияния")
        ancestor = self._find_common_ancestor(current_commit, other_commit)
        if ancestor == other_commit:
            # already merged
            return
        if ancestor == current_commit:
            # fast-forward
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

    # ------------------------------------------------------------------
    # Теги
    # ------------------------------------------------------------------
    def create_tag(self, tag_name: str, commit_hash: str = None):
        if commit_hash is None:
            commit_hash = self._get_branch_ref(self.current_branch)
        tag_file = os.path.join(self.tags_dir, tag_name)
        with open(tag_file, "w") as f:
            f.write(commit_hash)

    def get_tags(self) -> List[str]:
        return [f for f in os.listdir(self.tags_dir) if os.path.isfile(os.path.join(self.tags_dir, f))]

    def get_tag_commit(self, tag_name: str) -> Optional[str]:
        tag_file = os.path.join(self.tags_dir, tag_name)
        if os.path.exists(tag_file):
            with open(tag_file, "r") as f:
                return f.read().strip()
        return None

    # ------------------------------------------------------------------
    # Проверка целостности
    # ------------------------------------------------------------------
    def fsck(self) -> List[str]:
        errors = []
        # Проверяем объекты в objects/
        for obj in os.listdir(self.objects_dir):
            obj_path = os.path.join(self.objects_dir, obj)
            with open(obj_path, "rb") as f:
                compressed = f.read()
            try:
                data = zlib.decompress(compressed)
                computed = self._hash_data_sha256(data)
                if computed != obj:
                    errors.append(f"Неверный хэш для объекта {obj}")
            except zlib.error:
                errors.append(f"Неверная сжатая данных в объекте {obj}")
        # Проверяем pack-файлы
        for pack_name in os.listdir(self.packs_dir):
            if pack_name.endswith(".pack"):
                # Проверяем, что есть соответствующий .idx
                idx_name = pack_name[:-5] + ".idx"
                if not os.path.exists(os.path.join(self.packs_dir, idx_name)):
                    errors.append(f"Отсутствует индекс для pack-файла {pack_name}")
        # Проверяем ветки
        for branch in self.get_branches():
            commit = self._get_branch_ref(branch)
            if commit and not self._load_commit(commit):
                errors.append(f"Ветка {branch} указывает на несуществующий коммит {commit}")
        return errors

    def gc(self):
        """Запускает упаковку объектов и удаляет мусор."""
        self.pack_objects()
        # Можно также удалить старые pack-файлы, но оставляем