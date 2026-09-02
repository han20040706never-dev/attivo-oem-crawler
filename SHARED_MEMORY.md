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
*最后更新：2026-09-02 21:30*


## 云电脑使用说明

- [09-02 09:48] 云电脑豆包启动时先执行: ax memory pull 10 和 ax memory sync-github；跑完任务后: ax memory push 标题 类型 内容 标签，大数据文件传GitHub仓，摘要push到SHARED_MEMORY.md；禁止写入客户数据/底价/密钥/录音原件


## 已完成任务

- [09-02 21:30] [云电脑自检反馈：daemon保活+密钥+git冲突] 已处理：1.daemon保活已改5分钟计划任务(install_daemon_task.py) 2.oemkb.db已加入.gitignore并从仓库删除 3.sharedtask.py判空已修复且在auto_update列表 4.待用户操作：config.py密钥需同步到云电脑(config-export→config-import)
