"""Small acceptance checks, not a general semantic accuracy benchmark."""
import copy
import json
import platform
from pathlib import Path

from .agent import Agent, now
from .cli import ROOT, save_json
from .tools import KnowledgeBase, Tools
from .validation import validate_answer


def case_documents(case, source):
    docs = [copy.deepcopy(d) for d in source if d["doc_id"] not in case.get("exclude_docs", [])]
    replace = case.get("replace_text")
    if replace:
        for doc in docs:
            if doc["doc_id"] == replace["doc_id"]:
                for section in doc["sections"]:
                    section["text"] = section["text"].replace(replace["old"], replace["new"])
    return docs


def check_case(case, report):
    result, trace = report["result"], report["trace"]
    citations = {c["doc_id"] for c in result["citations"]}
    checks = {"status": result["status"] == case["expected_status"],
              "required_citations": set(case["required_citations"]).issubset(citations),
              "answer_contains": all(s in result["answer"] for s in case.get("answer_contains", [])),
              "answer_excludes": not any(s in result["answer"] for s in case.get("answer_excludes", [])),
              "bounded": report["model_calls"] <= report["limits"]["max_steps"] and report["tool_calls"] <= report["limits"]["max_tools"]}
    observations = [{"action": e["decision"]["action"], "result": e["observation"]}
                    for e in trace if "observation" in e]
    reads = {(o["result"]["document"]["doc_id"], o["result"]["document"]["section_id"]): o["result"]["document"]
             for o in observations if o["action"] == "read_document" and o["result"].get("ok")}
    try:
        if result["status"] not in {"model_error", "max_steps_exceeded"}:
            validate_answer(result, reads, observations)
        checks["citation_integrity"] = True
    except ValueError:
        checks["citation_integrity"] = False
    searches = [o for o in observations if o["action"] == "search_documents"]
    checks["supplementary_search"] = len(searches) >= case.get("min_searches", 0)
    if case.get("requires_failure"):
        failed = [i for i, e in enumerate(trace) if "observation" in e and not e["observation"].get("ok")]
        checks["observed_failure_then_decided"] = bool(failed) and any(
            any("decision" in e for e in trace[i+1:]) for i in failed)
    if case["id"] == "conflict":
        read_positions = [i for i, e in enumerate(trace) if e.get("decision", {}).get("action") == "read_document"
                          and e.get("observation", {}).get("ok")]
        checks["checked_after_reading_both"] = len(read_positions) >= 2 and any(
            e.get("decision", {}).get("action") == "search_documents" for e in trace[read_positions[1]+1:])
        checks["asks_for_scope"] = bool(result["follow_up_question"] and result["gaps"])
    return checks


def evaluate_cases(cases_path, output_dir, model_factory, selected=None):
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8-sig"))
    if selected:
        unknown = set(selected) - {c["id"] for c in cases}
        if unknown:
            raise ValueError("未知case_id: " + ", ".join(sorted(unknown)))
        cases = [c for c in cases if c["id"] in selected]
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("输出目录非空，请使用新目录以保留原始运行证据")
    model_factory()  # Validate configuration before creating any partial artifacts.
    source = json.loads((ROOT / "data/documents.json").read_text(encoding="utf-8"))
    result = {"created_at": now(), "python": platform.python_version(), "total": len(cases), "passed": 0,
              "scope": "固定合成用例的自动断言；不等同于一般语义准确率或候选人个人复核", "cases": []}
    for case in cases:
        kb = KnowledgeBase(case_documents(case, source))
        agent = Agent(model_factory(), Tools(kb, case.get("failure", "none")), case.get("max_steps", 10), case.get("max_tools", 8))
        report = agent.run(case["question"], case.get("history", []))
        report["case_id"] = case["id"]
        checks = check_case(case, report)
        passed = all(checks.values())
        folder = destination / case["id"]
        save_json(folder / "input.json", report["input"])
        save_json(folder / "documents.json", kb.documents)
        save_json(folder / "result.json", report["result"])
        save_json(folder / "run.json", report)
        save_json(folder / "checks.json", checks)
        trace_lines = [json.dumps(event, ensure_ascii=False) for event in report["trace"]]
        (folder / "trace.jsonl").write_text("\n".join(trace_lines) + "\n", encoding="utf-8")
        result["mode"] = report["mode"]
        result["model"] = report["model"]
        result["passed"] += int(passed)
        result["cases"].append({"id": case["id"], "passed": passed, "status": report["result"]["status"],
                                "checks": checks, "run": case["id"] + "/run.json", "covers": case["covers"]})
        save_json(destination / "summary.json", result)
        print(f"{case['id']}: {'PASS' if passed else 'FAIL'} ({report['result']['status']})", flush=True)
    return result
