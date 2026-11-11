import argparse
import json
import sys
from pathlib import Path

from .agent import Agent
from .models import ChatModel, MockModel, load_env
from .tools import KnowledgeBase, Tools

ROOT = Path(__file__).resolve().parents[2]


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="企业知识问答Agent：显式选择mock或live")
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask", help="问答，输出完整JSON运行记录")
    ask.add_argument("question")
    ask.add_argument("--history", help="包含role/content消息数组的JSON文件")
    ask.add_argument("--data", default=str(ROOT / "data/documents.json"))
    ask.add_argument("--failure", choices=["none", "search_once", "search_always", "read_once", "read_always"], default="none")
    ask.add_argument("--max-steps", type=int, default=10)
    ask.add_argument("--max-tools", type=int, default=8)
    ask.add_argument("--output", help="完整结果与Trace写入路径")
    evaluate = sub.add_parser("evaluate", help="执行验收集，保存逐条输入、输出、Trace及知识库快照")
    evaluate.add_argument("--cases", default=str(ROOT / "examples/cases.json"))
    evaluate.add_argument("--output-dir", required=True)
    evaluate.add_argument("--case", action="append", help="只运行指定case_id，可重复")
    for cmd in (ask, evaluate):
        cmd.add_argument("--mode", required=True, choices=["mock", "live"])
        cmd.add_argument("--env-file", default=".env", help="仅加载明确指定文件，环境变量优先")
    args = parser.parse_args(argv)
    try:
        factory = lambda: MockModel() if args.mode == "mock" else ChatModel(load_env(args.env_file))
        if args.command == "evaluate":
            from .evaluation import evaluate_cases
            report = evaluate_cases(args.cases, args.output_dir, factory, args.case)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["passed"] == report["total"] else 1
        kb = KnowledgeBase.load(args.data)
        history = json.loads(Path(args.history).read_text(encoding="utf-8-sig")) if args.history else []
        report = Agent(factory(), Tools(kb, args.failure), args.max_steps, args.max_tools).run(args.question, history)
        if args.output:
            save_json(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if report["result"]["status"] in {"model_error", "tool_error", "max_steps_exceeded"} else 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "configuration_error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
