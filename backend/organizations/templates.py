"""
Interview template versioning.

Templates define the structure of an interview: question banks, evaluation
criteria, behavioral dimensions, scoring weights, and required modalities.
Every change creates a new immutable version; the template points to the
current version number.

Templates are org-scoped and tenant-isolated.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.services.enterprise_db import get_enterprise_conn

logger = logging.getLogger("neurosync.templates")


@dataclass
class EvaluationCriterion:
    name:        str
    description: str
    weight:      float = 1.0
    dimension:   str   = "confidence"    # maps to behavioral dimension


@dataclass
class TemplateConfig:
    interview_type:       str                      = "behavioral"
    question_bank:        List[Dict[str, Any]]     = field(default_factory=list)
    evaluation_criteria:  List[EvaluationCriterion] = field(default_factory=list)
    dimensions:           List[str]                = field(default_factory=lambda: [
        "confidence", "stress", "engagement", "communication", "consistency"
    ])
    dimension_weights:    Dict[str, float]         = field(default_factory=lambda: {
        "confidence": 1.0, "stress": 0.8, "engagement": 0.9,
        "communication": 1.0, "consistency": 0.7,
    })
    expected_duration_min: int                     = 45
    required_modalities:  List[str]                = field(default_factory=lambda: ["face", "audio"])
    scoring_policy:       str                      = "weighted_average"
    pass_threshold:       float                    = 0.65

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_type":       self.interview_type,
            "question_bank":        self.question_bank,
            "evaluation_criteria":  [c.__dict__ for c in self.evaluation_criteria],
            "dimensions":           self.dimensions,
            "dimension_weights":    self.dimension_weights,
            "expected_duration_min": self.expected_duration_min,
            "required_modalities":  self.required_modalities,
            "scoring_policy":       self.scoring_policy,
            "pass_threshold":       self.pass_threshold,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "TemplateConfig":
        criteria = [
            EvaluationCriterion(**c) for c in d.get("evaluation_criteria", [])
        ]
        return cls(
            interview_type        = d.get("interview_type", "behavioral"),
            question_bank         = d.get("question_bank", []),
            evaluation_criteria   = criteria,
            dimensions            = d.get("dimensions", ["confidence", "stress", "engagement", "communication", "consistency"]),
            dimension_weights     = d.get("dimension_weights", {}),
            expected_duration_min = d.get("expected_duration_min", 45),
            required_modalities   = d.get("required_modalities", ["face", "audio"]),
            scoring_policy        = d.get("scoring_policy", "weighted_average"),
            pass_threshold        = d.get("pass_threshold", 0.65),
        )


@dataclass
class TemplateVersion:
    version_id:  str
    template_id: str
    version_num: int
    config:      TemplateConfig
    created_by:  str
    created_at:  float

    def to_dict(self) -> Dict:
        return {
            "version_id":  self.version_id,
            "template_id": self.template_id,
            "version_num": self.version_num,
            "config":      self.config.to_dict(),
            "created_by":  self.created_by,
            "created_at":  self.created_at,
        }


@dataclass
class InterviewTemplate:
    template_id:      str
    org_id:           str
    tenant_id:        str
    name:             str
    interview_type:   str
    description:      str
    status:           str     # active | archived | draft
    current_version:  int
    created_by:       str
    created_at:       float

    def to_dict(self) -> Dict:
        return {
            "template_id":     self.template_id,
            "org_id":          self.org_id,
            "tenant_id":       self.tenant_id,
            "name":            self.name,
            "interview_type":  self.interview_type,
            "description":     self.description,
            "status":          self.status,
            "current_version": self.current_version,
            "created_by":      self.created_by,
            "created_at":      self.created_at,
        }

    @classmethod
    def from_row(cls, row) -> "InterviewTemplate":
        return cls(
            template_id     = row["template_id"],
            org_id          = row["org_id"],
            tenant_id       = row["tenant_id"],
            name            = row["name"],
            interview_type  = row["interview_type"],
            description     = row["description"],
            status          = row["status"],
            current_version = row["current_version"],
            created_by      = row["created_by"],
            created_at      = row["created_at"],
        )


class TemplateService:
    def create(
        self,
        tenant_id:  str,
        org_id:     str,
        name:       str,
        created_by: str,
        config:     Optional[TemplateConfig] = None,
        description: str = "",
        interview_type: str = "behavioral",
    ) -> InterviewTemplate:
        template_id = f"tpl_{uuid.uuid4().hex[:12]}"
        version_id  = f"tv_{uuid.uuid4().hex[:12]}"
        created_at  = time.time()
        cfg         = config or TemplateConfig(interview_type=interview_type)

        con = get_enterprise_conn()
        try:
            con.execute(
                """
                INSERT INTO interview_templates
                  (template_id, org_id, tenant_id, name, interview_type, description,
                   status, current_version, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'active', 1, ?, ?)
                """,
                (template_id, org_id, tenant_id, name, interview_type,
                 description, created_by, created_at),
            )
            con.execute(
                """
                INSERT INTO template_versions
                  (version_id, template_id, version_num, config_json, created_by, created_at)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (version_id, template_id, json.dumps(cfg.to_dict()), created_by, created_at),
            )
            con.commit()
            logger.info("Template created: %s (%s) by %s", name, template_id, created_by)
            return InterviewTemplate(
                template_id=template_id, org_id=org_id, tenant_id=tenant_id, name=name,
                interview_type=interview_type, description=description, status="active",
                current_version=1, created_by=created_by, created_at=created_at,
            )
        finally:
            con.close()

    def publish_new_version(
        self, tenant_id: str, template_id: str, config: TemplateConfig, updated_by: str
    ) -> TemplateVersion:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT current_version FROM interview_templates WHERE template_id = ? AND tenant_id = ?",
                (template_id, tenant_id),
            ).fetchone()
            if row is None:
                raise LookupError(f"Template {template_id} not found")

            new_ver    = row["current_version"] + 1
            version_id = f"tv_{uuid.uuid4().hex[:12]}"
            created_at = time.time()

            con.execute(
                "INSERT INTO template_versions (version_id, template_id, version_num, config_json, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (version_id, template_id, new_ver, json.dumps(config.to_dict()), updated_by, created_at),
            )
            con.execute(
                "UPDATE interview_templates SET current_version = ? WHERE template_id = ?",
                (new_ver, template_id),
            )
            con.commit()
            logger.info("Template %s → v%d by %s", template_id, new_ver, updated_by)
            return TemplateVersion(
                version_id=version_id, template_id=template_id, version_num=new_ver,
                config=config, created_by=updated_by, created_at=created_at,
            )
        finally:
            con.close()

    def list_for_org(self, tenant_id: str, org_id: str) -> list:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT * FROM interview_templates WHERE org_id = ? AND tenant_id = ? AND status = 'active' ORDER BY name",
                (org_id, tenant_id),
            ).fetchall()
            return [InterviewTemplate.from_row(r) for r in rows]
        finally:
            con.close()

    def get_version(self, template_id: str, version_num: int) -> Optional[TemplateVersion]:
        con = get_enterprise_conn()
        try:
            row = con.execute(
                "SELECT * FROM template_versions WHERE template_id = ? AND version_num = ?",
                (template_id, version_num),
            ).fetchone()
            if row is None:
                return None
            return TemplateVersion(
                version_id=row["version_id"], template_id=row["template_id"],
                version_num=row["version_num"],
                config=TemplateConfig.from_dict(json.loads(row["config_json"])),
                created_by=row["created_by"], created_at=row["created_at"],
            )
        finally:
            con.close()

    def list_versions(self, template_id: str) -> list:
        con = get_enterprise_conn()
        try:
            rows = con.execute(
                "SELECT version_id, template_id, version_num, created_by, created_at FROM template_versions WHERE template_id = ? ORDER BY version_num DESC",
                (template_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


template_service = TemplateService()
