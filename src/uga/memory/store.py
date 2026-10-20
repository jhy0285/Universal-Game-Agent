import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

from uga.core.contracts import AgentEvent, ArtifactReference, TaskSpec, TaskStatus, utcnow
from uga.core.errors import UGAError


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".uga-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir(exist_ok=True)
        self.database = self.root / "uga.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                  id TEXT PRIMARY KEY, spec TEXT NOT NULL, status TEXT NOT NULL,
                  result TEXT, error TEXT, created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                  payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS checkpoints (
                  name TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS artifacts (
                  id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create_task(self, spec: TaskSpec):
        stamp = utcnow().isoformat()
        with self.connect() as db:
            db.execute(
                "INSERT INTO tasks(id,spec,status,created,updated) VALUES (?,?,?,?,?)",
                (spec.task_id, spec.model_dump_json(), TaskStatus.QUEUED, stamp, stamp),
            )

    def update_task(
        self, task_id: str, status: TaskStatus, result: dict | None = None, error: str | None = None
    ):
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE tasks SET status=?,result=?,error=?,updated=? WHERE id=?",
                (
                    status,
                    json.dumps(result, allow_nan=False) if result is not None else None,
                    error,
                    utcnow().isoformat(),
                    task_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(task_id)

    def task(self, task_id: str):
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        value = dict(row)
        for key in ("spec", "result"):
            value[key] = json.loads(value[key]) if value[key] else None
        return value

    def tasks(self, limit: int = 100):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id FROM tasks ORDER BY created DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.task(row["id"]) for row in rows]

    def append_event(self, event: AgentEvent):
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(task_id,payload) VALUES (?,?)",
                (event.task_id, event.model_dump_json()),
            )

    def events(self, task_id: str | None = None, after: int = 0, limit: int = 200):
        with self.connect() as db:
            rows = db.execute(
                "SELECT sequence,payload FROM events WHERE sequence>? AND (? IS NULL OR task_id=?) ORDER BY sequence LIMIT ?",
                (after, task_id, task_id, limit),
            ).fetchall()
        return [{"sequence": r["sequence"], **json.loads(r["payload"])} for r in rows]

    def checkpoint(self, name: str, value: dict):
        with self.connect() as db:
            db.execute(
                "INSERT INTO checkpoints VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload,updated=excluded.updated",
                (name, json.dumps(value, allow_nan=False), utcnow().isoformat()),
            )

    def load_checkpoint(self, name: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM checkpoints WHERE name=?", (name,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def put_artifact(
        self, data: bytes, media_type="application/octet-stream", suffix="bin"
    ) -> ArtifactReference:
        if not re.fullmatch(r"[a-z0-9]{1,12}", suffix):
            raise ValueError("invalid artifact suffix")
        digest = hashlib.sha256(data).hexdigest()
        path = self.artifacts / f"{digest}.{suffix}"
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise UGAError("existing artifact integrity check failed")
        else:
            fd, name = tempfile.mkstemp(prefix=".artifact-", dir=self.artifacts)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        ref = ArtifactReference(
            path=str(path.relative_to(self.root)),
            media_type=media_type,
            sha256=digest,
            size_bytes=len(data),
        )
        with self.connect() as db:
            db.execute(
                "INSERT INTO artifacts VALUES (?,?)", (ref.artifact_id, ref.model_dump_json())
            )
        return ref

    def artifact(self, artifact_id: str) -> ArtifactReference:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if not row:
            raise KeyError(artifact_id)
        return ArtifactReference.model_validate_json(row["payload"])

    def read_artifact(self, reference: ArtifactReference) -> bytes:
        path = (self.root / reference.path).resolve()
        if not path.is_relative_to(self.artifacts.resolve()):
            raise UGAError("artifact path outside store")
        data = path.read_bytes()
        if (
            len(data) != reference.size_bytes
            or hashlib.sha256(data).hexdigest() != reference.sha256
        ):
            raise UGAError("artifact integrity check failed")
        return data
