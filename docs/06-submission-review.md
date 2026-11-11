# 提交前复审（2026-11-11）

结论：修复本轮发现的异常边界后，项目具备题面要求的核心代码、运行方式、决策循环、验收证据和文档，可以作为本题提交。该结论针对考题要求，不承诺真实模型每次运行成功或获得特定评分。

复审由Codex执行，不冒充候选人或独立评审的人工核查。复审前远端main为a045fe02662420b36c4b2b60ce73af35451e5139；本轮修复另行提交，提交入口必须使用更新后的最终SHA。

## 逐项核对

| 要求 | 核对结论 | 证据 |
|---|---|---|
| 可复制运行入口 | Python CLI；独立解压目录及CI均可运行 | README、run.py、GitHub Actions |
| 模型驱动循环 | live适配实际调用远程模型，执行其动作，将观察反馈到下一次调用 | agent.py、models.py、live-v1中的正常/冲突Trace |
| 两条不同执行路径 | 正常读取后回答；冲突读取双方后两次补查并追问 | examples/execution-paths.md |
| 执行上限 | 模型轮数与工具次数均有限制，非法输出修复也计入预算 | tests、step_limit运行记录 |
| 明确答案 | 原文支持30天，包含起算条件及引用 | live-v1/normal |
| 文档冲突 | 保留30天/15天，引用双方，不凭日期选制度 | live-v1/conflict |
| 资料外问题 | 拒绝编造资料不存在的保险赔付规则 | live-v1/outside |
| 改写后相似问题 | “发票最晚、报账”仍返回报销提交期限 | live-v1/paraphrase |
| 上下文追问 | 根据请假历史查询两档审批规则 | live-v1-fallback/followup |
| 工具失败 | 检索与读取故障进入模型观察；持续失败明确结束 | tool_recovery、tool_failure、read_recovery |
| 引用支持性 | 成功样例中的原文支持制度事实；引用须实际读取、版本一致、原文可定位 | answer-review.md、verify_artifacts.py |
| 替换文档内容 | 同模型对照30天改45天；本轮另换ID、片段ID及单位后返回7个工作日 | 原mutation及review-live/renamed_units |
| 统一交付结构 | README、src、tests、examples、data、五份文档、依赖文件、.env.example均存在 | 仓库目录 |
| 实际记录与失败披露 | 没有将Mock当成真实模型，也没有把跨模型补跑称为单轮10/10 | 03-evaluation.md、acceptance-summary.json |
| 用时与AI使用 | 首次开发经过时间、AI范围、个人贡献边界已记录；本轮复审另计 | 03、04、05及本轮review-checks.json |
| GitHub交付 | 仓库当前公开可读，已核对远端SHA；发布后核查当前提交CI | SUBMISSION.md与GitHub Actions |

## 本轮发现并修复的问题

1. **输入格式边界**：空对象历史会被误当作无历史；数组类型的role会抛TypeError；非对象文档/片段会抛AttributeError。现统一为明确ValueError，由CLI返回configuration_error，不再产生未处理回溯。
2. **模型响应边界**：服务返回`choices: [null]`会抛AttributeError。现转换为model_error，保持明确未完成状态及运行Trace。

新增5项回归测试，当前 **36项全部通过**。原来的10组离线验收再次 **10/10通过**，记录位于[本轮离线验收](../examples/mock-review/summary.json)。修复没有改动检索排序、提示词、正常模型动作或已有原始Trace。

## 独立业务复验

未将原验收集的期望答案传给模型。新资料在每个case目录保存，使用glm-4.5-flash真实调用，结果为 **2/3通过，1项被服务429中断**，不能写成3/3。

| 新测试 | 实际结果 | 判断 |
|---|---|---|
| [更换ID、片段ID及期限单位](../examples/review-live/renamed_units/run.json) | POL77/RULE7，费用发生后7个工作日，正确引用修改原文 | 通过，答案不是固定的D01/30天 |
| [更换冲突内容并调整日期](../examples/review-live/renamed_conflict/run.json) | 已读取7/12个工作日并补查，结束前HTTP429 | 未完成；不计通过，原有冲突验收仍有成功证据 |
| [相关主题但资料未覆盖](../examples/review-live/related_outside/run.json) | 询问提交后到账时间；说明仅有提交期限，缺少到账规定 | 通过，没有把30天提交期限冒充到账时间 |

重跑示例（需配置真实模型密钥）：

```bash
python run.py ask "差旅报销申请最迟何时提交？" --mode live --data examples/review-live/renamed_units/documents.json --output local-runs/review-units.json
python run.py ask "差旅报销申请最迟何时提交？" --mode live --data examples/review-live/renamed_conflict/documents.json --output local-runs/review-conflict.json
python run.py ask "报销申请提交后几天能到账？" --mode live --data data/documents-normal.json --output local-runs/review-arrival.json
```

## 保留的限制与提交前个人事项

- 主模型最终整轮仍是6/10，显式备用模型补验4/4；额外复验也发生429。服务稳定性有限，不能宣传为单轮100%成功。
- 机械引用校验不证明任意回答的语义正确。本轮成功答案逐条核对未发现无依据制度结论，但这不是通用正确性保证。
- 备用模型上下文回答有模板字样残留，失败结束有多余追问；这些展示问题已披露，未修改实际输出美化日志。
- 词法检索面向小合成集，复杂同义表达、更多文档和明确适用范围仍需更广评测。
- 题面未给正式题号，候选人须按招聘方实际编号填写。
- AI使用与现有个人贡献已如实记录；若要证明个人学习和修改能力，候选人应亲自运行、理解并按实际情况补充个人复核/修改记录。AI不能代填未发生的个人经历。
