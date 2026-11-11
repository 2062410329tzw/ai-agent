# 提交信息与发布步骤

- 项目题目：企业知识问答 Agent。
- 正式题号：题面未显示编号，请按招聘方实际编号填写，不能推测。
- GitHub URL：https://github.com/2062410329tzw/ai-agent 。这是用户指定的目标代码仓库；发布状态以最终交付记录为准。
- 最终commit SHA：在项目根目录运行`git rev-parse HEAD`，使用实际输出。SHA不写入同一个commit内以避免自引用问题。

## 推送到自己的GitHub仓库

本地代码与验证材料已经集中在同一文件夹。若本地已初始化Git并创建提交，直接从第2步开始。

1. 初始化并提交（仅在尚无Git提交时执行）：

   ```bash
   git init -b main
   git add .
   git commit -m "Complete enterprise knowledge QA agent submission"
   ```

2. 用户已经提供空仓库。若origin尚未配置，添加后推送：

   ```bash
   git remote add origin https://github.com/2062410329tzw/ai-agent.git
   git push -u origin main
   git rev-parse HEAD
   ```

3. 如果仓库私有，在仓库访问设置中让招聘方指定评审账号可读。题目未提供账号，本项目不猜测邀请对象。
4. 在提交入口填写正式题号、GitHub仓库URL、上一步SHA。确认SHA对应远端main最新提交。
5. 若之后修改任何代码或文档，重新commit/push并更新提交入口中的SHA。

## 发布前复核

读取README、运行测试和至少两条真实模型路径；检查`.env`及真实密钥未进入Git；候选人按事实补充AI使用说明中的个人验证记录。GitHub Actions只执行离线测试和证据一致性检查，不需要配置模型密钥，不能把它当作真实模型在线验收。

开发生成的本地提交如使用`Codex (AI-assisted build)`身份，仅表示AI创建交付快照，不代表候选人独立编写。候选人后续修改应使用本人正常Git身份提交。
