# Git 维护约定

代码仓库：<https://github.com/huanyu-9019/QQbot>。
用户已授权本机和服务器维护程序自行查历史、提交和推送已验证的项目修改。

## 分支与生产

- `codex/astrbot-migration`：本机整理的迁移与维护源码、测试、操作记录。
- `codex/qq-autonomous-evolution`：Codex 服务器成功发布后的自动演进记录。
- `main`：现有默认分支。以上两个工作分支各自推进；本次不把未审定的
  服务器演进与本机工作直接混合到 main，也不改写旧提交。
- 生产源码在 QQ 服务器 `/home/hermes`，安装中的插件位于
  `/opt/jiangsheng-astrbot/runtime/data/plugins`。服务器 Git 工作目录在
  `/home/admin/qq-evolution/development`。Git 提交和生产部署是两件事。

## 提交信息

手动维护使用具体中文标题，例如 `fix(admin): 修复状态采集缺失依赖导致的过期数据`。
正文写清：

1. 实际问题与可复现触发条件。
2. 找到的原因，而不只是“优化了一下”。
3. 改了哪些行为和文件，保留哪些边界。
4. 实际跑过的验证、已知限制、是否已部署。
5. 可用的生产快照或回退办法。

自动提交使用同样的分段正文，记录文件、问题类别、修改层级、增删行数、
补丁 SHA-256 和生产快照。模型评估证据可能包含聊天内容，不能原样放入公开提交；
自动正文只使用固定类别和发布回执，具体实现变化看该提交 diff。
旧的泛化提交信息保留，不为了美化历史而重写。

## 每轮工作

先核对 status 和差异；只提交本次明确负责并验证的内容。
运行相应测试，扫描待提交文件，分主题提交后普通 push。
用 `git ls-remote` 比对远端 SHA；失败则保留本地提交并重试，不能谎称已上传。
服务器现有 `QQ_EVOLUTION_GIT_REMOTE=origin` 启用自动推送，每轮轮询重试未完成归档。
生产发布失败不生成“发布成功”提交。

不提交凭据、原始聊天、用户档案、记忆数据库或临时修复补丁。
服务器上与本次无关的脏文件要保留，不能用 add . 或 reset --hard 一起处理。

## 查以前为什么这样改

```sh
git fetch origin
git log --all --oneline --decorate -30
git log --all --grep='状态采集'
git log --follow -- migration/plugin/policy.py
git show <commit>
git blame migration/plugin/policy.py
git log --all -S 'sender_identity_mismatch' -- migration/plugin/main.py
git log --all -G 'learning_status' -- qq-evolution/publish_admin_status.py
```

修改前先查首次引入、后续修补与部署记录。回退用新提交或生产快照，
不删除远端历史；回退代码仍须测试并重新发布。
