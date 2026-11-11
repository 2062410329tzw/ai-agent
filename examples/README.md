# 运行证据索引

先读[最终验收汇总](acceptance-summary.json)、[实际执行路径](execution-paths.md)、[回答核对](answer-review.md)。汇总明确区分每次尝试，不隐藏失败，不把跨次覆盖率写成单轮成功率。

| 目录 | 含义 |
|---|---|
| mock | 首轮离线验收，保留通用词误召回的失败 |
| mock-final | 停用词修复后的离线验收 |
| mock-release | 空虚拟环境中的离线复现 |
| mock-v1 | 主题召回与回答范围改进后的离线验收 |
| live-attempt-1 | 初始网络连接失败记录 |
| live | GLM-4.7-Flash服务错误记录 |
| live-flash | 旧Flash模型的正常成功和冲突格式失败 |
| live-final | GLM-4.5-Flash首轮完整验收，7/10 |
| live-retry | 首轮三个失败项的补跑，2/3；保留改写问题范围扩展失败 |
| live-v1 | 修复问题范围扩展后的完整真实回归，6/10，其余为模型服务错误 |
| live-v1-fallback | 同一最终提示词，显式备用模型补验四个服务失败项，4/4 |

每个case内：input.json为原始输入，documents.json为该次知识库，result.json为实际结果，run.json为完整记录，trace.jsonl为逐步记录，checks.json为自动断言。日志中的reason是模型对行动的简短说明，不是内部思维链。

test-results.txt与test-summary.json来自unittest实际执行；cli-smoke.json为真实CLI入口检查。执行脚本可重建汇总，不能修改原始结果制造通过记录。
