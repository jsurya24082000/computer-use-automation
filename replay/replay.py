import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright

from artifact.models import Capability, Step
from guardrails.policy import default_policy

EVIDENCE_DIR = Path("evidence")


class ReplayResult:
    def __init__(self):
        self.success = False
        self.outcome = "unknown"
        self.outputs: Dict[str, Any] = {}
        self.error_step: int = -1
        self.error_message: str = ""
        self.logs: List[Dict[str, Any]] = []


def _locator(page, target: Dict[str, Any]):
    name = target.get("name")
    text = target.get("text")
    tag = target.get("tag")
    type_ = target.get("type")

    if name:
        return page.locator(f"[name='{name}']")
    if text:
        if tag == "a":
            return page.get_by_role("link", name=text)
        if tag == "input" and type_ == "submit":
            return page.locator(f"input[type='submit'][value='{text}']")
        return page.get_by_role("button", name=text)
    raise ValueError(f"Cannot locate target: {target}")


def _extract_outputs(page, output_names: List[str]) -> Dict[str, str]:
    text = page.locator("body").inner_text()
    result: Dict[str, str] = {}
    for name in output_names:
        if name == "savings_balance":
            m = re.search(r"Current savings balance:\s*\$([0-9,]+\.\d{2})", text)
            if m:
                result[name] = m.group(1)
        elif name == "new_account_number":
            m = re.search(r"New account number:\s*(\S+)", text)
            if m:
                result[name] = m.group(1)
    return result


def replay_capability(
    capability: Capability,
    parameter_values: Dict[str, str],
    headless: bool = True,
) -> ReplayResult:
    run_id = uuid.uuid4().hex[:8]
    log_path = EVIDENCE_DIR / f"replay_log_{run_id}.jsonl"
    screenshot_dir = EVIDENCE_DIR / f"replay_screenshots_{run_id}"
    screenshot_dir.mkdir(exist_ok=True)
    policy = default_policy()
    result = ReplayResult()

    def _log(record: Dict[str, Any]) -> None:
        record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        result.logs.append(record)

    def _screenshot(name: str):
        return  # screenshots captured by caller if needed

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(capability.entry_url)

        for step in capability.steps:
            # Halt if policy says the action is risky and not confirmed.
            check = policy.check_action(step.action, step.target, step.value)
            if not check["allowed"]:
                result.error_step = step.step_number
                result.error_message = f"Guardrail blocked: {check['reasons']}"
                _log({"step": step.step_number, "event": "policy_block", "details": check})
                browser.close()
                return result

            if step.action == "done":
                # Verify checkpoint if present.
                if step.checkpoint and step.checkpoint not in page.locator("body").inner_text():
                    result.error_step = step.step_number
                    result.error_message = f"Checkpoint not found: {step.checkpoint}"
                    _log({"step": step.step_number, "event": "checkpoint_failed"})
                    browser.close()
                    return result

                result.success = True
                if step.output and step.output.get("outcome"):
                    result.outcome = step.output.get("outcome")
                    result.outputs = step.output
                else:
                    result.outcome = "success"
                    result.outputs = _extract_outputs(page, [o.name for o in capability.outputs])
                _log({"step": step.step_number, "event": result.outcome, "outputs": result.outputs})
                browser.close()
                return result

            if step.action == "escalate":
                result.outcome = "escalation"
                result.error_message = "Replay encountered an escalation step"
                _log({"step": step.step_number, "event": "escalation"})
                browser.close()
                return result

            try:
                if step.action == "navigate":
                    page.goto(step.value)
                elif step.action == "wait":
                    page.wait_for_timeout(int(step.value) if step.value else 1000)
                elif step.action in ("click", "submit"):
                    _locator(page, step.target).click()
                elif step.action == "fill":
                    # Substitute parameter placeholders.
                    value = step.value
                    if value:
                        for k, v in parameter_values.items():
                            value = value.replace(f"{{{k}}}", v)
                    _locator(page, step.target).fill(value)

                page.wait_for_timeout(300)

                # Business-outcome checks: "Member not found" is a legitimate result.
                body = page.locator("body").inner_text()
                if "Member not found" in body:
                    result.success = True
                    result.outcome = "business_outcome"
                    result.error_message = "Member not found"
                    _log({"step": step.step_number, "event": "business_outcome", "message": "Member not found"})
                    browser.close()
                    return result

                _log({"step": step.step_number, "event": "executed", "action": step.action})

            except Exception as e:
                result.error_step = step.step_number
                result.error_message = str(e)
                _log({"step": step.step_number, "event": "error", "message": str(e)})
                browser.close()
                return result

        result.error_message = "Reached end of artifact without a 'done' step"
        _log({"event": "error", "message": result.error_message})
        browser.close()
        return result
