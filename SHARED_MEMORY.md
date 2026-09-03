# 豆包共享记忆（本地↔云电脑同步）

> 非机密信息同步通道。客户数据、底价、密钥、录音原件禁止写入。
> 本地豆包和云电脑豆包都读写此文件，启动时先pull，变更后push。

## 一、用户偏好与铁律（长期有效）
- 回复≤3句，要点式，直接给结论
- 代码问题必须走DeepSeek API或dsh agent，禁止自己反复试错
- PowerShell不内联Python，永远写.py文件
- 截图不进上下文，本地RapidOCR提文字
- 录音总结必须豆包亲自做，不外包AI
- Odoo只操作user_id=18（陈国标），备注必须append_html保留原文
- 报销周期按半月（如8.16-8.31），审批人He JiaLei，金额会计填

## 二、已完成项目（避免重复造轮子）
- OEM配件知识库：oemkb.db（Yamaha 110万零件，Suzuki爬中），megazip来源
- attivox官网产品库：shop_products.json（2403产品）+ product_details.json（详情）
- yamamotor配件目录：yamamotor_parts.json（3888配件，7品牌）
- boats.net爬虫：crawl_boatsnet.py（playwright绕过CF）
- 费用报销脚本：ax.py toll/expense（通行费一条龙）
- 补手机号脚本：crm_ops.py phonebatch（微信名片/视频号OCR）
- 商机备注同步：sync_leads.py（定时任务每天8:00）
- 多AI路由：ax.py think（DeepSeek）/ ax.py ai（GLM/通义/火山免费）

## 三、进行中任务
- [ ] Suzuki megazip零件爬取（units 1545+，sections/parts待跑）
- [ ] attivox详情页兼容性数据爬取（823/2403）
- [ ] boats.net零件爬取（playwright，Yamaha+Suzuki）
- [ ] 电商平台国产船外机配件价格监控（云电脑负责）

## 四、业务决策记录
- 目标市场：90-300马力区间，60以下被国产件碾压
- 福建是主战场（转化率25%），浙江基本放弃（6%）
- 复购全是小件（碳刷/叶轮/油封），大件零复购
- F150齿轮不成套（有小齿缺前齿后齿），铃木DF90/DF140空白

## 五、云电脑→本地同步区
（云电脑跑完任务后在此追加结果摘要和数据文件路径）

## 六、本地→云电脑同步区
（本地豆包变更偏好/决策后在此追加）

---
*最后更新：2026-09-03 15:51*


## 云电脑使用说明

- [09-02 09:48] 云电脑豆包启动时先执行: ax memory pull 10 和 ax memory sync-github；跑完任务后: ax memory push 标题 类型 内容 标签，大数据文件传GitHub仓，摘要push到SHARED_MEMORY.md；禁止写入客户数据/底价/密钥/录音原件


## 已完成任务

- [09-03 15:51] [开发助手自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': None}

- [09-03 15:16] [云电脑 爬虫脚本自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': None}

- [09-03 15:00] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T15:00:35.954630
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 14:46)
  sharedtask.py: 存在(更新于09-03 14:46)
  shared_mem.py: 存在(更新于09-03 14:46)
  config.py: 存在(更新于09-02 21:44)

- [09-03 14:54] [开发助手自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': None}

- [09-03 14:53] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T14:53:36.096486
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 14:46)
  sharedtask.py: 存在(更新于09-03 14:46)
  shared_mem.py: 存在(更新于09-03 14:46)
  config.py: 存在(更新于09-02 21:44)

- [09-03 14:46] [保活配置-Linux三层终极保活(脚本优化)] 系统运维完成: 保活配置已派发(云电脑 价格监控)，6秒后异步执行三层保活，daemon将自动重启

- [09-03 14:37] [保活配置-Linux三层终极保活(脚本优化)] {' reusable_experience': None, ' pitfall_lessons': None, ' reusable_code_or_script_name': None, ' output_data_file_path': None}

- [09-03 14:15] [开发助手自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': None}

- [09-03 13:42] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T13:42:20.525154
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 13:41)
  sharedtask.py: 存在(更新于09-03 12:41)
  shared_mem.py: 存在(更新于09-03 12:44)
  config.py: 存在(更新于09-02 21:44)

- [09-03 13:42] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T13:42:09.121064
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 13:41)
  sharedtask.py: 存在(更新于09-03 12:41)
  shared_mem.py: 存在(更新于09-03 12:44)
  config.py: 存在(更新于09-02 21:44)

- [09-03 13:42] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T13:41:57.221542
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 13:41)
  sharedtask.py: 存在(更新于09-03 12:41)
  shared_mem.py: 存在(更新于09-03 12:44)
  config.py: 存在(更新于09-02 21:44)

- [09-03 13:41] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T13:41:45.616205
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 13:41)
  sharedtask.py: 存在(更新于09-03 12:41)
  shared_mem.py: 存在(更新于09-03 12:44)
  config.py: 存在(更新于09-02 21:44)

- [09-03 13:29] [开发助手自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': None}

- [09-03 12:49] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T12:49:38.686349
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 12:41)
  sharedtask.py: 存在(更新于09-03 12:41)
  shared_mem.py: 存在(更新于09-03 12:44)
  config.py: 存在(更新于09-02 21:44)

- [09-03 12:44] [云电脑 价格监控自检+心跳更新] 自检完成:
时间: 2026-09-03T12:44:31.225584
实例: 云电脑 价格监控
标签: 价格监控,公开信息调研,数据整理
Python: 3.12.11
工作目录: /sandboxdata/workspace/file/attivo-cloud
  daemon.py: 存在(更新于09-03 12:41)
  sharedtask.py: 存在(更新于09-03 12:41)
  shared_mem.py: 存在(更新于09-03 12:44)
  config.py: 存在(更新于09-02 21:44)

- [09-03 12:15] [云电脑 爬虫脚本自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': '/sandboxdata/workspace/file/attivo-collab/oemkb.db'}

- [09-03 10:40] [云电脑 爬虫脚本自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': '/sandboxdata/workspace/file/attivo-collab/oemkb.db'}

- [09-03 09:58] [Linux开发助手保活：cron @reboot + 5分钟watchdog] {'reusable_experience': None, 'pitfall_lessons': '容器无crontab写入权限，改用supervisord实现等效保活', 'reusable_code_or_script_name': None, 'output_data_file_path': None}

- [09-03 08:25] [云电脑 爬虫脚本自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': '/sandboxdata/workspace/file/attivo-collab/oemkb.db'}

- [09-03 01:10] [云电脑 爬虫脚本自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': '/sandboxdata/workspace/file/attivo-collab/oemkb.db'}

- [09-03 00:03] [云电脑 爬虫脚本自检+心跳更新] {'reusable_experience': None, 'pitfalls': None, 'reusable_code_script_name': ['daemon.py', 'sharedtask.py', 'shared_mem.py', 'config.py'], 'output_data_file_path': '/sandboxdata/workspace/file/attivo-collab/oemkb.db'}

- [09-02 21:30] [云电脑自检反馈：daemon保活+密钥+git冲突] 已处理：1.daemon保活已改5分钟计划任务(install_daemon_task.py) 2.oemkb.db已加入.gitignore并从仓库删除 3.sharedtask.py判空已修复且在auto_update列表 4.待用户操作：config.py密钥需同步到云电脑(config-export→config-import)


## 踩坑教训

- [09-03 15:51] [新建instances_shard.py心跳分片模块(解决三台并发覆盖)] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:24] [保活配置-Linux三层终极保活(脚本优化)] ERROR: 系统运维异常 name 'requests' is not defined

- [09-03 14:19] [保活配置-Linux三层终极保活(脚本优化)] ERROR: 系统运维异常 name 'requests' is not defined

- [09-03 14:18] [清理重复健康检查：合并health.py和healthcheck.py] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:17] [消除9个脚本中重复定义的common函数] ERROR: 无法从标题提取目标文件名: 消除9个脚本中重复定义的common函数

- [09-03 14:17] [改造scrape_yamamotor系列3个脚本继承crawler_base.CrawlerBase] ERROR: 无法从标题提取目标文件名: 改造scrape_yamamotor系列3个脚本继承crawler_base.CrawlerBase

- [09-03 14:17] [改造crawl_boatsnet.py和scrape_shop.py继承crawler_base.CrawlerBase] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:17] [优化ai_router.py与ds_harness.py集成：统一AI调用入口] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:16] [统一Odoo操作封装：审计crm_ops.py/create_expense.py/sync_leads.py重复代码] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:16] [改造crawl_crossref.py继承crawler_base.CrawlerBase] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:16] [改造crawl_bg.py + crawl_full.py继承crawler_base] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:15] [改造crawl_diagrams.py继承crawler_base.CrawlerBase] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:15] [改造crawl_suzuki_eparts.py继承crawler_base.CrawlerBase] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes

- [09-03 14:15] [Linux开发助手保活：加cron @reboot] ERROR: 无法从标题提取目标文件名: Linux开发助手保活：加cron @reboot

- [09-03 14:14] [保活配置-Linux三层终极保活(脚本优化)] ERROR: 系统运维异常 name 'requests' is not defined

- [09-03 13:42] [保活配置-Linux三层终极保活(脚本优化)] ERROR: 系统运维异常 name 'requests' is not defined

- [09-03 13:33] [megazip剩余45个section零件抓取收尾] ERROR: 爬虫0成功(DONE: 0/45 ok, 45 errors)

- [09-03 12:54] [改造crawl_yamaha_pdfs.py继承crawler_base.CrawlerBase] ERROR: DeepSeek生成失败 ERROR(exit 1): File "/opt/python3.12/bin/python3", line 1
    ELF
SyntaxError: source code cannot contain null bytes
