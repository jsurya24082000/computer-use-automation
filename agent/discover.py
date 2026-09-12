import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.sync_api import sync_playwright

from .llm import LLMClient
from .page import build_prompt, extract_controls
from artifact.models import Capability, InputParameter, OutputParameter, Step
from artifact.store import save_artifact
from guardrails.policy import default_policy
from human_operator.handoff import check_handoff_or_pause

EVIDENCE_DIR = Path("evidence")
EVIDENCE_DIR.mkdir(exist_ok=True)


class DiscoveryAgent:
    def __init__(
        self,
        goal: str,
        inputs: Optional[Dict[str, str]] = None,
        outputs: Optional[Dict[str, str]] = None,
        max_steps: int = 25,
        headless: bool = True,
    ):
        self.goal = goal
        self.inputs = inputs or {}
        self.outputs = outputs or {}
        self.max_steps = max_steps
        self.headless = headless
        self.llm = LLMClient()
        self.policy = default_policy()
        self.run_id = uuid.uuid4().hex[:8]
        self.log_path = EVIDENCE_DIR / f"discovery_log_{self.run_id}.jsonl"
        self.screenshot_dir = EVIDENCE_DIR / f"discovery_screenshots_{self.run_id}"
        self.screenshot_dir.mkdir(exist_ok=True)
        self.steps: List[Step] = []

    def _log(self, record: Dict[str, Any]) -> None:
        record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _screenshot(self, page, name: str) -> str:
        path = self.screenshot_dir / f"{name}.png"
        page.screenshot(path=str(path))
        return str(path)

    def _locate(self, page, target: Dict[str, Any]):
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

    def _format_goal(self, goal: str) -> str:
        for key, val in self.inputs.items():
            goal = goal.replace(f"{{{key}}}", str(val))
        return goal

    def run(self) -> Capability:
        formatted_goal = self._format_goal(self.goal)
        previous_actions: List[str] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto("http://localhost:5000")

            for step_num in range(1, self.max_steps + 1):
                check_handoff_or_pause()

                url = page.url
                title = page.title()
                body_text = page.locator("body").inner_text()

                # Business outcome short-circuit: "Member not found" is a legitimate answer.
                if "Member not found" in body_text:
                    step = Step(
                        step_number=step_num,
                        action="done",
                        target={},
                        value=None,
                        expected_url=url,
                        checkpoint="Member not found",
                        output={"outcome": "business_outcome", "message": "Member not found"},
                        notes="Search returned a known business outcome",
                    )
                    self.steps.append(step)
                    self._screenshot(page, f"step_{step_num:02d}_post")
                    self._log({"type": "business_outcome", "data": step.output})
                    break

                controls = extract_controls(page)
                self._screenshot(page, f"step_{step_num:02d}_pre")

                prev_text = "\n".join(f"{i+1}. {a}" for i, a in enumerate(previous_actions[-5:]))
                prompt = build_prompt(formatted_goal, url, title, controls, body_text, prev_text)
                raw_action = self.llm.decide_action(prompt)
                raw_action["step_number"] = step_num
                self._log({"type": "llm_action", "data": self.policy.redact(raw_action)})

                # Validate action against guardrails
                check = self.policy.check_action(
                    raw_action.get("action", ""),
                    raw_action.get("target", {}),
                    raw_action.get("value"),
                )
                if not check["allowed"]:
                    self._log({"type": "policy_block", "data": check})
                    raise RuntimeError(f"Guardrail blocked action: {check['reasons']}")

                step = Step(
                    step_number=step_num,
                    action=raw_action.get("action", ""),
                    target=raw_action.get("target", {}),
                    value=raw_action.get("value"),
                    expected_url=url,
                    notes=raw_action.get("reason", ""),
                )

                if raw_action.get("action") == "done":
                    step.output = self._extract_outputs(page)
                    self.steps.append(step)
                    self._screenshot(page, f"step_{step_num:02d}_post")
                    self._log({"type": "success", "data": step.output})
                    break

                if raw_action.get("action") == "escalate":
                    self._log({"type": "escalation", "reason": raw_action.get("reason")})
                    from human_operator.handoff import request_handoff
                    request_handoff(self.run_id, step_num, raw_action.get("reason", ""), page)
                    raise RuntimeError("Escalated to human operator")

                self._execute_action(page, raw_action)
                self._screenshot(page, f"step_{step_num:02d}_post")

                # Wait for stability
                page.wait_for_timeout(300)

                # Simple checkpoint: if a step has expected_url, ensure still on that domain.
                if raw_action.get("action") == "navigate":
                    step.expected_url = page.url

                previous_actions.append(
                    f"step {step_num}: {raw_action.get('action')} {raw_action.get('target')} "
                    f"value={self.policy.redact(raw_action.get('value'))}"
                )
                self.steps.append(step)

            else:
                raise RuntimeError(f"Did not reach a 'done' or 'escalate' within {self.max_steps} steps")

            browser.close()

        capability = Capability(
            id=f"capability-{self.run_id}",
            name=formatted_goal,
            goal=formatted_goal,
            entry_url="http://localhost:5000",
            inputs=[
                InputParameter(name=k, description=v, type="string")
                for k, v in self.inputs.items()
            ],
            outputs=[
                OutputParameter(name=k, description=v, type="string")
                for k, v in self.outputs.items()
            ],
            steps=self.steps,
            success_condition="Reached the goal and extracted declared outputs",
        )

        save_artifact(capability, EVIDENCE_DIR / f"artifact_{capability.id}.json")
        return capability

    def _execute_action(self, page, raw_action: Dict[str, Any]) -> None:
        action = raw_action["action"]
        target = raw_action.get("target", {})
        value = raw_action.get("value")

        if action == "navigate":
            page.goto(value)
            return

        if action == "wait":
            page.wait_for_timeout(int(value) if value else 1000)
            return

        locator = self._locate(page, target)

        if action == "fill":
            locator.fill(value)
        elif action == "click":
            locator.click()
        elif action == "submit":
            if target.get("name"):
                page.locator(f"[name='{target['name']}']").click()
            else:
                locator.click()

    def _extract_outputs(self, page) -> Dict[str, str]:
        # Try to extract declared outputs from the page text.
        text = page.locator("body").inner_text()
        result: Dict[str, str] = {}

        # Simple extraction patterns.  These are application-specific.
        for name, desc in self.outputs.items():
            if name == "savings_balance":
                m = re.search(r"Current savings balance:\s*\$([0-9,]+\.\d{2})", text)
                if m:
                    result[name] = m.group(1)
            elif name == "new_account_number":
                m = re.search(r"New account number:\s*(\S+)", text)
                if m:
                    result[name] = m.group(1)
            else:
                result[name] = text[:200]

        return result
