"""Read-only local tools. Search summaries are discovery hints, not evidence."""
import copy
import hashlib
import json
import re
from datetime import date
from pathlib import Path

ALIASES = {"报账": "报销", "发票": "报销", "报费用": "报销", "最晚": "期限",
           "多久": "期限", "多少天": "期限", "休假": "请假", "电脑": "设备",
           "笔记本": "设备", "导出": "导出", "报批": "审批"}


def normalize(text):
    for old, new in ALIASES.items():
        text = text.replace(old, new)
    return text.lower()


def terms(text):
    text = normalize(text)
    result = set(re.findall(r"[a-z0-9_-]+", text))
    for part in re.findall(r"[\u4e00-\u9fff]+", text):
        result.update(part[i:i+2] for i in range(len(part)-1))
    return result - {"员工", "制度", "规定", "申请", "多少", "怎么", "如何", "公司", "说明", "支持"}


class KnowledgeBase:
    def __init__(self, documents):
        if not isinstance(documents, list) or not documents:
            raise ValueError("知识库必须是非空文档数组")
        self.documents = copy.deepcopy(documents)
        self.index = {}
        seen = set()
        for doc in self.documents:
            if not isinstance(doc, dict):
                raise ValueError("每份文档必须为JSON对象")
            for key in ("doc_id", "version_date", "title", "topic"):
                if not isinstance(doc.get(key), str) or not doc[key].strip():
                    raise ValueError("文档元数据缺失: " + key)
            date.fromisoformat(doc["version_date"])
            if doc["doc_id"] in seen:
                raise ValueError("重复文档 ID")
            seen.add(doc["doc_id"])
            if not isinstance(doc.get("sections"), list) or not doc["sections"]:
                raise ValueError("文档缺少片段")
            for section in doc["sections"]:
                if not isinstance(section, dict):
                    raise ValueError("每个片段必须为JSON对象")
                if not all(isinstance(section.get(k), str) and section[k].strip()
                           for k in ("section_id", "text")):
                    raise ValueError("无效片段")
                key = (doc["doc_id"], section["section_id"])
                if key in self.index:
                    raise ValueError("重复片段 ID")
                self.index[key] = {k: doc.get(k) for k in
                                   ("doc_id", "version_date", "title", "topic", "scope", "supersedes")}
                self.index[key].update(section)
        self.fingerprint = hashlib.sha256(json.dumps(self.documents, ensure_ascii=False,
                                                    sort_keys=True).encode()).hexdigest()

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    def search(self, query, limit=8):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 300:
            raise ValueError("query 必须为1至300字符")
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError("limit 必须为1至12的整数")
        query_terms = terms(query)
        explicit_topics = {r["topic"] for r in self.index.values() if r["topic"] in normalize(query)}
        ranked = []
        for record in self.index.values():
            text = record["title"] + " " + record["text"]
            # A cross-topic precedence notice can still mention the queried policy.
            if explicit_topics and not any(t in normalize(text + record["topic"]) for t in explicit_topics):
                continue
            overlap = query_terms & terms(text)
            topic_hit = record["topic"] in normalize(query)
            score = len(overlap) + (8 if topic_hit else 0)
            # Ignore isolated generic bigrams; exact topic and IDs remain discoverable.
            if topic_hit or len(overlap) >= 2 or record["doc_id"].lower() in query.lower():
                ranked.append((score, record))
        ranked.sort(key=lambda item: (-item[0], item[1]["doc_id"], item[1]["section_id"]))
        hits = [{**{k: r[k] for k in ("doc_id", "version_date", "title", "section_id", "topic")},
                 "score": score, "preview": r["text"][:100]} for score, r in ranked[:limit]]
        return {"ok": True, "hits": hits, "total": len(ranked), "truncated": len(ranked) > limit,
                "notice": "摘要仅用于发现资料，回答前必须读取原文；排序不代表制度优先级。"}

    def read(self, doc_id, section_id):
        if not isinstance(doc_id, str) or not isinstance(section_id, str):
            raise ValueError("文档和片段ID必须为字符串")
        record = self.index.get((doc_id, section_id))
        if record is None:
            return {"ok": False, "error": {"code": "NOT_FOUND", "retryable": False,
                                           "message": "指定文档或片段不存在"}}
        return {"ok": True, "document": copy.deepcopy(record)}


class Tools:
    def __init__(self, kb, failure="none"):
        if failure not in {"none", "search_once", "search_always", "read_once", "read_always"}:
            raise ValueError("未知故障注入模式")
        self.kb, self.failure, self.failed = kb, failure, False

    def execute(self, action, arguments):
        if action not in {"search_documents", "read_document"}:
            return {"ok": False, "error": {"code": "UNKNOWN_TOOL", "message": "工具不在白名单中"}}
        short = "search" if action == "search_documents" else "read"
        if self.failure.startswith(short) and (self.failure.endswith("always") or not self.failed):
            self.failed = True
            return {"ok": False, "error": {"code": "TEMPORARY_UNAVAILABLE", "retryable": True,
                    "message": "合成故障：工具暂不可用。这不是无检索结果。"}}
        try:
            result = self.kb.search(**arguments) if short == "search" else self.kb.read(**arguments)
            return result
        except (ValueError, TypeError):
            return {"ok": False, "error": {"code": "INVALID_ARGUMENTS", "retryable": False,
                                           "message": "参数不符合工具协议"}}
