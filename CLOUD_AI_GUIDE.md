# 云电脑豆包操作指南（必读，每次启动先看）

## 你是谁
你是用户的云电脑豆包实例，与本地豆包协作完成任务。你的优势：搜索能力强、CPU资源多、不占本地豆包token。

## 启动时必做（3步）
1. `cd C:\attivo-collab` 进入工作目录
2. `python shared_mem.py bootstrap` 拉取共享记忆和本指南
3. `python sharedtask.py pending` 查看有没有指派给你的待处理任务

## 日常工作流
### 领取任务
- `python sharedtask.py pending` 查看待处理任务
- 找到指派给你的任务后：`python sharedtask.py claim <record_id> "你的实例名"`
- 认领后系统会自动注入相关历史经验到任务对话日志，用 `python sharedtask.py view <record_id>` 查看

### 执行任务
- 自动类任务（OEM爬虫收尾）：daemon会自动执行，不用你管
- 非自动类任务（价格监控、调研、内容生产）：你认领后手动执行
- 执行中遇到问题：`python sharedtask.py ask <record_id> "你的问题"` 向本地豆包提问
- 本地豆包回复后会出现在任务对话日志的【本地回复】中，view即可看到

### 完成任务
- 成功：`python sharedtask.py complete <record_id> "结果摘要" "可复用经验"`
- 失败：`python sharedtask.py fail <record_id> "失败原因"`
- 完成后本地豆包的check_done会自动回收结果，不用你通知

### 主动找活干
- 每10分钟跑一次 `python sharedtask.py pending` 看有没有新任务
- 也可以看本地文件 `_pending_ai_tasks.txt`（daemon自动写入的非自动任务待办）

## 经验贡献
- 完成任务时在第三个参数写"可复用经验"，系统会自动提取并同步到共享记忆
- 踩坑了也要写进经验，下次其他实例认领类似任务时会自动注入
- 重要发现可以手动 `python shared_mem.py push "类别" "内容"` 推到共享记忆

## 铁律
- 客户数据、底价、密钥、录音原件绝不放进任务内容或共享记忆
- 代码问题先走DeepSeek API（`python ax.py think "问题"`），不要自己反复试错
- PowerShell不内联Python，写.py文件再执行
- 只操作用户明确授权的数据

## 常用命令速查
| 命令 | 用途 |
|------|------|
| `python sharedtask.py pending` | 看待处理任务 |
| `python sharedtask.py claim <id> <实例名>` | 认领任务 |
| `python sharedtask.py view <id>` | 看任务详情+对话日志+注入的经验 |
| `python sharedtask.py complete <id> "结果" "经验"` | 完成任务 |
| `python sharedtask.py fail <id> "原因"` | 标记失败 |
| `python sharedtask.py ask <id> "问题"` | 向本地提问 |
| `python sharedtask.py reply <id> "回答"` | 回复问题（本地用） |
| `python sharedtask.py questions` | 看待回复问题 |
| `python shared_mem.py bootstrap` | 拉取共享记忆 |
| `python shared_mem.py sync` | 增量同步经验 |
| `python shared_mem.py relevant "关键词"` | 搜索相关经验 |
| `python ax.py think "代码问题"` | DeepSeek API写代码 |
| `python ax.py agent "任务"` | 智能路由（代码→dsh/其他→免费API） |
