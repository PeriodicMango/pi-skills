# desktop-view

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)
![Windows](https://img.shields.io/badge/Windows-PowerShell-5391FE)

[English](README.md) | 简体中文

一个 [pi](https://github.com/earendil-works/pi) skill，让 agent 能**通过 ssh 看见 Windows 桌面**——
列出打开的窗口，或抓取某个窗口的像素——而不必让你去截图。

```
$ winshot.sh list
6753740|CASCADIA_HOSTING_WINDOW_CLASS|Terminal|3702,210,682,666
7998136|ApplicationFrameWindow|Settings|2552,-8,1936,1048
5117558|RainmeterMeterWindow|...\Skins\Widget\Widget.ini|2969,0,739,1003

$ winshot.sh shot "Widget.ini" widget.png
MATCHCOUNT|1
CHOSEN|5117558|...\Skins\Widget\Widget.ini
PRINTWINDOW|True
SIZE|739x1003|dst=0,0
wrote widget.png (20819 bytes)
```

## 为什么需要它

在 GUI 上工作的 agent 没有眼睛。通常的绕法是让人类截图并描述，既慢又有损："看起来有点歪"不是一个数字，
而且 agent 无法自己验收。

只要那台 Windows 机器能被 ssh 到，这个绕法就不必要了。两条命令替代它，agent 可以自己迭代到像素级正确。

## 安装

克隆进你的 pi skills 目录：

```bash
./install.sh desktop-view      # 在 pi-skills 仓库根目录执行
```

手工安装就是把本目录复制到 `~/.pi/agent/skills/desktop-view`。

skill 目录名必须与 `SKILL.md` 里的 `name` 一致（`desktop-view`）。pi 在启动时扫描 skills 目录，
所以需要**新开一个会话**才会被提供；也可以用 `/skill:desktop-view` 强制调用。

## 配置

```bash
mkdir -p ~/.config/pi-desktop-view
cp config.example ~/.config/pi-desktop-view/config
$EDITOR ~/.config/pi-desktop-view/config
```

两个值必填：

| 键 | 含义 |
|---|---|
| `WIN_SSH_TARGET` | Windows 主机的 ssh 目标——`me@host` 或 `~/.ssh/config` 里的别名 |
| `WIN_TMP` | Windows 侧的临时目录，写成 `C:/Users/you/AppData/Local/Temp` 或 `/mnt/c/Users/you/AppData/Local/Temp` |

驱动会自动推导出你没写的那种形式，并且在对端看不到该路径时直接拒绝执行——所以写错会立刻得到明确报错，
而不是截图截到一半才失败。

可选键（`WIN_SSH_KEY`、`WIN_POWERSHELL`、`WIN_TMP_SHELL`、`WIN_SSH_OPTS`）在 `config.example` 里有说明。

## 对端要求

- 能 ssh 进一个 **POSIX 风格、且其文件系统暴露了 Windows 盘符的 shell**。WSL 是验证过的路径；
  Git Bash 或 Cygwin 应该也可以。
- **PowerShell 5.1 或更新**，能从那个 shell 通过 `WIN_POWERSHELL` 调到（默认是 WSL 里
  `powershell.exe` 的路径）。
- **运行 agent 的那台机器**不需要挂载 Windows 文件系统——所有传输都走 ssh，所以 agent 完全可以住在另一台主机上。

如果你 ssh 进的是**原生** Windows OpenSSH 服务（登录 shell 是 cmd.exe 或 PowerShell、没有 `/mnt/c`），
驱动里的 `cat`/`md5sum` 调用不会工作。那种环境需要把传输改写成经 PowerShell 走 base64；
目前没有实现，欢迎提交。

## 用法

```
winshot.sh list                                     # 打开的窗口，纯文本
winshot.sh screen                                   # 显示器信息 + 查询进程的 DPI 感知级别
winshot.sh shot <title-substring> [out.png] [pad]   # 抓取一个窗口
```

退出码：`0` 正常，`1` 配置/用法问题，`2` 对端抓取失败。

在比较来自两个不同程序的坐标之前，先跑一次 `screen`。DPI 不感知的进程看到的是虚拟化坐标空间，
per-monitor 感知的进程看到的是物理像素，所以同一批窗口在不同提问者那里会得到不同的数字。

## 工作原理，以及唯一重要的那个决定

`win_shot.ps1` 用 `EnumWindows` + `GetWindowRect` 枚举顶层窗口，然后用下面的方式抓取：

```csharp
PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT /* = 2 */)
```

**不是 `Graphics.CopyFromScreen`**——那是显而易见的选择，也是错的那个：它抓的是合成后的屏幕，
所以返回的是压在该窗口之上的东西。一次本想展示某个应用的截图，会带回来另一个应用——包括用户当时
恰好打开的私密内容。`PrintWindow` 是向目标窗口本身索取，所以遮挡和放在屏幕外都无所谓。

DWM 合成的窗口必须带 `PW_RENDERFULLCONTENT`；不带的话 `PrintWindow` 返回一张空白位图。

实际后果：你拿到的是窗口自己的像素，所以半透明或分层窗口会与黑色合成，而不是与它背后的桌面合成。
这些截图可以信几何和文字，不要用它判断叠在壁纸上的观感。

## 限制

- 抓不到菜单弹出、工具提示和右键菜单——它们是独立的顶层窗口，先在 `list` 里按各自的标题或类名找到它们，
  再单独抓。
- 桌面/壁纸不是窗口，这种方式抓不到。
- 最小化的窗口可能返回空白。
- `-Pad` 会从屏幕上再加一圈边，那一圈里包含当时压在那里的任何东西，包括其他窗口。所以默认关闭。

## 隐私

这会读取一个真实的桌面。`list` 暴露窗口标题；`shot` 暴露一个窗口的像素；`-Pad` 和任何整屏抓取会暴露周边。
skill 要求 agent 把这三者当成三个不同级别的授权，默认只做窗口内抓取，并且把超出预期的内容报告出来并丢弃。

## License

MIT —— 见 [LICENSE](LICENSE)。
