# 评估与验证

## 环境、复现与记录来源

验证日期：2026-11-11，本地Windows、Python 3.10.1，另在新建的空虚拟环境中运行，未安装第三方包。源代码快照d0c5364已通过GitHub Actions的Ubuntu、Python 3.10/3.13离线测试、Mock验收及证据检查，见[CI记录](https://github.com/2062410329tzw/ai-agent/actions/runs/42995138810)。真实模型验收在Windows执行，不把离线CI称为Linux真实模型联调。

开发和实际执行由Codex完成，候选人个人复核尚待本人记录。数据均为合成资料；调用外部模型只发送合成问题、合成历史、合成原文及动作协议。

```bash
python scripts/run_tests.py
python run.py evaluate --mode mock --output-dir local-runs/new-mock
python run.py evaluate --mode live --output-dir local-runs/new-live
python scripts/verify_artifacts.py
```

离线验证不需要密钥。真实验证按README配置`.env`；本次主要验证模型为`glm-4.5-flash`，`QA_THINKING=disabled`。每轮模型输出上限2400 tokens，最多10轮模型决策和8次业务工具调用。单请求超时60秒，模型HTTP异常不自动重试。

## 自动化测试实际结果

31项unittest通过，0 failures、0 errors，见[完整测试输出](../examples/test-results.txt)和[摘要](../examples/test-summary.json)。其中一项测试包含10个验收子用例；不能把它们再重复计入31的总数。

测试覆盖：完整离线验收、工具观察反馈至下一次模型调用、路径变化、中文改写检索、停用词回归、搜索截断、缺失片段、非法参数和未知工具、版本/原文/正文引用检查、错误引用后的模型修复、持续非法输出终止、模型失败不切Mock、工具预算、历史角色限制、模型HTTP请求协议和错误响应脱敏。

空虚拟环境中的复现及改进后10组离线验收均10/10通过，见[当前离线摘要](../examples/mock-v1/summary.json)。CLI正常、上下文入口及缺密钥退出行为见[CLI冒烟结果](../examples/cli-smoke.json)。这部分只证明代码流程与规则模拟行为，不证明真实模型推理效果。

## 真实模型执行

首次完整GLM-4.5-Flash验收 **7/10通过**，见[原始摘要](../examples/live-final/summary.json)。normal、conflict、followup、tool_recovery、tool_failure、mutation、step_limit通过；outside、paraphrase、read_recovery受到模型HTTP429影响，返回model_error，未记为通过。随后补跑2/3通过，口语改写出现过度扩展问题。该失败不是服务问题：模型正确读取30天，却主动追查未问的财务付款时间，最终误报资料不足。修复回答范围和主题召回后，完整回归保存在live-v1。

最终代码完整回归GLM-4.5-Flash为 **6/10**：正常、冲突、资料外、改写、检索恢复、上限通过，其余四项均为HTTP429或网络/超时错误。显式改用`glm-4-flash-250414`且`QA_THINKING=omit`补验四项，**4/4通过**，见[备用模型补验](../examples/live-v1-fallback/summary.json)。因此最终10个用例均有通过记录，来自两个模型、分轮运行，不能写成同一模型单轮10/10。

对失败项的显式补跑写入独立目录，不覆盖原始失败。最终逐例状态汇总在[验收汇总](../examples/acceptance-summary.json)，其中保留各次尝试的分子/分母，不将多次尝试合并后的覆盖率描述为单轮成功率。

| 验收点 | 输入/实际输出/Trace入口 | 预期 |
|---|---|---|
| 明确答案 | [normal](../examples/live-v1/normal/run.json) | 30天，引用D01 |
| 冲突 | [conflict](../examples/live-v1/conflict/run.json) | 两个期限、引用双方、补查后追问 |
| 资料外问题 | [outside补跑](../examples/live-v1/outside/run.json) | 无依据则说明缺口 |
| 相似改写 | [paraphrase补跑](../examples/live-v1/paraphrase/run.json) | 仍回答30天 |
| 上下文 | [followup](../examples/live-v1-fallback/followup/run.json) | 请假审批两档规则 |
| 工具临时失败 | [tool_recovery](../examples/live-v1/tool_recovery/run.json) | 观察错误后再决策，最终恢复 |
| 持续失败 | [tool_failure](../examples/live-v1-fallback/tool_failure/run.json) | 明确tool_error，不声称资料不存在 |
| 内容替换 | [mutation](../examples/live-v1-fallback/mutation/run.json) | 45天及修改后的原文 |
| 上限 | [step_limit](../examples/live-v1/step_limit/run.json) | max_steps_exceeded |
| 读取故障 | [read_recovery补跑](../examples/live-v1-fallback/read_recovery/run.json) | 观察读取失败后恢复 |

每个case目录另有input.json、result.json、documents.json、trace.jsonl、checks.json。完整记录是实际运行数据，路径摘要见[实际执行路径](../examples/execution-paths.md)。逐条回答与原文的AI审阅见[回答核对记录](../examples/answer-review.md)，不等同于候选人或独立评审的人工复核。

## 两条动态决策路径

正常路径：最新模型检索命中D01、读取D01并结束，共3轮模型调用、2次工具调用，回答费用发生后30天。早期live-final/normal另包含一次JSON格式错误和修复，原记录保留。

冲突路径：模型检索发现D01/D02，依次读取两份原文，继续执行两次补充检索后，返回needs_clarification。共6轮模型调用、5次工具调用，引用30天和15天两种规定，未擅自选择新版本。

工具失败路径：search_once第一次返回结构化故障；下一次模型选择再次检索，之后读取D01并回答。程序没有根据故障直接生成预写的成功答案。早期持续失败时真实模型尝试了4次检索后停止；最新备用模型补验更快停止。资料外问题仍可能反复补查，虽有上限约束，检索效率仍有改进空间。

## 内容替换与检索改进

早期live-final/normal与live-final/mutation的问题、模型及D01元数据相同，仅将实际原文30天改为45天并保存不同知识库哈希。真实答案从30天变为45天；读到的原文与引用一并变化。conflict相对normal增加D02，模型动作从读取单文档后回答变为读取双方并补查、追问。

早期离线验收[9/10](../examples/mock/summary.json)：资料外问题附加“制度”后误召回含“员工、制度”的报销资料。加入通用停用词后，[10/10](../examples/mock-final/summary.json)通过，并由test_stopwords_do_not_retrieve_unrelated_policy固定回归。此为小样本词法改进，不是通用检索准确率评测。

## 失败记录与限制

- [live-attempt-1](../examples/live-attempt-1/summary.json)：初始网络连接失败，0/10，未发生业务工具调用。
- [live](../examples/live/summary.json)：GLM-4.7-Flash服务异常，0/10；单独诊断确认供应商错误码1305，表示过载。
- [live-flash](../examples/live-flash/summary.json)：旧备用模型normal成功，conflict反复漏正文引用并达到上限，1/2。后来改进修复反馈和提示词，未删除失败日志。
- 备用模型的上下文回答有模板字样残留，故障结束包含多余追问；事实和引用核对通过，文案质量仍有缺陷，见回答核对记录。
- 模型服务过载可能使相同命令复跑失败。真实结果是一次开发过程中的固定小样本证据，不代表稳定性或生产准确率。
- 机械校验不能证明语义蕴含；自动断言以状态、必需来源、关键事实和动作特征为主，没有通用正确性证明。
- 词法召回、少量别名和小知识库不能代表复杂企业资料检索；截断结果可能遗漏冲突，提示词依从性也不能绝对保证。
- 尚未覆盖所有明确替代关系、跨部门范围、提示注入攻击、长对话、真实企业隐私权限和并发负载。
- 早期运行中JSON解析错误轮次未完整记入usage元数据，不能把已保存usage之和称为精确总计费；当前实现已补充错误轮次可取得的模型元数据。

## 用时

本轮可核对的开发起点为2026-11-11 16:35:50（北京时间），包含代码生成、测试、模型等待、失败修复和文档整理。本地开发与验收完成于2026-11-11 17:22:32（北京时间），经过46.7分钟，包含模型服务等待。GitHub登录与上传时间另计。时间及最终工具重放检查见examples/release-checks.json；不把AI辅助经过时间冒充候选人独立工时。
