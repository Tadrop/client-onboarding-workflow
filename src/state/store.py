"""SQLite-backed durable store.

One table per aggregate. Rows hold a JSON blob plus the columns we need to
query on (run_id, milestone, key). Writes happen on a per-call basis with
short-lived connections — fine for a single-process onboarding agent and keeps
the test fixtures trivial.

Idempotency key is `{run_id}:{milestone}:{step}`; storing the previous result
lets repeated integration calls return the same answer (Slack channel already
exists → return existing instead of erroring or duplicating).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..config import get_settings
from ..schemas import (
    AMReview,
    Draft,
    IdempotencyRecord,
    MilestoneName,
    OnboardingRun,
    ReviewDecision,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_runs (
    run_id TEXT PRIMARY KEY,
    envelope_id TEXT NOT NULL,
    contract_type TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_envelope ON onboarding_runs(envelope_id);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    milestone TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES onboarding_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_drafts_run ON drafts(run_id);

CREATE TABLE IF NOT EXISTS am_reviews (
    review_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    milestone TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES onboarding_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_reviews_run ON am_reviews(run_id);
CREATE INDEX IF NOT EXISTS idx_reviews_pending ON am_reviews(decision);

CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    milestone TEXT NOT NULL,
    step TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _sqlite_path_from_url(url: str) -> str:
    """Turn `sqlite:///./data/onboarding.db` or `:memory:` into a usable path."""
    if url == "sqlite:///:memory:" or url == ":memory:":
        return ":memory:"
    if url.startswith("sqlite:///"):
        return url.removeprefix("sqlite:///")
    parsed = urlparse(url)
    if parsed.scheme == "sqlite":
        return parsed.path.lstrip("/")
    return url


class Store:
    """Durable storage for onboarding runs and AM drafts/reviews.

    Thread-safe at the SQLite level (each call opens a short-lived connection).
    """

    def __init__(self, database_url: str) -> None:
        self._path = _sqlite_path_from_url(database_url)
        self._lock = threading.Lock()
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._shared_conn: sqlite3.Connection | None = None
        else:
            # in-memory DBs only persist for the lifetime of a single connection,
            # so we keep one open for the lifetime of the Store.
            self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        if self._shared_conn is not None:
            with self._lock:
                yield self._shared_conn
                self._shared_conn.commit()
            return
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)

    # ─── OnboardingRun ───────────────────────────────────────────────────────

    def save_run(self, run: OnboardingRun) -> None:
        payload = run.model_dump_json()
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO onboarding_runs "
                "(run_id, envelope_id, contract_type, data, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    run.run_id,
                    run.contract.envelope_id,
                    run.contract.contract_type.value,
                    payload,
                    run.created_at.isoformat(),
                ),
            )

    def get_run(self, run_id: str) -> OnboardingRun | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM onboarding_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        return OnboardingRun.model_validate_json(row["data"])

    def find_run_by_envelope(self, envelope_id: str) -> OnboardingRun | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM onboarding_runs WHERE envelope_id = ?", (envelope_id,)
            ).fetchone()
        if not row:
            return None
        return OnboardingRun.model_validate_json(row["data"])

    def list_runs(self) -> list[OnboardingRun]:
        with self._conn() as c:
            rows = c.execute("SELECT data FROM onboarding_runs ORDER BY created_at DESC").fetchall()
        return [OnboardingRun.model_validate_json(r["data"]) for r in rows]

    # ─── Drafts ──────────────────────────────────────────────────────────────

    def save_draft(self, draft: Draft) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO drafts "
                "(draft_id, run_id, milestone, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    draft.draft_id,
                    draft.run_id,
                    draft.milestone.value,
                    draft.model_dump_json(),
                    draft.created_at.isoformat(),
                ),
            )

    def get_draft(self, draft_id: str) -> Draft | None:
        with self._conn() as c:
            row = c.execute("SELECT data FROM drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        if not row:
            return None
        return Draft.model_validate_json(row["data"])

    def drafts_for_run(self, run_id: str) -> list[Draft]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT data FROM drafts WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [Draft.model_validate_json(r["data"]) for r in rows]

    def find_draft(self, run_id: str, milestone: MilestoneName) -> Draft | None:
        """Most-recent draft for a (run, milestone), if any."""
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM drafts WHERE run_id = ? AND milestone = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (run_id, milestone.value),
            ).fetchone()
        if not row:
            return None
        return Draft.model_validate_json(row["data"])

    # ─── AM Reviews ──────────────────────────────────────────────────────────

    def save_review(self, review: AMReview) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO am_reviews "
                "(review_id, run_id, milestone, draft_id, decision, data, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    review.review_id,
                    review.run_id,
                    review.milestone.value,
                    review.draft_id,
                    review.decision.value,
                    review.model_dump_json(),
                    review.created_at.isoformat(),
                ),
            )

    def get_review(self, review_id: str) -> AMReview | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM am_reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
        if not row:
            return None
        return AMReview.model_validate_json(row["data"])

    def reviews_for_run(self, run_id: str) -> list[AMReview]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT data FROM am_reviews WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [AMReview.model_validate_json(r["data"]) for r in rows]

    def list_pending_reviews(self) -> list[AMReview]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT data FROM am_reviews WHERE decision = ? ORDER BY created_at",
                (ReviewDecision.PENDING.value,),
            ).fetchall()
        return [AMReview.model_validate_json(r["data"]) for r in rows]

    def find_review_for_draft(self, draft_id: str) -> AMReview | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM am_reviews WHERE draft_id = ? ORDER BY created_at DESC LIMIT 1",
                (draft_id,),
            ).fetchone()
        if not row:
            return None
        return AMReview.model_validate_json(row["data"])

    # ─── Idempotency ─────────────────────────────────────────────────────────

    @staticmethod
    def idempotency_key(run_id: str, milestone: MilestoneName, step: str) -> str:
        return f"{run_id}:{milestone.value}:{step}"

    def get_idempotent(
        self, run_id: str, milestone: MilestoneName, step: str
    ) -> dict[str, Any] | None:
        key = self.idempotency_key(run_id, milestone, step)
        with self._conn() as c:
            row = c.execute("SELECT data FROM idempotency WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        rec = IdempotencyRecord.model_validate_json(row["data"])
        return rec.result

    def put_idempotent(
        self,
        run_id: str,
        milestone: MilestoneName,
        step: str,
        result: dict[str, Any],
    ) -> None:
        key = self.idempotency_key(run_id, milestone, step)
        rec = IdempotencyRecord(
            key=key, run_id=run_id, milestone=milestone, step=step, result=result
        )
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO idempotency "
                "(key, run_id, milestone, step, data, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    run_id,
                    milestone.value,
                    step,
                    rec.model_dump_json(),
                    rec.created_at.isoformat(),
                ),
            )


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store(get_settings().database_url)


def reset_store_cache() -> None:
    """Tests can call this to get a fresh store (e.g. after changing the URL)."""
    get_store.cache_clear()
