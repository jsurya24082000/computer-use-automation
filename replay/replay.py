import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright

from artifact.models import ApprovalState, Capability, KnownOutcome, Step, TargetRef
from guardrails.policy import default_policy

EVIDENCE_DIR = Path("evidence")


class LocatorAttempt:
    def __init__(self, strategy: str, selector: str, matched: bool):
        self.strategy = strategy
        self.selector = selector
        self.matched = matched


class ReplayResult:
    def __init__(self):
        self.status = "unknown"
        self.outputs: Dict[str, Any] = {}
        self.step_id: int = -1
        self.error_message: str = ""
        self.expected: str = ""
        self.observed: str = ""
        self.locator_attempts: List[Dict[str, Any]] = []
        self.screenshot_path: str = ""
        self.dom_snapshot_path: str = ""
        self.logs: List[Dict[str, Any]] = []


def _resolve_target(step: Step, capability: Capability, tenant_id: Optional[str]) -> TargetRef:
    override = capability.get_tenant_override(tenant_id or "", step.step_number)
    return override.target if override else step.target


def _substitute_value(value: Optional[str], parameter_values: Dict[str, str]) -> Optional[str]:
    if not value:
        return value
    for k, v in parameter_values.items():
        value = value.replace(f"{{{k}}}", v)
    return value


def _locate_with_attempts(page, target: TargetRef, attempts: List[Dict[str, Any]]):
    """Try multiple locator strategies, logging each. Returns a Playwright Locator."""

    # Strategy 1: name attribute
    if target.kind == "name" and target.value:
        selector = f"[name='{target.value}']"
        loc = page.locator(selector)
        matched = loc.count() > 0
        attempts.append({"strategy": "name", "selector": selector, "matched": matched})
        if matched:
            return loc

    # Strategy 2: exact visible text on button/link
    if target.value:
        selector = f"text={target.value}"
        loc = page.locator(selector)
        matched = loc.count() > 0
        attempts.append({"strategy": "text", "selector": selector, "matched": matched})
        if matched:
            return loc

    # Strategy 3: role+name (button / link)
    if target.value:
        if target.tag == "a":
            selector = f"get_by_role(link, name='{target.value}')"
            loc = page.get_by_role("link", name=target.value)
        else:
            selector = f"get_by_role(button, name='{target.value}')"
            loc = page.get_by_role("button", name=target.value)
        matched = loc.count() > 0
        attempts.append({"strategy": "role", "selector": selector, "matched": matched})
        if matched:
            return loc

    # Strategy 4: input submit by value
    if target.type == "submit" and target.value:
        selector = f"input[type='submit'][value='{target.value}']"
        loc = page.locator(selector)
        matched = loc.count() > 0
        attempts.append({"strategy": "submit_value", "selector": selector, "matched": matched})
        if matched:
            return loc

    # Final fallback: raise with all attempts
    raise RuntimeError(f"No locator matched for target {target.model_dump()}; attempts={attempts}")


def _check_known_outcomes(body: str, url: str, known_outcomes: List[KnownOutcome]) -> Optional[KnownOutcome]:
    for ko in known_outcomes:
        d = ko.detect
        if d.kind == "body_contains" and d.value in body:
            return ko
        if d.kind == "url_contains" and d.value in url:
            return ko
    return None


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
    tenant_id: Optional[str] = None,
    save_to: Optional[Path] = None,
) -> ReplayResult:
    run_id = uuid.uuid4().hex[:8]
    log_path = save_to or (EVIDENCE_DIR / f"replay/replay_log_{run_id}.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_dir = EVIDENCE_DIR / f"replay/replay_screenshots_{run_id}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    dom_dir = EVIDENCE_DIR / f"replay/replay_dom_{run_id}"
    dom_dir.mkdir(parents=True, exist_ok=True)
    policy = default_policy()
    result = ReplayResult()

    def _log(record: Dict[str, Any]) -> None:
        record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        result.logs.append(record)

    def _screenshot(name: str) -> str:
        path = screenshot_dir / f"{name}.png"
        page.screenshot(path=str(path))
        return str(path)

    def _dom_snapshot(name: str) -> str:
        path = dom_dir / f"{name}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(page.content())
        return str(path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(capability.entry_url)

        for step in capability.steps:
            result.step_id = step.step_number
            target = _resolve_target(step, capability, tenant_id)
            value = _substitute_value(step.value, parameter_values)

            # Guardrails before every action.
            check = policy.check_action(step.action, target.model_dump(), value)
            if not check["allowed"]:
                result.status = "failure"
                result.error_message = f"Guardrail blocked: {check['reasons']}"
                result.screenshot_path = _screenshot(f"policy_block_step_{step.step_number}")
                _log({
                    "step": step.step_number,
                    "event": "policy_block",
                    "details": check,
                    "screenshot": result.screenshot_path,
                })
                browser.close()
                return result

            # Risk/irreversible gating: approval required for risky actions on a draft artifact.
            if step.risk in ("irreversible", "risky") and capability.approval_state != ApprovalState.APPROVED:
                result.status = "escalation"
                result.error_message = f"Step {step.step_number} is {step.risk} but artifact is {capability.approval_state}"
                _log({"step": step.step_number, "event": "approval_gate", "risk": step.risk, "approval_state": capability.approval_state})
                browser.close()
                return result

            if step.action == "done":
                observed = page.locator("body").inner_text()
                if step.checkpoint and step.checkpoint not in observed:
                    result.status = "failure"
                    result.error_message = f"Checkpoint not found: {step.checkpoint}"
                    result.expected = step.checkpoint
                    result.observed = observed[:500]
                    result.screenshot_path = _screenshot(f"checkpoint_failed_step_{step.step_number}")
                    result.dom_snapshot_path = _dom_snapshot(f"checkpoint_failed_step_{step.step_number}")
                    _log({
                        "step": step.step_number,
                        "event": "checkpoint_failed",
                        "expected": step.checkpoint,
                        "observed": result.observed,
                        "screenshot": result.screenshot_path,
                        "dom": result.dom_snapshot_path,
                    })
                    browser.close()
                    return result

                result.status = "success"
                result.outputs = _extract_outputs(page, [o.name for o in capability.outputs])
                _log({"step": step.step_number, "event": "success", "outputs": result.outputs})
                browser.close()
                return result

            if step.action == "escalate":
                result.status = "escalation"
                result.error_message = "Replay encountered an escalation step"
                _log({"step": step.step_number, "event": "escalation"})
                browser.close()
                return result

            try:
                result.locator_attempts = []
                if step.action == "navigate":
                    page.goto(value)
                elif step.action == "wait":
                    page.wait_for_timeout(int(value) if value else 1000)
                elif step.action in ("click", "submit"):
                    locator = _locate_with_attempts(page, target, result.locator_attempts)
                    locator.click()
                elif step.action == "fill":
                    locator = _locate_with_attempts(page, target, result.locator_attempts)
                    locator.fill(value)

                page.wait_for_timeout(300)
                _log({"step": step.step_number, "event": "executed", "action": step.action, "locator_report": result.locator_attempts})

                # Known outcomes are checked after every executed step, before any checkpoint.
                body = page.locator("body").inner_text()
                url = page.url
                ko = _check_known_outcomes(body, url, capability.known_outcomes)
                if ko:
                    result.status = "business_outcome"
                    result.outputs = {"known_outcome": ko.name, "message": ko.message}
                    result.step_id = step.step_number
                    _log({"step": step.step_number, "event": "business_outcome", "known_outcome": ko.name, "message": ko.message})
                    browser.close()
                    return result

            except Exception as e:
                result.status = "failure"
                result.error_message = str(e)
                result.screenshot_path = _screenshot(f"error_step_{step.step_number}")
                result.dom_snapshot_path = _dom_snapshot(f"error_step_{step.step_number}")
                result.observed = page.locator("body").inner_text()[:500]
                _log({
                    "step": step.step_number,
                    "event": "error",
                    "message": str(e),
                    "locator_report": result.locator_attempts,
                    "observed": result.observed,
                    "screenshot": result.screenshot_path,
                    "dom": result.dom_snapshot_path,
                })
                browser.close()
                return result

        result.error_message = "Reached end of artifact without a 'done' step"
        result.status = "failure"
        result.screenshot_path = _screenshot("no_done_step")
        result.dom_snapshot_path = _dom_snapshot("no_done_step")
        _log({"event": "error", "message": result.error_message, "screenshot": result.screenshot_path, "dom": result.dom_snapshot_path})
        browser.close()
        return result
