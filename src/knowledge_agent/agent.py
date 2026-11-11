"""Bounded model -> action -> observation loop, with an auditable public trace."""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

from .models import ModelError
from .prompts import SYSTEM_PROMPT
from .validation import validate_action, validate_answer


def now():
    return datetime.now(timezone.utc).isoformat()


def summary(result):
    if not result.get("ok"):
        return result.get("error", {})
    if "hits" in result:
        return {"hits": [h["doc_id"] + ":" + h["section_id"] for h in result["hits"]],
                "total": result["total"], "truncated": result["truncated"]}
    doc = result["document"]
    return {"doc_id": doc["doc_id"], "section_id": doc["section_id"], "text": doc["text"][:160]}


class Agent:
    def __init__(self, model, tools, max_steps=10, max_tools=8):
        if type(max_steps) is not int or not 1 <= max_steps <= 30:
            raise ValueError("max_steps必须为1至30整数")
        if type(max_tools) is not int or not 1 <= max_tools <= 25:
            raise ValueError("max_tools必须为1至25整数")
        self.model, self.tools, self.max_steps, self.max_tools = model, tools, max_steps, max_tools

    def run(self, question, history=None):
        history = history or []
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
            raise ValueError("问题必须为1至2000字符")
        if not isinstance(history, list) or len(history) > 12:
            raise ValueError("history必须为最多12条消息的数组")
        for item in history:
            if not isinstance(item, dict) or set(item) != {"role", "content"} or item["role"] not in {"user", "assistant"}:
                raise ValueError("历史消息必须包含user/assistant角色和content")
            if not isinstance(item["content"], str) or len(item["content"]) > 2000:
                raise ValueError("历史消息最多2000字符")
        started = time.monotonic()
        initial = {"question": question, "history": history}
        report = {"run_id": str(uuid.uuid4()), "started_at": now(), "mode": self.model.mode,
                  "model": self.model.name, "input": initial, "knowledge_sha256": self.tools.kb.fingerprint,
                  "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                  "limits": {"max_steps": self.max_steps, "max_tools": self.max_tools},
                  "failure_injection": self.tools.failure, "trace": []}
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(initial, ensure_ascii=False)}]
        evidence, observations, count = {}, [], 0
        final = None
        for step in range(1, self.max_steps + 1):
            event = {"step": step, "timestamp": now()}
            report["trace"].append(event)
            try:
                decision = self.model.decide(messages)
                event["model_metadata"] = dict(self.model.last_metadata)
                validate_action(decision)
                event["decision"] = decision
                messages.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
                name, args = decision["action"], decision["arguments"]
                if name == "finish":
                    validate_answer(args, evidence, observations)
                    final = args
                    event["outcome"] = "accepted"
                    break
                if count >= self.max_tools:
                    final = self.unfinished("max_steps_exceeded", "工具调用次数已达到上限，任务未完成。")
                    event["outcome"] = "tool_budget_exhausted"
                    break
                count += 1
                result = self.tools.execute(name, args)
                observation = {"action": name, "arguments": args, "result": result}
                observations.append(observation)
                event["observation"] = result
                event["return_summary"] = summary(result)
                if name == "read_document" and result.get("ok"):
                    doc = result["document"]
                    evidence[(doc["doc_id"], doc["section_id"])] = doc
                messages.append({"role": "user", "content": json.dumps({"observation": observation,
                    "remaining_model_steps": self.max_steps - step, "remaining_tool_calls": self.max_tools - count}, ensure_ascii=False)})
            except ValueError as exc:
                # Schema, JSON, and citation repair is itself budgeted and model-driven.
                event["model_metadata"] = dict(self.model.last_metadata)
                event["validation_error"] = str(exc)[:400]
                messages.append({"role": "user", "content": json.dumps({"validation_error": str(exc)[:400],
                              "instruction": "请修正输出或继续获取证据。", "remaining_model_steps": self.max_steps-step}, ensure_ascii=False)})
            except ModelError as exc:
                event["model_metadata"] = dict(self.model.last_metadata)
                event["model_error"] = str(exc)
                final = self.unfinished("model_error", str(exc))
                break
        if final is None:
            final = self.unfinished("max_steps_exceeded", "模型决策轮数已达到上限，任务未完成。")
        for current, following in zip(report["trace"], report["trace"][1:]):
            current["next_action"] = following.get("decision", {}).get("action", "model_or_validation_error")
        if report["trace"]:
            report["trace"][-1]["next_action"] = "end"
        report.update({"result": final, "tool_calls": count, "model_calls": len(report["trace"]),
                       "finished_at": now(), "elapsed_seconds": round(time.monotonic()-started, 3)})
        return report

    @staticmethod
    def unfinished(status, reason):
        return {"status": status, "answer": reason, "citations": [], "gaps": [reason], "follow_up_question": ""}
