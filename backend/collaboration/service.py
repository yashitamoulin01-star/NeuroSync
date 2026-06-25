"""
Collaboration service — review threads, comments, recruiter notes.

All collaboration is anchored to interview sessions. Threads provide
structured discussion; comments support @mentions and decision tracking.
Every write is tenant-isolated and auditable.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.collaboration")


@dataclass
class CollabThread:
    thread_id:  str
    session_id: str
    tenant_id:  str
    org_id:     Optional[str]
    title:      str
    status:     str    # open | resolved | closed
    created_by: str
    created_at: float
    comments:   List["CollabComment"] = field(default_factory=list)

    def to_dict(self, include_comments: bool = False) -> Dict:
        d = {
            "thread_id":  self.thread_id,
            "session_id": self.session_id,
            "tenant_id":  self.tenant_id,
            "org_id":     self.org_id,
            "title":      self.title,
            "status":     self.status,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }
        if include_comments:
            d["comments"] = [c.to_dict() for c in self.comments]
        return d


@dataclass
class CollabComment:
    comment_id: str
    thread_id:  str
    session_id: str
    tenant_id:  str
    author_id:  str
    body:       str
    mentions:   List[str]
    created_at: float
    updated_at: float
    deleted:    bool

    def to_dict(self) -> Dict:
        return {
            "comment_id": self.comment_id,
            "thread_id":  self.thread_id,
            "session_id": self.session_id,
            "author_id":  self.author_id,
            "body":       self.body if not self.deleted else "[deleted]",
            "mentions":   self.mentions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted":    self.deleted,
        }

    @classmethod
    def from_row(cls, row) -> "CollabComment":
        return cls(
            comment_id = row["comment_id"],
            thread_id  = row["thread_id"],
            session_id = row["session_id"],
            tenant_id  = row["tenant_id"],
            author_id  = row["author_id"],
            body       = row["body"],
            mentions   = json.loads(row["mentions"] or "[]"),
            created_at = row["created_at"],
            updated_at = row["updated_at"],
            deleted    = bool(row["deleted"]),
        )


class CollaborationService:
    # ── Threads ───────────────────────────────────────────────────────────────

    def create_thread(
        self,
        session_id: str,
        tenant_id:  str,
        created_by: str,
        title:      str = "",
        org_id:     Optional[str] = None,
    ) -> CollabThread:
        thread_id  = f"thr_{uuid.uuid4().hex[:12]}"
        created_at = time.time()
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO collab_threads
                  (thread_id, session_id, tenant_id, org_id, title, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (thread_id, session_id, tenant_id, org_id, title, created_by, created_at),
            )
            con.commit()
        finally:
            con.close()
        return CollabThread(
            thread_id=thread_id, session_id=session_id, tenant_id=tenant_id,
            org_id=org_id, title=title, status="open", created_by=created_by,
            created_at=created_at,
        )

    def list_threads(self, tenant_id: str, session_id: str) -> List[CollabThread]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM collab_threads WHERE tenant_id = ? AND session_id = ? ORDER BY created_at DESC",
                (tenant_id, session_id),
            ).fetchall()
            return [
                CollabThread(
                    thread_id=r["thread_id"], session_id=r["session_id"],
                    tenant_id=r["tenant_id"], org_id=r["org_id"],
                    title=r["title"], status=r["status"],
                    created_by=r["created_by"], created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            con.close()

    def resolve_thread(self, tenant_id: str, thread_id: str, resolved_by: str) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE collab_threads SET status = 'resolved' WHERE thread_id = ? AND tenant_id = ?",
                (thread_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    # ── Comments ──────────────────────────────────────────────────────────────

    def add_comment(
        self,
        thread_id:  str,
        session_id: str,
        tenant_id:  str,
        author_id:  str,
        body:       str,
        mentions:   Optional[List[str]] = None,
    ) -> CollabComment:
        comment_id = f"cmt_{uuid.uuid4().hex[:12]}"
        now        = time.time()
        men        = mentions or []
        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO collab_comments
                  (comment_id, thread_id, session_id, tenant_id, author_id, body, mentions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (comment_id, thread_id, session_id, tenant_id, author_id, body,
                 json.dumps(men), now, now),
            )
            con.commit()
        finally:
            con.close()
        return CollabComment(
            comment_id=comment_id, thread_id=thread_id, session_id=session_id,
            tenant_id=tenant_id, author_id=author_id, body=body,
            mentions=men, created_at=now, updated_at=now, deleted=False,
        )

    def list_comments(self, tenant_id: str, thread_id: str) -> List[CollabComment]:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM collab_comments WHERE thread_id = ? AND tenant_id = ? ORDER BY created_at",
                (thread_id, tenant_id),
            ).fetchall()
            return [CollabComment.from_row(r) for r in rows]
        finally:
            con.close()

    def edit_comment(
        self, tenant_id: str, comment_id: str, author_id: str, new_body: str
    ) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE collab_comments SET body = ?, updated_at = ? WHERE comment_id = ? AND author_id = ? AND tenant_id = ? AND deleted = 0",
                (new_body, time.time(), comment_id, author_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def delete_comment(self, tenant_id: str, comment_id: str, actor_id: str) -> bool:
        con = get_enterprise_conn()
        try:
            cur = con.execute(
                "UPDATE collab_comments SET deleted = 1, updated_at = ? WHERE comment_id = ? AND tenant_id = ?",
                (time.time(), comment_id, tenant_id),
            )
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()

    def get_session_summary(self, tenant_id: str, session_id: str) -> Dict:
        con = get_enterprise_conn()
        try:
            threads = con.execute(
                "SELECT COUNT(*) FROM collab_threads WHERE tenant_id = ? AND session_id = ?",
                (tenant_id, session_id),
            ).fetchone()[0]
            open_threads = con.execute(
                "SELECT COUNT(*) FROM collab_threads WHERE tenant_id = ? AND session_id = ? AND status = 'open'",
                (tenant_id, session_id),
            ).fetchone()[0]
            comments = con.execute(
                "SELECT COUNT(*) FROM collab_comments WHERE tenant_id = ? AND session_id = ? AND deleted = 0",
                (tenant_id, session_id),
            ).fetchone()[0]
            return {
                "session_id":    session_id,
                "threads":       threads,
                "open_threads":  open_threads,
                "total_comments": comments,
            }
        finally:
            con.close()


collab_service = CollaborationService()
