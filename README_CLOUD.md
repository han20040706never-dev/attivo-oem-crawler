# 云电脑运行说明（给豆包云电脑看）

目标：在云电脑上**无人值守**抓取 megazip 的 Yamaha/Suzuki 船外机齿轮箱+曲轴配件数据，断点续爬，关本机不影响。

## 文件
- `crawl_oem_tree.py`：核心爬虫（SQLite 存 `oemkb.db`，已抓的不重复）
- `crawl_full.py`：总控，依次跑 Yamaha、Suzuki 全马力
- `oemkb.db`：当前进度（可直接接着跑，也可删除重抓）

## 运行步骤（Windows 云电脑，PowerShell）
1. 新建目录 `C:\oem-crawler`，把本仓库这 3 个文件下载进去
   （或 `git clone 本仓库地址`；没有 git 就用 raw 链接逐个下载）。
2. 确认有 Python：`python --version`；没有就装一个并勾选 pip，然后
   `pip install requests`（仅依赖 requests，装不了就 `pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple`）。
3. 进目录后台运行（关掉远程窗口也继续）：
   ```
   cd C:\oem-crawler
   Start-Process -WindowStyle Hidden python -ArgumentList "crawl_full.py" -RedirectStandardOutput run.log -RedirectStandardError err.log
   ```
4. 看进度：`python crawl_oem_tree.py stats`
   或看 `run.log`。断点续爬，中断后重复第 3 步即可接着抓。

## 注意
- megazip **直连即可，不需要代理**；脚本已内置代理失败自动回退直连。
- 只抓业务核心分区：Lower casing & drive（齿轮组/驱动轴/桨轴）、Crankshaft & Piston（曲轴）。
- 礼貌延时 0.7s，不要调小；不要并发多开，避免被封。
- 全部抓完后，把最终的 `oemkb.db` 传回（上传回本仓库或发回本地都行）。
