"""Independently compare saved successful citations with corpus and read trace."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from knowledge_agent.tools import KnowledgeBase

count = 0
for path in sorted((root / "examples").glob("*/*/run.json")):
    run = json.loads(path.read_text(encoding="utf-8"))
    kb = KnowledgeBase.load(path.with_name("documents.json"))
    assert run["knowledge_sha256"] == kb.fingerprint, str(path)
    assert run["input"] == json.loads(path.with_name("input.json").read_text(encoding="utf-8")), str(path)
    assert run["result"] == json.loads(path.with_name("result.json").read_text(encoding="utf-8")), str(path)
    lines = [json.loads(line) for line in path.with_name("trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert lines == run["trace"], str(path)
    assert run["model_calls"] == len(lines) <= run["limits"]["max_steps"], str(path)
    assert run["tool_calls"] == sum("observation" in event for event in lines) <= run["limits"]["max_tools"], str(path)
    read = set()
    for event in lines:
        if event.get("decision", {}).get("action") == "read_document" and event.get("observation", {}).get("ok"):
            doc = event["observation"]["document"]
            key = (doc["doc_id"], doc["section_id"])
            assert doc == kb.index[key], str(path)
            read.add(key)
    for cite in run["result"]["citations"]:
        key = (cite["doc_id"], cite["section_id"])
        assert key in read, str(path)
        assert cite["version_date"] == kb.index[key]["version_date"], str(path)
        assert cite["quote"] and cite["quote"] in kb.index[key]["text"], str(path)
    count += 1
if not count:
    raise SystemExit("No artifacts found")
print(f"Verified {count} saved runs: corpus hashes, source quotes, read observations, counts and trace consistency.")
print("This is a mechanical integrity check, not semantic entailment or human review.")
