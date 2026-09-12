import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class ActionPolicy:
    """Enforce what the automation is permitted to do."""

    def __init__(
        self,
        allowed_domains: Optional[List[str]] = None,
        allowed_actions: Optional[List[str]] = None,
        irreversible_actions: Optional[List[str]] = None,
        redact_keys: Optional[List[str]] = None,
    ):
        self.allowed_domains = set(allowed_domains or ["localhost:5000"])
        self.allowed_actions = set(
            allowed_actions or ["click", "fill", "submit", "navigate", "wait", "done", "escalate"]
        )
        # Actions that should never run unattended unless explicitly approved.
        self.irreversible_actions = set(irreversible_actions or ["submit"])
        self.redact_keys = set(redact_keys or ["password", "token", "ssn"])

    def check_action(self, action: str, target: Dict[str, Any], value: Optional[str]) -> Dict[str, Any]:
        result = {"allowed": True, "risky": False, "reasons": []}

        if action not in self.allowed_actions:
            result["allowed"] = False
            result["reasons"].append(f"Action '{action}' is not in the allowlist.")
            return result

        if action in self.irreversible_actions:
            result["risky"] = True
            result["reasons"].append(f"Action '{action}' is irreversible and requires confirmation.")

        if action == "navigate" and value:
            parsed = urlparse(value)
            domain = parsed.netloc
            if not any(d == domain or (d.startswith("localhost") and not domain) for d in self.allowed_domains):
                result["allowed"] = False
                result["reasons"].append(f"Navigation to '{value}' is outside the allowed domain list.")

        return result

    def _is_sensitive_target(self, target: Any) -> bool:
        if not isinstance(target, dict):
            return False
        name = (target.get("name") or "").lower()
        type_ = (target.get("type") or "").lower()
        return name in self.redact_keys or type_ in self.redact_keys

    def redact(self, obj: Any, parent: Optional[Dict[str, Any]] = None) -> Any:
        if isinstance(obj, dict):
            # If this object has a sensitive target, redact its value.
            if self._is_sensitive_target(obj.get("target")) and "value" in obj:
                obj = {**obj, "value": "<redacted>"}
            return {k: "<redacted>" if k in self.redact_keys else self.redact(v, parent=obj) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.redact(v, parent=parent) for v in obj]
        if isinstance(obj, str):
            # Mask 9-digit SSN patterns.
            masked = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "<redacted>", obj)
            # Mask account numbers like 100-12345-0, keeping only the last digit.
            masked = re.sub(r"\b\d{3}-\d{5}-(\d)\b", r"***-*****-\1", masked)
            return masked
        return obj


def default_policy() -> ActionPolicy:
    return ActionPolicy()
