# 企业知识问答 Agent

小影校招AI Agent开发岗位项目：员工制度/产品知识问答。原生Python实现模型选择动作、执行工具、观察结果、再次决策的循环，交付答案、原文引用、资料缺口和任务状态。

> 本项目由候选人与AI辅助工具协作完成，贡献边界见 [AI使用说明](docs/04-ai-usage.md)。全部业务资料为合成内容。Mock仅验证流程，不能证明真实模型决策；实际结果与失败记录见 [评估文档](docs/03-evaluation.md)。

## 评审入口

1. 运行下面的离线命令，再看 `examples/mock-v1/` 的实际输出。
2. 阅读 [需求与验收映射](docs/01-requirements.md)、[方案与决策循环](docs/02-solution.md)。
3. 查看 [真实模型验收汇总](examples/acceptance-summary.json)和[实际执行路径](examples/execution-paths.md)。汇总保留首轮及补跑结果，逐条输入、知识库快照、输出和Trace都在对应case目录。
4. 比较 [正常路径](examples/live-v1/normal/run.json) 和 [冲突路径](examples/live-v1/conflict/run.json)，再比较 [内容替换](examples/live-v1-fallback/mutation/run.json)。
5. 阅读 [测试与限制](docs/03-evaluation.md)、[AI使用](docs/04-ai-usage.md)、[复盘](docs/05-retrospective.md)。

本地验证：31项自动化测试通过、离线验收10/10；真实验收主模型最终整轮6/10，服务错误项切换配置补验4/4。最终10项均有真实通过记录，涉及两个模型，全部失败记录保留。

## 环境与安装

Python **3.10或更新版本**。核心运行与unittest测试只用标准库，没有第三方依赖，无需Docker、数据库或API框架。

在仓库根目录执行。确认`python --version`不低于3.10；Windows也可以把命令中的`python`替换为`py -3.10`。本开发机器PATH的默认python为3.8，所以本机请用`py -3.10`。

```bash
python --version
python -m pip install -r requirements.txt
```

第二行会确认无额外依赖，可以省略。`run.py`直接加载`src/`；不要求`pip install -e .`。可自行创建虚拟环境。

## 一分钟离线运行

```bash
# 正常：只存在30天制度
python run.py ask "报销期限多久？" --mode mock --data data/documents-normal.json --output local-runs/normal.json

# 冲突：默认知识库同时存在30天和15天制度
python run.py ask "报销期限多久？" --mode mock --output local-runs/conflict.json

# 上下文追问
python run.py ask "那需要谁审批？" --mode mock --history examples/history.json

# 检索故障后由模型替身决定下一步；持续失败可改成search_always
python run.py ask "报销期限多久？" --mode mock --failure search_once

# 明确演示执行上限
python run.py ask "报销期限多久？" --mode mock --max-steps 1
```

完整JSON写到stdout，指定`--output`还会保存文件。`result`是业务结果，`trace`是逐步动作与观察。正常业务结束、追问、资料不足的进程退出码为0；工具/模型错误、达到上限、配置错误为2。达到上限的演示命令返回2是预期行为。

## 真实模型运行

复制`.env.example`为`.env`，填自己的QA_API_KEY，按评估文档中的已验证模型设置QA_MODEL与QA_THINKING。**不能提交`.env`和真实密钥。** 环境变量优先于文件；程序只读取指定文件，不自动搜索父目录凭据。

PowerShell：

```powershell
Copy-Item .env.example .env
# 编辑.env后运行
py -3.10 run.py ask "报销期限多久？" --mode live --env-file .env --output local-runs/live-conflict.json
```

macOS/Linux：

```bash
cp .env.example .env
# 编辑.env后运行
python run.py ask "报销期限多久？" --mode live --env-file .env --output local-runs/live-conflict.json
```

QA_BASE_URL是HTTPS聊天API基础地址，程序追加`/chat/completions`。每轮由远程模型输出一个结构化动作，而非预设日志。模型服务故障时返回model_error，不会伪装成资料不足或自动切换Mock；切换模型需显式修改配置并保留原失败记录。

## 测试与复现实验

```bash
# 不访问模型服务
python -m unittest discover -s tests -v

# 保存本次测试结果到examples/test-results.txt与test-summary.json
python scripts/run_tests.py

# 10组离线验收，保存逐例输入/输出/Trace/知识库快照
python run.py evaluate --mode mock --output-dir local-runs/mock-evaluation

# 真实模型验收，会请求配置的模型API；服务费用由所用账号/模型决定
python run.py evaluate --mode live --env-file .env --output-dir local-runs/live-evaluation

# 只运行指定案例，case可重复指定
python run.py evaluate --mode live --output-dir local-runs/live-two-paths --case normal --case conflict

# 核对已保存运行记录的知识库哈希、引用原文和Trace一致性
python scripts/verify_artifacts.py
```

评测输出目录必须为空或不存在，第二次复现请换一个新目录，不会覆盖历史证据。evaluate全部用例通过退出0，否则退出1；配置问题退出2。`--max-steps`控制模型轮数（含修复），`--max-tools`控制业务工具次数。

normal去除D02；mutation在此基础上把D01的30天替换45天；conflict使用全部文档。这些变换只改变知识库，答案仍由模型观察工具结果后生成。每次评测实际资料保存在case目录的documents.json中，可直接复跑：

```bash
python run.py ask "报销期限多久？" --mode mock --data examples/mock-v1/mutation/documents.json
```

## 目录

```text
src/knowledge_agent/  CLI、Agent循环、模型适配、工具、检索、引用校验、评测
tests/               可执行离线测试
data/                合成制度与正常场景知识库
examples/            用例、历史、实际输入/输出/Trace、失败记录、测试报告
docs/                五份要求文档及提交说明
scripts/             测试记录与证据校验脚本
run.py               无需安装的启动入口
requirements.txt     无第三方运行依赖说明
.env.example         模型配置模板
```

## 提交

正式题号、GitHub URL、最终commit SHA及推送步骤见 [提交说明](docs/SUBMISSION.md)。本地可运行与远程仓库可供评审读取是两个检查项；未推送前不能声称GitHub交付已完成。
