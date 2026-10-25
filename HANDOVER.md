# 交接说明

> 新会话请把工作区设为 `D:\A\Harness\ime-focus`。读这一份就够了，不用翻聊天记录。

## 现状一句话

能用的 0.1 原型：托盘常驻 + 设置窗口，焦点进密码框自动切美式键盘、离开切回。已推送到 GitHub 公开仓库，CI 绿，20 个测试全过。**还没在真实浏览器里验证过。**

## 仓库

- `https://github.com/young-ski/ime-focus`，public，MIT
- 默认分支 `main`，最新提交 `cf1892e`
- 本机 SSH key 已配好（`~/.ssh/config` 把 github.com 转到 ssh.github.com:443），`gh` 已登录 `young-ski`，scope `repo` + `workflow`
- 注意：**HTTPS 到 github.com 不通**，远端只能用 SSH；`gh` 装在 `C:\Program Files\GitHub CLI\gh.exe`，PATH 里可能没有，用全路径

## 目录

```
src/imefocus/
  rules.py    判定逻辑，纯函数，状态机只有 idle/en
  win.py      UIA 读焦点 + 切键盘布局（ctypes）
  engine.py   tick() 轮询，CLI 和 GUI 共用
  gui.py      tkinter 窗口 + 事件日志 + 配置保存 + 自启
  tray.py     ctypes 自绘 Shell_NotifyIcon
  cli.py      run / doctor / gui 三个子命令
tests/        20 条，rules 全覆盖，engine/win/tray 有针对性用例
dev/          排障脚手架（见下），产物写 dev/out/，已 gitignore
docs/         README 用的截图
```

## 前提

- Windows 10/11 + Python 3.10+
- **系统里必须装了「美式键盘」（00000409）**，它靠切布局工作
- `.venv` 已经建好（`pip install -e . pytest ruff`），直接 `.venv\Scripts\python.exe` 用

## 怎么跑

```powershell
.venv\Scripts\python.exe -m imefocus.cli doctor      # 环境自检，先跑这个
.venv\Scripts\python.exe -m imefocus.cli gui         # 开界面（正式用 pythonw）
.venv\Scripts\python.exe -m imefocus.cli run --dry-run -v   # 纯命令行试跑
.venv\Scripts\pythonw.exe -m imefocus.cli gui        # 不带控制台窗口
```

测试与风格：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

## dev/ 脚手架

造一个真密码框，用来验证检测链路，不用手点浏览器。

| 脚本 | 干什么 |
|---|---|
| `pwnd.py` | 起一个带消息泵的密码 EDIT 窗口，前台 40 秒 |
| `pwprobe.py` | 造窗口 + 抢前台 + 连续采样 `win.focused()`，结果写 `out/pwprobe.out` |
| `fmain.py` | 主线程里直接调一次 `focused()`，最快的一条 |
| `elemprobe.py` | 按窗口句柄取 UIA 元素，验证 `IsPassword` 本身（不依赖前台） |
| `vercheck.py` | 报告当前焦点元素的类名/类型/IsPassword |
| `pw.html` / `edgeopen.py` | 浏览器版（`--force-renderer-accessibility` 开新 profile） |
| `raise.py` | 按标题把窗口提到前台 |

典型用法：先跑 `fmain.py`，它 3 秒内会把 `pw=True` 写进 `out/fmain.out`；再开 GUI + `pwnd.py` 看界面有没有出现 `to_en` 行。

### 三个必须知道的前提

1. **用 `pythonw.exe`，别用 `python.exe`**。控制台窗口会抢走前台焦点，探针看到的永远是自己。
2. **测试窗口必须有消息泵**（`pwnd.py` 里的 `PeekMessage` 循环）。只 `sleep` 的窗口会被系统收回前台，`GetFocusedElement` 也就跟着飘。
3. **抢前台别靠硬编码坐标**：本机 DPI 是缩放的，进程间坐标系不一致。用 `AllowSetForegroundWindow(-1)` + `AttachThreadInput`，必要时按 `GetWindowRect` 算点击点。

在 DSH 会话里直接跑这些脚本是可以的，跨进程 UIA 正常（本机实测 `pw=1`）。

曾经误判成「会话内 UIA 会降级成只看得见自己」，其实是上面第 2 条：没泵的窗口前台被收回后，焦点一直停在自家窗口上。

## 已验证

- 20 个测试通过；ruff 干净；CI 在 windows-latest 绿
- 端到端：`pwnd.py` 置前台后，界面日志出现 `[时间] pythonw.exe Edit -> to_en (password field)`，离开后出现 `restore`（截图见 `docs/window.png`）
- 句柄级：`elemprobe.py` 对一个 `ES_PASSWORD` 编辑框报 `type=50004 cls='Edit' pw=1`
- 托盘：启停、换图标有单测；通知区图标**肉眼看没确认过**（本机任务栏自动隐藏）

## 没验证 / 已知缺陷

- **真实浏览器一次没测通**。Edge 的 Chromium 树在这里只暴露 4 个节点，`GetFocusedElement` 拿不到输入框，加 `--force-renderer-accessibility` 也一样。优先验证这条，B 站/邮箱登录页都行。
- UWP、部分 Electron 应用的 UIA 树不完整
- 管理员权限窗口（任务管理器等）看不到，需以管理员身份启动
- 只切「键盘布局」，不改输入法内部中英模式；只装微软拼音的用户没效果
- 全屏游戏里每 120ms 一次 UIA 有开销，大可以加进 `ignore`
- 关窗口 = 退进程；托盘没有「最小化时提示」

## 踩过的坑（别重复）

| 现象 | 原因 |
|---|---|
| 建窗口时 access violation，但程序还能跑 | `kernel32.GetModuleHandleW` 没声明 `restype`，64 位 HMODULE 被截断成 int |
| `OSError: 无法在设置线程模式后更改` | `comtypes` 首次 import 会做 STA 初始化，和先设的 MTA 冲突。要在模块顶层 import comtypes，再在目标线程 `CoInitializeEx(MTA)` |
| UIA 调用永久卡死 | 从工作线程调 UIA，自家窗口属于主线程 STA，被 marshal 回主线程而主线程在 `sleep`。现在没有后台线程，`tick()` 由 `after()` 驱动 |
| `IsPassword` 恒为 false | 原生编辑框的焦点落在 `InputSiteWindowClass` 包装层，真控件在祖先上（`win._real_control`） |
| 只有一个属性读失败，整条焦点信息全丢 | 原来把多个属性写在同一个 `replace()` 里；现在逐个读（`win._read`），失败给默认值 |
| pystray 起不来 `WinError 5` | `ChangeWindowMessageFilterEx` 被拒，异常在建窗口阶段带走整个托盘线程。已弃用，改自绘 |
| `CreateIconFromResourceEx` 返回 NULL | 它要图片数据本身，不能喂整个 ICO 文件（含 22 字节头） |
| 计划任务里 `SetForegroundWindow` 一直失败 | 后台进程没有前台资格，要 `AllowSetForegroundWindow(-1)` + `AttachThreadInput`，或者干脆模拟一次点击；DPI 虚拟化还会让硬编码坐标偏掉，要按 `GetWindowRect` 算 |
| 错误日志里什么都看不到 | 早期异常事件被当 noop 过滤掉了，现在强制落日志 |

## 下一步（按优先级）

1. 真实浏览器验证；不行就退到「按 UIA 树属性兜底」——比如沿 `Document` 找 `Edit`，或读窗口标题里的「密码」
2. 用 TSF `ITfInputProcessorProfileMgr::ActivateProfile` 替代布局切换，解决「只有微软拼音」
3. 按进程记忆偏好，替代现在全局一个状态
4. PyInstaller 打成单文件 exe，去掉 Python 依赖
5. 开机自启现在是 `schtasks /create`，换成注册表 Run 键更轻

## 发布注意

- 提交前跑 `pytest` + `ruff`，两者都必须干净
- 校内的东西（IP、MAC、账号、`user_account`）一个都不能进代码
- README 改动记得同步截图；`docs/window.png` 是 616×739 的界面裁剪
- 许可证保持 MIT，别换 GPL
- 中文提交信息是惯例，首行说清做了什么
