# 方案与取舍

## 调用流程

`run.py -> cli.py -> Agent.run -> Model.decide -> Tools.execute -> 观察反馈 -> Model.decide`。

采用原生Python循环，没有使用Agent框架，因而无需框架运行时或框架版本。Python标准库承担HTTP、JSON、CLI、哈希和unittest。可选安装包的构建配置使用setuptools；从仓库执行run.py不需要安装构建工具。

每轮给模型的消息包含系统动作协议、用户问题/历史、此前结构化动作、真实工具观察及剩余预算。模型输出一个JSON动作，程序按白名单执行。这里采用结构化JSON动作协议，不依赖供应商原生tool_calls；search/read/finish的选择和参数均来自模型响应。

核心流程不包含“有冲突就自动补查”等业务分支。冲突识别与下一步选择由模型完成；Python只负责协议检查、工具执行、引用校验、预算和错误边界。MockModel内的条件分支仅用于离线流程模拟，不是模型驱动ReAct的证明。

## 工具与检索

`search_documents(query, limit=8)`返回多个相关片段的文档ID、版本、标题、位置、摘要、分数、总数及截断标记。`read_document(doc_id, section_id)`返回原文、适用范围和明确替代关系。搜索摘要不进入可引用证据集合，只有成功读取的片段才能被引用。

使用中文二元词项、英文/数字词项和少量业务别名匹配。词项交集计分，主题命中加权；同分按文档ID排序，不能视为优先级。为减少通用词误召回，过滤员工、制度等词项。查询显式提及主题时，候选的标题、正文或主题至少要涉及所问主题；不会排除正文涉及报销的跨主题优先级通知。未采用向量库：五份合成资料下，确定性可解释的词法检索便于在时间预算内验证冲突处理。代价是对复杂语义和未知同义表达召回不足，不能宣称生产级检索效果。

## 冲突与上下文

提示词要求读取同主题的相关版本，发现冲突后补查适用范围/优先级/替代关系。日期较新或分数较高都不能作为选取规则的依据。冲突无法消解时输出needs_clarification，引用双方并请求适用制度信息。

历史作为JSON数据随用户问题传入，禁止system角色。模型自行补全省略表达后检索，历史旧回答不加入可引用证据集合。工具返回和历史中的指令视为不可信数据；提示词隔离不能保证抵抗所有提示注入，本项目未做完整对抗安全认证。

## 输出检查与边界

引用检查文档/片段存在于本次读取集合、版本一致、quote是非空连续原文、正文标记与引用清单一致。不接受不存在的引用、摘要代替原文、拼接伪造片段或无引用的completed。校验失败反馈模型并占用下一轮预算；达到预算返回max_steps_exceeded。

这些是结构与来源检查，不是通用语义蕴含证明。错误结论即使附了真实原文，也可能通过机械校验，因此评测另外检查关键事实并逐条审阅真实输出。未实现自动法律/制度优先级推理验证器；资料中出现明确替代关系时主要依靠模型理解，当前验收聚焦题面要求的无优先级冲突。

状态包括completed、needs_clarification、insufficient_evidence、tool_error，以及Runtime产生的model_error、max_steps_exceeded。工具失败不可当作空结果；缺少成功检索时不得声称资料不足。工具错误以结构化观察返回模型，不进行隐形自动业务重试。模型HTTP错误直接形成model_error，不静默切换Mock。

## 可观察性

每步记录模型选择、工具参数、返回摘要、完整观察、简短行动依据和next_action。运行还包含模式、模型名、知识库SHA256、提示词SHA256、预算、UTC时间、模型调用与工具调用次数、耗时。真实模型保存供应商请求ID及usage（若返回），不读取或保存reasoning_content，不保存Authorization或密钥。

`examples/*/<case>/`包含input.json、documents.json、result.json、run.json、trace.jsonl、checks.json。评测不覆盖已有非空目录，失败运行保留。数据与用例文件必须受信任；本CLI不是面向不可信租户的服务器。

## 模型接入依据

按智谱官方[对话补全API](https://docs.bigmodel.cn/api-reference/模型-api/对话补全)使用HTTPS聊天接口、JSON输出和消息列表；模型参数参考[GLM-4.7-Flash官方文档](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash)。查阅日期：2026-11-11。

QA_BASE_URL、QA_MODEL、QA_API_KEY可配置，QA_THINKING=omit适用于不接受thinking字段的接口。其他兼容服务未实际联调，不保证仅替换地址即可支持所有供应商。默认不自动重试模型调用、不自动切换模型。网络不可用时可使用显式Mock验证流程。
