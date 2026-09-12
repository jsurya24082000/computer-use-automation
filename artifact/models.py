from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApprovalState:
    DRAFT = "draft"
    APPROVED = "approved"


class TargetRef(BaseModel):
    """A lightweight, surface-agnostic locator reference."""

    kind: str  # e.g., name, text, aria_label, role, body_contains, url_contains
    value: str
    tag: Optional[str] = None
    type: Optional[str] = None


class InputParameter(BaseModel):
    name: str
    description: str
    type: str = "string"
    required: bool = True


class OutputParameter(BaseModel):
    name: str
    description: str
    type: str = "string"


class KnownOutcome(BaseModel):
    """A non-failing business result that can terminate a replay."""

    name: str
    detect: TargetRef  # how the replay recognises this outcome
    message: str
    status: str = "business_outcome"


class Stability(BaseModel):
    """Track replay success over consecutive runs."""

    consecutive_successes: int = 0
    total_replays: int = 0
    successful_replays: int = 0
    last_runs: List[Dict[str, Any]] = Field(default_factory=list)


class TenantOverride(BaseModel):
    """Per-tenant patch for a single step."""

    tenant_id: str
    step_number: int
    target: TargetRef
    notes: Optional[str] = None


class Step(BaseModel):
    step_number: int
    action: str
    target: TargetRef = Field(default_factory=TargetRef)
    value: Optional[str] = None
    expected_url: Optional[str] = None
    checkpoint: Optional[str] = None  # text expected on the page after the step
    output: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    risk: Optional[str] = None  # "risky" | "irreversible"
    risk_reason: Optional[str] = None


class Capability(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    goal: str
    entry_url: str
    inputs: List[InputParameter] = Field(default_factory=list)
    outputs: List[OutputParameter] = Field(default_factory=list)
    known_outcomes: List[KnownOutcome] = Field(default_factory=list)
    steps: List[Step] = Field(default_factory=list)
    success_condition: str
    stability: Stability = Field(default_factory=Stability)
    approval_state: str = ApprovalState.DRAFT
    tenant_overrides: List[TenantOverride] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def get_input(self, name: str) -> Optional[InputParameter]:
        return next((i for i in self.inputs if i.name == name), None)

    def get_step(self, step_number: int) -> Optional[Step]:
        return next((s for s in self.steps if s.step_number == step_number), None)

    def get_tenant_override(self, tenant_id: str, step_number: int) -> Optional[TenantOverride]:
        return next(
            (o for o in self.tenant_overrides if o.tenant_id == tenant_id and o.step_number == step_number),
            None,
        )
