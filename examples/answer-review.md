# 真实回答与证据核对

审阅者：Codex（AI辅助审阅），2026-11-11。不是候选人亲自复核或独立人工评审。依据最终验收汇总指向的实际run.json及各case内documents.json逐条核对，原始回答未改写。

| 用例 | 实际行为及依据核对 | 结论 |
|---|---|---|
| [normal](live-v1/normal/run.json) | 回答费用发生后30天；D01原文逐字包含该起算点和期限；本次已读取D01 | 事实及引用一致 |
| [conflict](live-v1/conflict/run.json) | 读取D01的30天及D02的15天，补查适用范围、替代关系和优先级；最终保留双方、请求澄清，没有按日期选择15天 | 符合冲突要求 |
| [outside](live-v1/outside/run.json) | 多次检索无命中，说明未找到宠物医疗保险制度，不编造比例，不附无关引用 | 资料外拒答正确；7次检索偏多 |
| [paraphrase](live-v1/paraphrase/run.json) | “发票最晚啥时候交、报账”被理解为报销申请提交期限；回答费用发生后30天并需附票，均由D01支持 | 修复了未问事项扩展问题 |
| [followup](live-v1-fallback/followup/run.json) | 根据请假历史查询D03；不超过3天直属主管，超过3天还须部门负责人，未漏掉条件 | 事实正确；正文有“原文支持的结论”模板残留，展示不够简洁 |
| [tool_recovery](live-v1/tool_recovery/run.json) | 首次检索返回合成故障，随后模型重选检索、成功读取D01、回答30天 | 故障反馈及恢复可追踪 |
| [tool_failure](live-v1-fallback/tool_failure/run.json) | 持续合成故障后返回tool_error，说明无法检索，没有把工具故障解释成制度不存在 | 状态正确；额外“其他问题”追问无必要 |
| [mutation](live-v1-fallback/mutation/run.json) | 读取的D01已改45天，回答和引用均为45天；没有复用30天答案 | 内容替换有效 |
| [step_limit](live-v1/step_limit/run.json) | 1次模型调用、1次检索后返回明确未完成状态 | 上限生效 |
| [read_recovery](live-v1-fallback/read_recovery/run.json) | 读取失败作为观察反馈；后续成功读取D03，回答申请提前时间与两档审批 | 事实及引用一致 |

正常与冲突的最新成功记录均来自glm-4.5-flash和相同提示词，知识库差异为新增D02，因此可以直接观察工具结果变化对应的动作变化。30天改45天的同模型对照另见[首轮normal](live-final/normal/run.json)与[首轮mutation](live-final/mutation/run.json)，均为glm-4.5-flash；最终备用模型结果再次验证45天，但不将不同模型的两次输出作为严格控制变量实验。

自动断言通过不等于文案完美。上述模板残留与多余追问未改变制度事实或引用支持性，仍作为已知展示缺陷保留，没有修改实际输出来美化结果。下一步应在独立测试集上验证更强的格式约束，不能仅为这些样例硬编码答案。
