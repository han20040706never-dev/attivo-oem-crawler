# -*- coding: utf-8 -*-
"""
注册Windows计划任务，每5分钟触发一次daemon.py --once
替代常驻进程，解决云沙箱回收导致daemon死亡的问题
用法：python install_daemon_task.py --instance "云电脑 爬虫脚本" --tags "爬虫,数据整理,配件查询"
"""
import sys, io, os, subprocess, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--instance", required=True, help="实例名称")
    p.add_argument("--tags", required=True, help="专长标签，逗号分隔")
    p.add_argument("--interval", type=int, default=5, help="触发间隔分钟，默认5")
    a = p.parse_args()

    task_name = f"AttivoDaemon_{a.instance.replace(' ', '_')}"
    script_path = os.path.join(PROJECT, "daemon.py")
    cmd = f'"{PY}" "{script_path}" --instance "{a.instance}" --tags "{a.tags}" --once'

    # 先删除旧任务
    subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"],
                   capture_output=True, text=True)

    # 创建计划任务：每5分钟触发一次，持续无限期
    xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Attivo协作系统daemon - {a.instance}</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT{a.interval}M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{PY}</Command>
      <Arguments>"{script_path}" --instance "{a.instance}" --tags "{a.tags}" --once</Arguments>
      <WorkingDirectory>{PROJECT}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''

    xml_path = os.path.join(PROJECT, "_daemon_task.xml")
    with open(xml_path, 'w', encoding='utf-16') as f:
        f.write(xml)

    r = subprocess.run(["schtasks", "/Create", "/TN", task_name, "/XML", xml_path, "/F"],
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(f"ERROR: {r.stderr}")
        return

    # 清理临时xml
    if os.path.exists(xml_path):
        os.remove(xml_path)

    # 验证
    r2 = subprocess.run(["schtasks", "/Query", "/TN", task_name, "/FO", "LIST"],
                        capture_output=True, text=True)
    print(r2.stdout)
    print(f"\n✅ 计划任务已注册：{task_name}")
    print(f"   每{a.interval}分钟触发一次 daemon.py --once")
    print(f"   实例：{a.instance}")
    print(f"   标签：{a.tags}")
    print(f"   沙箱回收不影响（系统级计划任务）")

if __name__ == "__main__":
    main()
