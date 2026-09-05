# 脚本能力地图（自动生成，勿手改）
> 生成时间 2026-09-05 16:12 · 生成器 `python build_script_index.py`
> **新任务铁律**：先在本地图找现成脚本/函数 → 再 `ax route` → 都没有才写新脚本；新脚本必须有模块 docstring，写完重跑本生成器入库。
> 共 95 个脚本，分 11 类。


## CRM/Odoo 操作（16）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `append_to_odoo` | 安全追加HTML到Odoo备注（绝不覆盖原文） | main |
| `b2b_ledger` | B端作战台账:类型 + 试用复购状态 + 区域景气 + 信任阶段(豆包读拜访记录人工标注) + 下次动作 | prov_of, ctype, first_main_cat |
| `cleanup_legacy_blocks` | 清理/格式化联系人comment里的历史同步块（一次性治理+可复用）。 | fmt_body, new_title, main |
| `corrections` | 专有名词纠错表（共享模块）。 | apply_corrections |
| `crm_ops` | CRM批量操作工具 - 零token省额度 | get_client, find_state_id, find_tag_id, find_source_id, cmd_newlead, cmd_fixleads, cmd_note, cmd_pricelist |
| `customer_score` | customer_score.py — 客户价值分(value_score)与行动分(action_score)计算 | Customer, Lead, normalize_text, classify_category, category_cycle, region_score, compute_cycle, compute_value_score |
| `customer_summary` | 客户速查 — 一句话查客户全貌 | strip_html, main |
| `fill_phone` | （无docstring，待补） |  |
| `fix_typos` | 专有名词纠错批量订正：遍历陈国标的商机/线索备注，替换错误写法为正确写法。 | main |
| `match_opp` | 本地商机匹配 - 根据录音文件名自动匹配Odoo联系人/商机 | extract_names_from_filename, match_opportunity |
| `nophone` | 列出陈国标的活跃线索/商机中缺手机号的记录（含联系人侧号码判断）。 | has |
| `odoo_query` | Odoo紧凑查询 — 最少token输出 | main |
| `region` | 中国行政区划解析 - 基于 pca-code.json | parse_region, parse_region_full, get_all_cities |
| `sop_followup` | sop_followup.py  SOP复购跟进清单（本地聚合Odoo数据 + customer_score双分模型） | d, load, order_skus, group_by_partner, pname, pcity, build_scored, fmt_customer |
| `sync_leads` | Odoo商机备注 → 联系人备注 增量同步（JSON-RPC版） | strip_html, sanitize_lead_html, jsonrpc_search_read, jsonrpc_read, make_sync_block, update_partner_comment, main |
| `visit_pipeline` | 录音拜访一键流水线（省token版） | asr, safe_append, check |

## 销售分析/带货推荐（8）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `analyze_sales` | 本地聚合分析销售数据，输出紧凑结论 | infer_region, infer_category |
| `build_dashboard` | 生成自包含HTML可视化看板，零token查看 |  |
| `build_loadout` | 外勤装车综合建议：以桌面最新需求清单为底，叠加中国仓现货/全员销售热度/覆盖广度， | avail_of, advise, style_header |
| `build_profiles` | 客户行为态度档案 customer_profile.json 生成器(v2 对齐销售SOP)。 | norm_trust, tier_of, ctype, consume_kind, cross_of, brand_of, sop_stage |
| `gen_evidence` | （无docstring，待补） |  |
| `gen_lookup` | 机型代际查询 & 货盘代际结构扫描。 | build_index, lookup, cmd_lookup, cmd_scan |
| `pull_sales` | 一次性拉取Odoo全量销售数据，本地聚合，输出紧凑JSON给可视化用 |  |
| `recommend_goods` | 外勤带货综合推荐：需求清单 ∪ 全员销售小件 ∪ 油封OEM主数据，结合Odoo在手，只四冲。 | norm, repn, brand_of, cov_count, bigcat, is_filter, infer_cat, style_sheet |

## 配件/库存/OEM知识库（17）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `build_seal_rec` | 油封/O圈/密封套件 带货推荐 v2：只看中国仓有货；没卖过但适配60-300马力也推荐 | fix_pos, norm, parse_hp, bk, stock, grade, head, body |
| `cn_stock` | Odoo 中国仓实时库存轻量查询模块。 | norm, live_qty, load_cache, qty_with_verify, main |
| `crawl_crossref` | megazip.net 配件互换款爬虫（纯requests+正则，零额外依赖） | load_json, save_json, search_megazip, extract_supersessions, lookup_part, main |
| `crawl_oem_tree` | crawl_oem_tree.py — megazip 船外机机型树爬虫（Yamaha/Suzuki） | OEMTreeCrawler, main |
| `crawl_suzuki_eparts` | 铃木原厂eParts爬虫 - API方式，零token，断点续爬 | db, api_get, get_vehicle_id, main |
| `oem_query` | oem_query.py — 零token三源统一配件查询 | db_for, expand, hp_variants, query_megazip, load_json, query_attivox, query_yamamotor, main |
| `parts_dict` | 船外机配件 英->中 持久词典 + OCR归一化。累积维护，新真术语加进 TRANS。 | normalize, zh |
| `parts_extra` | 库存表扩展词典（在 parts_dict 基础181条之上累积；新领域术语加这里） | norm2, lookup |
| `parts_kb` | 船外机配件业务知识库。 | norm, fix_pos, brush_note, is_old, categorize |
| `parts_translate` | parts_translate.py —— 船外机配件英文清单(longshot_ocr产物) -> 中英对照Excel | main |
| `scrape_shop` | attivox.com/shop 产品库工具 — 零token查配件 | parse_page, parse_detail, scrape_list, scrape_details, search, search_fit, list_categories |
| `scrape_yamamotor` | yamamotor.com.tw 配件目录爬虫 | decode_ptype |
| `scrape_yamamotor_full` | yamamotor.com.tw 完整配件目录爬虫 - 增量保存+重试 | make_session, fetch, get_model_ids, parse_products, get_max_page, load_existing, save |
| `scrape_yamamotor_specs` | yamamotor 补充爬虫 - 补 stroke(冲程) + HP(马力) 到现有配件 | fetch, parse_product_cards, main |
| `seal_guide` | seal_guide.py  船外机油封/O圈/齿轮箱密封套件 外勤带货推荐 | mega_to_compact, norm, is_pure_seal, newentry, build_yamaha, build_suzuki, build_sales, build_stock |
| `stock_check_list` | 任意 Excel 清单一键核“中国仓实时库存” —— 高频复用工具。 | main |
| `yamamotor_query` | yamamotor本地配件查询 - 零token | load_data, search |

## OEM 爬虫（9）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `crawl_bg` | crawl_bg.py — OEM爬虫多profile后台启动器（AI全程只发一条命令，不盯梢） | alive, prof, cmd_start, cmd_status, cmd_stop |
| `crawl_boatsnet` | crawl_boatsnet.py — boats.net 船外机零件爬虫（playwright绕过Cloudflare） | db, is_done, mark, save_parts, extract_path_info, crawl |
| `crawl_brand` | crawl_brand.py — 单品牌无人值守爬虫（可与主进程并行，写独立db文件） | log, write_stats |
| `crawl_diagrams` | Crawl ATTIVOX product pages for diagrams and part numbers. | load_json, save_json, get_session, fetch_with_retry, extract_json_scripts, extract_product_images, extract_diagram_images, extract_compatibility_data |
| `crawl_full` | crawl_full.py — 无人值守总控：Yamaha+Suzuki 全马力，断点续爬。 | log, write_stats, main |
| `crawl_yamaha_pdfs` | 雅马哈原厂PDF零件目录批量下载解析 - 零token | db, download, extract_parts, main |
| `crawler_base` | crawler_base.py — 爬虫统一基类 v1.0 | CrawlerBase |
| `probe_megazip` | 深入探测yamamotor和megazip的配件目录结构 |  |
| `probe_sites` | 探测yamamotor.com.tw和megazip结构 |  |

## AI 路由/DeepSeek/反思（11）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `ai_router` | 统一AI路由 - 多provider自动切换，免费优先，零豆包token | token_stats, translate, chat, summarize, classify, extract, stats, code_helper |
| `code_quality_gate` | code_quality_gate.py — 代码质量门禁 | check_syntax, check_secrets, check_danger, check_imports, verify_file, main |
| `ds_harness` | DeepSeek Harness - 多轮迭代编码助手 | extract_code, run_code, build_context, main |
| `extract_sop_notes` | 从 res.partner.comment + crm.lead.description 抽取SOP字段,看哪些'待问'其实备注里已有。 | strip |
| `fill_from_notes` | 豆包亲自据Odoo备注证据卡归纳,回填customer_profile.json(只填证据明确项,不臆测)。 |  |
| `learn_taxonomy` | 从attivox官网提取完整分类体系和配件术语 |  |
| `multi_ai` | 多AI辅助模块 - 向后兼容入口，实际使用ai_router统一路由 |  |
| `profile_tool` | 客户档案查询(对齐SOP, v2)。 | gaps_of, stat, lst, show, gaps, stage |
| `reflect` | reflect.py — 自动反思检查器（文件层+行为层） | add, check_temp_files, check_hardcoded, check_large_files, check_behavior, check_iron_rules, check_reuse, main |
| `smart` | smart.py - 省token智能中枢 | decide, ds_edit, selftest, main |
| `tx` | 豆包省token工具箱 - 把烧token的操作封装成脚本调用 | cmd_ai, cmd_code, cmd_fetch, cmd_grep, cmd_run, cmd_odoo |

## 云协作/共享任务/健康（11）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `auto_dispatch` | 智能任务派发器 v1.2（dsh审查修复版） | classify, is_confidential, recommend_instance, dispatch, main |
| `check_done` | check_done.py — 本地主动轮询：自动回收云电脑已完成的任务 | load_notifications, save_notifications, add_notification, load_cache, save_cache, main |
| `cloud_ax` | cloud_ax.py — 云电脑豆包专用精简入口 | check_update, run, cmd_memory, cmd_task, cmd_think, cmd_ai, cmd_bootstrap, cmd_version |
| `cloud_handoff` | 按需协作派发入口（替代常驻 daemon / 保活 / 心跳）。 | wake, send, main |
| `common` | common.py — 公共函数模块，消除重复代码 | db, load_json, save_json, safe_request, cli, cell, log, run |
| `daemon` | 协作系统自动巡检daemon v3.0（dsh agent深度审查后修复版） | acquire_cycle_lock, release_cycle_lock, auto_update, load_instance_stats, task_matches_tags, get_pending_tasks, should_auto_execute, auto_execute_crawl |
| `gh_push` | 通用 GitHub 内容推送(无git环境): python gh_push.py 文件1 [文件2 ...] | push |
| `health` | 一键系统健康检查：输出本地daemon、云电脑实例、任务、零件库、token、通知全貌 | run |
| `healthcheck` | healthcheck.py — 兼容入口，深度自检已合并进 health.py（2026-09-03） |  |
| `shared_mem` | shared_mem.py — 本地↔云电脑共享记忆同步 | push, search, relevant, pull, sync_github, sync, bootstrap, push_github |
| `sharedtask` | sharedtask.py —— 豆包Agent共享任务库（飞书多维表格）命令行封装，省token。 | list_by_status, push, set_status, chat, view, complete, claim, rate |

## 报销/费用（2）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `create_expense` | Odoo费用报销自动创建（增强版） | extract_text_from_pdf, detect_invoice_type, extract_toll_info, extract_vat_info, get_ocr, ocr_payment_screenshot, build_description, build_expense_name |
| `toll` | toll.py —— 通行费报销一条龙（一条命令，本地OCR零token，不重复造轮子） | parse_mini_detail, classify_image, main |

## 录音/转写（3）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `asr_rolemap` | asr_rolemap.py — 录音转写后、豆包总结前的【说话人角色标定】工具（零外部AI，省token） | parse, score, main |
| `process_recordings` | 录音处理一条龙：mediakit转写(并行) → 匹配Odoo商机 → 输出清单 | submit_asr, poll_asr, subtitles_to_text, process_one, main |
| `transcribe` | 录音转写工具 - mediakit-cli (字节自研ASR) | transcribe_file, main |

## 微信联系人采集（5）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `wx_collect` | 微信群聊消息收集+总结（零封号风险） | collect, summarize |
| `wx_dedup` | wx_dedup.py —— 微信名单 ↔ Odoo 一次做全查重（根治反复漏判/误判） | clean_line, kw_variants, search_both, score, classify_one, main |
| `wx_group_scan` | wx_group_scan.py - 微信群消息扫描与分析工具 | ensure_dirs, get_timestamp, find_wechat_window, restore_wechat_window, connect_wechat, get_current_chat, load_messages, save_messages |
| `wx_ocr` | 微信群聊消息OCR提取（零封号风险） | find_and_restore_wechat, get_msg_area, scroll, extract, analyze |
| `wx_ocr_fast` | wx_ocr_fast.py - 快速提取微信PC 4.x群聊消息（纯本地OCR） | find_wx_window, restore_window, capture_window, capture_screen, crop_message_area, scroll_wheel, scroll_to_top, ocr_image |

## Excel/文件/通用工具（7）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `build_script_index` | 扫描本目录所有 .py，自动生成《脚本能力地图 SCRIPT_INDEX.md》。 | classify, scan, main |
| `card_ocr` | 微信名片 / 视频号主页 截图 -> 本地OCR提取手机号（零token、零风险，不碰微信客户端） | find_phones, cluster_rows, ocr_image, main |
| `longshot_ocr` | longshot_ocr.py —— 超长截图本地OCR（自动纵向切片 + 按y归行 + 重叠去重） | engine, ocr_long, main |
| `patch_file` | 通用“定点补丁”工具 —— 替代每次手写 str.replace 驱动，规避 PowerShell 命令行引号 / f-string 花括号转义地狱。 | process_one_file, main |
| `search_github_code` | GitHub代码搜索：船外机配件数据 |  |
| `search_github_outboard` | GitHub搜索船外机配件相关项目 |  |
| `xlsx2pdf` | xlsx -> PDF（PyMuPDF绘制表格，不依赖Excel/WPS，绝不卡COM） | wlen, new_page, draw_header |

## 其他（6）
| 脚本 | 用途 | 主要入口/函数 |
|---|---|---|
| `_gen2` | DeepSeek 生成 patch_file.py / stock_check_list.py 两个可复用工具, 落盘+编译 |  |
| `_test2` | （无docstring，待补） | ck |
| `_test3` | （无docstring，待补） | ck |
| `add_demand` | 中国大陆需求清单一键填写工具 | check_part, main |
| `ax` | 统一工作流入口 - 所有操作走这里，强制省token模式 | cmd_query, cmd_part, cmd_customer, cmd_sales, cmd_ai, cmd_think, cmd_summarize, cmd_fetch |
| `parse_suzuki_pdf` | 铃木原厂PDF零件目录解析 - 提取零件号+名称+适用机型 | extract_parts |
