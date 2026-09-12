import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright

from .llm import LLMClient
from .page import build_prompt, extract_controls
from artifact.models import Capability, InputParameter, KnownOutcome, OutputParameter, Step, TargetRef
from artifact.store import save_artifact
from guardrails.policy import default_policy
from human_operator.handoff import check_handoff_or_pause, ControlState, Intervention, StateMachine

EVIDENCE_DIR = Path("evidence")
EVIDENCE_DIR.mkdir(exist_ok=True)


class DiscoveryAgent:
    def __init__(
        self,
        goal: str,
        inputs: Optional[Dict[str, str]] = None,
        outputs: Optional[Dict[str, str]] = None,
        known_outcomes: Optional[List[KnownOutcome]] = None,
        max_steps: int = 25,
        headless: bool = True,
        run_id: Optional[str] = None,
        capability_id: str = "lookup-member-balance",
    ):
        self.capability_id = capability_id
        self.goal = goal
        self.inputs = inputs or {}
        self.outputs = outputs or {}
        self.known_outcomes = known_outcomes or []
        self.max_steps = max_steps
        self.headless = headless
        self.llm = LLMClient()
        self.policy = default_policy()
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.log_path = EVIDENCE_DIR / f"discovery_log_{self.run_id}.jsonl"
        self.screenshot_dir = EVIDENCE_DIR / f"discovery_screenshots_{self.run_id}"
        self.screenshot_dir.mkdir(exist_ok=True)
        self.steps: List[Step] = []
        self.state_machine = StateMachine(self.run_id)

    def _log(self, record: Dict[str, Any]) -> None:
        record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _screenshot(self, page, name: str) -> str:
        path = self.screenshot_dir / f"{name}.png"
        page.screenshot(path=str(path))
        return str(path)

    def _page_snapshot(self, page) -> Dict[str, Any]:
        return {
            "url": page.url,
            "title": page.title(),
            "body_preview": page.locator("body").inner_text()[:500],
        }

    def _locate(self, page, target: TargetRef):
        if target.kind == "name" and target.value:
            return page.locator(f"[name='{target.value}']")
        if target.kind == "text" and target.value:
            if target.tag == "a":
                return page.get_by_role("link", name=target.value)
            if target.tag == "input" and target.type == "submit":
                return page.locator(f"input[type='submit'][value='{target.value}']")
            return page.get_by_role("button", name=target.value)
        raise ValueError(f"Cannot locate target: {target}")

    def _format_goal(self, goal: str) -> str:
        for key, val in self.inputs.items():
            goal = goal.replace(f"{{{key}}}", str(val))
        return goal

    def _handoff(self, page, step_num: int, reason: str):
        """Pause for human intervention in the same live browser session."""
        screenshot = self._screenshot(page, f"handoff_step_{step_num:02d}")
        pre = self._page_snapshot(page)

        intervention = Intervention(
            intervention_id=f"{self.run_id}-{step_num:02d}",
            capability_id=self.capability_id,
            run_id=self.run_id,
            step_id=step_num,
            goal=self._format_goal(self.goal),
            reason=reason,
            current_url=page.url,
            screenshot_path=str(screenshot),
            what_to_do="Please take control of the visible browser, resolve the issue, then create evidence/interventions/resume_{{run_id}}.json with either {\"continue\": true} or {\"done\": true, \"output\": {...}}.",
        )
        path = self.state_machine.request_intervention(intervention)

        # Wait for the resume signal. Do NOT close the browser.
        resume_path = self.state_machine.wait_for_resume(timeout=120.0)
        with open(resume_path, "r", encoding="utf-8") as f:
            signal = json.load(f)

        post = self._page_snapshot(page)
        human_actions = {
            "pre_handoff": pre,
            "post_handoff": post,
            "url_changed": pre["url"] != post["url"],
            "title_changed": pre["title"] != post["title"],
            "body_changed": pre["body_preview"] != post["body_preview"],
        }
        self._log({"type": "human_handoff", "intervention": str(path), "human_actions": human_actions})

        if signal.get("done"):
            step = Step(
                step_number=step_num,
                action="done",
                target=TargetRef(kind="unknown", value=""),
                value=None,
                expected_url=page.url,
                checkpoint=signal.get("checkpoint", ""),
                output=signal.get("output"),
                notes="Human completed the task via handoff",
            )
            self.steps.append(step)
            self._screenshot(page, f"step_{step_num:02d}_post")
            self._log({"type": "success", "data": step.output, "human_completed": True})
            return step, True  # step, should_break

        # Otherwise continue the discovery loop.
        self.state_machine.complete()
        return None, False

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

                raw_target = raw_action.get("target") or {}
                target = TargetRef(
                    kind="name" if raw_target.get("name") else ("text" if raw_target.get("text") else "unknown"),
                    value=raw_target.get("name") or raw_target.get("text") or "",
                    tag=raw_target.get("tag"),
                    type=raw_target.get("type"),
                )
                step = Step(
                    step_number=step_num,
                    action=raw_action.get("action", ""),
                    target=target,
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
                    reason = raw_action.get("reason", "Agent requested human intervention")
                    handoff_step, should_break = self._handoff(page, step_num, reason)
                    if should_break:
                        break
                    continue

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
                # Max steps without finishing: escalate to human in the same session.
                handoff_step, should_break = self._handoff(page, self.max_steps, "Reached max steps without reaching the goal")
                if not should_break:
                    raise RuntimeError(f"Did not reach a 'done' or 'escalate' within {self.max_steps} steps")

            browser.close()

        capability = Capability(
            id=self.capability_id,
            name=self.capability_id,
            goal=self.goal,
            entry_url="http://localhost:5000",
            inputs=[
                InputParameter(name=k, description="runtime input", type="string")
                for k, v in self.inputs.items()
            ],
            outputs=[
                OutputParameter(name=k, description=v, type="string")
                for k, v in self.outputs.items()
            ],
            known_outcomes=self.known_outcomes,
            steps=self.steps,
            success_condition="Reached the goal and extracted declared outputs",
        )

        # Parameterize: replace concrete input values with placeholders so one artifact
        # can be replayed with different parameter values.
        for step in capability.steps:
            if step.value:
                for k, v in self.inputs.items():
                    if v in step.value:
                        step.value = step.value.replace(v, f"{{{k}}}")

        save_artifact(capability, EVIDENCE_DIR / f"artifact_{capability.id}.json")
        return capability

    def _execute_action(self, page, raw_action: Dict[str, Any]) -> None:
        action = raw_action["action"]
        raw_target = raw_action.get("target") or {}
        value = raw_action.get("value")
        target = TargetRef(
            kind="name" if raw_target.get("name") else ("text" if raw_target.get("text") else "unknown"),
            value=raw_target.get("name") or raw_target.get("text") or "",
            tag=raw_target.get("tag"),
            type=raw_target.get("type"),
        )

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
            if target.kind == "name" and target.value:
                page.locator(f"[name='{target.value}']").click()
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
