from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InputParameter(BaseModel):
    name: str
    description: str
    type: str = "string"
    required: bool = True


class OutputParameter(BaseModel):
    name: str
    description: str
    type: str = "string"


class Step(BaseModel):
    step_number: int
    action: str  # click, fill, submit, navigate, wait, done, escalate
    target: Dict[str, Any] = Field(default_factory=dict)
    value: Optional[str] = None
    expected_url: Optional[str] = None
    checkpoint: Optional[str] = None  # text expected on the page after the step
    output: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class Capability(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    goal: str
    entry_url: str
    inputs: List[InputParameter] = Field(default_factory=list)
    outputs: List[OutputParameter] = Field(default_factory=list)
    steps: List[Step] = Field(default_factory=list)
    success_condition: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def get_input(self, name: str) -> Optional[InputParameter]:
        return next((i for i in self.inputs if i.name == name), None)
