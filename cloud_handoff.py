# -*- coding: utf-8 -*-
"""
按需协作派发入口（替代常驻 daemon / 保活 / 心跳）。
云电脑=ByteFaaS 容器，不活跃必被回收，无远程唤醒 API，高频保活纯烧 token。
新规矩：本地主控把任务 push 进共享任务表 -> 用户开云电脑时贴一条一次性指令 ->
云电脑领完积压任务、回写结果、同步经验后结束，不自举 daemon、不心跳、不装保活。

用法:
  python cloud_handoff.py list                      # 看待处理积压
  python cloud_handoff.py wake "实例名"              # 只生成唤醒指令(任务已在队列)
  python cloud_handoff.py send "实例名" "类型" "标题" "内容" ["优先级"]
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sharedtask as ST

# 实例 -> (擅长标签, 云端目录)
INSTANCES = {
    "开发助手": ("代码开发/重构/bug修复/脚本优化", "~/attivo-collab"),
    "云电脑 价格监控": ("价格监控/公开信息调研/数据整理", "~/attivo-cloud"),
    "云电脑 爬虫脚本": ("爬虫/数据整理/配件查询", "~/attivo-collab"),
}

WAKE_TMPL = (
    "按需开工，跑完即走，【不要】启动 daemon/watchdog/心跳/保活（容器回收保不住，白烧token）：\n"
    "cd {dir} && git pull -q; python3 sharedtask.py pending\n"
    "# ↑认领指派给「{name}」(标签:{tags})的待处理任务: python3 sharedtask.py claim <rid> \"{name}\"\n"
    "# 逐个完成后: python3 sharedtask.py complete <rid> \"结果\" ; 卡住用 ask <rid> 问题\n"
    "# 全部做完: ax memory push 标题 运维 经验摘要 架构  然后直接结束，无需常驻"
)


def wake(name):
    if name not in INSTANCES:
        print(f"未知实例 {name}，可选: {list(INSTANCES)}"); return
    tags, dir_ = INSTANCES[name]
    print("=" * 60)
    print(f"复制下面整段发给云电脑「{name}」：")
    print("=" * 60)
    print(WAKE_TMPL.format(dir=dir_, name=name, tags=tags))
    print("=" * 60)


def send(name, typ, title, content, prio="中"):
    if name not in INSTANCES:
        print(f"未知实例 {name}，可选: {list(INSTANCES)}"); return
    ST.push(typ, title, content, "", name, prio)
    print(f"[已入队] {title} -> {name} ({prio})")
    wake(name)


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    act = sys.argv[1]
    if act == "list":
        ST.list_by_status("待处理")
    elif act == "wake":
        wake(sys.argv[2])
    elif act == "send":
        send(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5],
             sys.argv[6] if len(sys.argv) > 6 else "中")
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
