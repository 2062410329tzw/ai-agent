"""Mechanical grounding guards; semantic entailment still needs evaluation."""
import re

STATUSES = {"completed", "needs_clarification", "insufficient_evidence", "tool_error"}


def validate_action(action):
    if not isinstance(action, dict) or set(action) != {"action", "arguments", "reason"}:
        raise ValueError("动作必须包含且仅包含action、arguments、reason")
    if not isinstance(action["action"], str) or action["action"] not in {"search_documents", "read_document", "finish"}:
        raise ValueError("未知动作")
    if not isinstance(action["arguments"], dict):
        raise ValueError("arguments必须为对象")
    if not isinstance(action["reason"], str) or not 1 <= len(action["reason"].strip()) <= 400:
        raise ValueError("reason必须为1至400字符的简短行动依据")


def validate_answer(answer, read_evidence, observations):
    fields = {"status", "answer", "citations", "gaps", "follow_up_question"}
    if not isinstance(answer, dict) or set(answer) != fields:
        raise ValueError("结束结果字段不符合协议")
    if not isinstance(answer["status"], str) or answer["status"] not in STATUSES:
        raise ValueError("未知任务状态")
    if not isinstance(answer["answer"], str) or not answer["answer"].strip():
        raise ValueError("回答不能为空")
    if not isinstance(answer["follow_up_question"], str):
        raise ValueError("追问必须为字符串")
    if not isinstance(answer["gaps"], list) or any(not isinstance(x, str) or not x.strip() for x in answer["gaps"]):
        raise ValueError("gaps必须是非空字符串列表，或空列表")
    if not isinstance(answer["citations"], list):
        raise ValueError("citations必须为列表")
    seen = set()
    for cite in answer["citations"]:
        if not isinstance(cite, dict) or set(cite) != {"doc_id", "section_id", "version_date", "quote"}:
            raise ValueError("引用字段不符合协议")
        if any(not isinstance(x, str) or not x.strip() for x in cite.values()):
            raise ValueError("引用字段不能为空")
        key = (cite["doc_id"], cite["section_id"])
        evidence = read_evidence.get(key)
        if evidence is None or evidence["version_date"] != cite["version_date"]:
            raise ValueError("引用未读取的片段或版本不匹配")
        if cite["quote"] not in evidence["text"]:
            raise ValueError("引用不是原文连续片段")
        if key in seen:
            raise ValueError("重复引用")
        seen.add(key)
    inline = set(re.findall(r"\[([A-Za-z0-9_-]+):([A-Za-z0-9_-]+)\]", answer["answer"]))
    if inline != seen:
        required = " ".join(f"[{doc}:{section}]" for doc, section in sorted(seen))
        raise ValueError("正文引用与引用清单不一致。请在answer对应事实句末添加这些标记：" + required)
    if answer["status"] == "completed" and (not seen or answer["gaps"] or answer["follow_up_question"]):
        raise ValueError("成功答案需要引用且不能同时声称仍有待澄清缺口")
    if answer["status"] != "completed" and not answer["gaps"]:
        raise ValueError("未完成状态必须说明资料或执行缺口")
    if answer["status"] == "needs_clarification" and not answer["follow_up_question"].strip():
        raise ValueError("需澄清状态必须包含追问")
    searches = [x for x in observations if x["action"] == "search_documents"]
    if answer["status"] == "insufficient_evidence" and not any(x["result"].get("ok") for x in searches):
        raise ValueError("没有成功检索，不能把工具故障说成资料不足")
    if answer["status"] == "tool_error" and not any(not x["result"].get("ok") for x in observations):
        raise ValueError("没有工具失败记录")
