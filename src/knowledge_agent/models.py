"""Model adapters. The offline rule model explicitly does NOT prove LLM reasoning."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .tools import normalize


class ModelError(Exception):
    pass


def load_env(path):
    values = {}
    if path and Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return {**values, **os.environ}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Prevent bearer credentials being forwarded to a redirected endpoint.
        return None


class ChatModel:
    mode = "live"

    def __init__(self, config):
        self.name = config.get("QA_MODEL", "glm-4.5-flash")
        self.key = config.get("QA_API_KEY", "")
        self.base_url = config.get("QA_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("QA_BASE_URL必须是无凭据、无查询参数的HTTPS地址")
        if not self.key or self.key == "your-api-key":
            raise ValueError("live模式需要QA_API_KEY；请配置环境变量或.env，不会自动切换Mock")
        self.timeout = float(config.get("QA_TIMEOUT", "60"))
        if not 1 <= self.timeout <= 120:
            raise ValueError("QA_TIMEOUT必须在1到120秒之间")
        self.thinking = config.get("QA_THINKING", "disabled")
        if self.thinking not in {"disabled", "enabled", "omit"}:
            raise ValueError("QA_THINKING必须是disabled/enabled/omit")
        self.opener = urllib.request.build_opener(NoRedirect())
        self.last_metadata = {}

    def decide(self, messages):
        payload = {"model": self.name, "messages": messages, "temperature": 0,
                   "max_tokens": 2400, "stream": False, "response_format": {"type": "json_object"}}
        if self.thinking != "omit":
            payload["thinking"] = {"type": self.thinking}
        req = urllib.request.Request(self.base_url + "/chat/completions",
              data=json.dumps(payload, ensure_ascii=False).encode(),
              headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        self.last_metadata = {"requested_model": self.name}
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ModelError("模型响应超过大小限制")
            body = json.loads(raw)
            choice = body["choices"][0]
            if not isinstance(choice, dict):
                raise ModelError("模型服务响应结构异常：choice必须为对象")
            self.last_metadata.update({"model": body.get("model", self.name),
                                       "request_id": body.get("id"), "usage": body.get("usage", {}),
                                       "finish_reason": choice.get("finish_reason")})
            if choice.get("finish_reason") == "length":
                raise ValueError("模型输出被截断，需要缩短输出")
            content = choice["message"]["content"]
            # reasoning_content is intentionally neither read nor saved.
            return json.loads(content)
        except urllib.error.HTTPError as exc:
            # Do not echo raw provider bodies, request headers, or keys.
            raise ModelError(f"模型HTTP错误 {exc.code}；请检查服务、配额或配置") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ModelError("模型网络错误或超时") from None
        except (KeyError, IndexError, TypeError):
            raise ModelError("模型服务响应结构异常") from None


def action(name, args, reason):
    return {"action": name, "arguments": args, "reason": reason}


class MockModel:
    """Deterministic, domain-limited flow simulator; never labelled real model evidence."""
    mode, name = "mock", "offline-rule-simulator-v1"
    last_metadata = {"simulation": True}

    def decide(self, messages):
        initial = json.loads(messages[1]["content"])
        question = normalize(initial["question"])
        if not any(t in question for t in ("报销", "请假", "设备", "导出")) and initial["history"]:
            question = normalize(" ".join(x["content"] for x in initial["history"]) + " " + question)
        topic = next((t for t in ("报销", "请假", "设备", "导出") if t in question), None)
        observations = []
        for msg in messages[2:]:
            if msg["role"] == "user":
                value = json.loads(msg["content"])
                if "observation" in value:
                    observations.append(value["observation"])
        if observations and not observations[-1]["result"].get("ok"):
            failed = [o for o in observations if not o["result"].get("ok")]
            if len(failed) < 2:
                last = observations[-1]
                return action(last["action"], last["arguments"], "离线规则模拟：观察到工具错误，重试一次。")
            return self.finish("tool_error", "工具持续不可用，无法完成查证。", [], ["工具调用失败"], "")
        searches = [o for o in observations if o["action"] == "search_documents"]
        if not searches:
            if not topic and any(x in question for x in ("那", "这个", "它")):
                return self.finish("needs_clarification", "请明确要查询的制度。", [], ["问题缺少主题"], "你指哪项制度？")
            return action("search_documents", {"query": topic or question, "limit": 8}, "离线规则模拟：先检索问题主题。")
        hits = {}
        for search in searches:
            for hit in search["result"].get("hits", []):
                if not topic or hit["topic"] == topic:
                    hits[(hit["doc_id"], hit["section_id"])] = hit
        reads = {(o["result"]["document"]["doc_id"], o["result"]["document"]["section_id"]): o["result"]["document"]
                 for o in observations if o["action"] == "read_document" and o["result"].get("ok")}
        for key in hits:
            if key not in reads:
                return action("read_document", {"doc_id": key[0], "section_id": key[1]},
                              "离线规则模拟：读取尚未读取的同主题片段。")
        records = [r for key, r in reads.items() if key in hits]
        if not records:
            if len(searches) < 2:
                return action("search_documents", {"query": initial["question"] + " 制度", "limit": 8},
                              "离线规则模拟：没有命中，补充检索。")
            return self.finish("insufficient_evidence", "当前资料没有足够依据回答此问题。", [], ["缺少相关制度或产品资料"], "")
        numbers = {m for r in records for m in re.findall(r"(\d+)天", r["text"])}
        conflict = topic == "报销" and len(numbers) > 1
        if conflict and len(searches) < 2:
            return action("search_documents", {"query": "报销 适用范围 优先级 替代关系", "limit": 8},
                          "离线规则模拟：发现不同期限，补检索适用范围与优先级。")
        citations = [{k: r[k] for k in ("doc_id", "version_date", "section_id")} | {"quote": r["text"]} for r in records]
        text = "\n".join(f"{r['text']}[{r['doc_id']}:{r['section_id']}]" for r in records)
        if conflict:
            return self.finish("needs_clarification", "资料存在冲突，无法确定统一期限：\n" + text, citations,
                               ["缺少明确适用范围或制度替代关系"], "请确认适用制度或补充说明优先级的文件。")
        return self.finish("completed", text, citations, [], "")

    @staticmethod
    def finish(status, answer, citations, gaps, follow_up):
        return action("finish", {"status": status, "answer": answer, "citations": citations,
                                 "gaps": gaps, "follow_up_question": follow_up}, "离线规则模拟：按观察结果结束。")
