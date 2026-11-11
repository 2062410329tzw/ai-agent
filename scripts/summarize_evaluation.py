"""Aggregate explicit attempts; retain first-attempt failures and latest results."""
import argparse
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("runs", nargs="+", help="Run directories under examples, in chronological order")
args = parser.parse_args()
expected = json.loads((root / "examples/cases.json").read_text(encoding="utf-8"))
latest, attempts = {}, []
for directory in args.runs:
    path = (root / "examples" / directory).resolve()
    if path.parent != (root / "examples").resolve():
        raise SystemExit("Only direct run directories under examples are accepted")
    report = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    if report["mode"] != "live" or len(report["cases"]) != report["total"]:
        raise SystemExit("Only finished live evaluations may be aggregated")
    attempts.append({"directory": directory, "passed": report["passed"], "total": report["total"], "model": report["model"]})
    for case in report["cases"]:
        latest[case["id"]] = {**case, "run": directory + "/" + case["run"]}
cases = [latest[c["id"]] for c in expected if c["id"] in latest]
result = {"note": "Latest result per case across explicit attempts; not a single-run success rate. Raw failures retained.",
          "total": len(expected), "evaluated": len(cases), "passed": sum(c["passed"] for c in cases),
          "attempts": attempts, "cases": cases}
(root / "examples/acceptance-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = ["# 实际执行路径", "", "由保存的真实模型run.json生成。以下为公开动作与观察，不包含模型内部思维过程。", ""]
for case in cases:
    if case["id"] not in {"normal", "conflict", "outside", "tool_recovery", "mutation"}:
        continue
    run = json.loads((root / "examples" / case["run"]).read_text(encoding="utf-8"))
    lines += ["## " + case["id"], "", f"[完整记录]({case['run']})；状态：{run['result']['status']}", "",
              "| 步骤 | 动作及参数 | 工具摘要或校验结果 | 后续动作 | 简短行动依据 |", "|---|---|---|---|---|"]
    for event in run["trace"]:
        decision = event.get("decision", {})
        cells = [str(event["step"]), decision.get("action", "模型输出错误") + " " + json.dumps(decision.get("arguments", {}) if decision.get("action") != "finish" else {"status": decision["arguments"]["status"]}, ensure_ascii=False),
                 json.dumps(event.get("return_summary", event.get("validation_error", event.get("outcome", event.get("model_error", "")))), ensure_ascii=False),
                 event["next_action"], decision.get("reason", "")]
        lines.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    lines += ["", "实际回答：" + run["result"]["answer"], ""]
(root / "examples/execution-paths.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
print(json.dumps({"passed": result["passed"], "total": result["total"], "attempts": attempts}, ensure_ascii=False))
raise SystemExit(0 if result["passed"] == result["total"] else 1)
