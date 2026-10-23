# pi-skills

[English](README.md) | 简体中文

给 [pi](https://github.com/earendil-works/pi)（pi-coding-agent / pi-web）用的 agent skill 集合，
放进 `~/.pi/agent/skills/` 即可使用。

一个 skill 就是一个含 `SKILL.md` 的目录。agent 按需读取它：`description` 是唯一预先进入上下文的部分，
正文只在任务匹配时才加载。没有构建步骤，也没有运行时依赖。

## 安装

```bash
git clone https://github.com/PeriodicMango/pi-skills.git
cd pi-skills

./install.sh --list                       # 看看有哪些
./install.sh pi-session-move              # 装一个
./install.sh desktop-view rainmeter-skin-layout   # 一次装多个
./install.sh --all                        # 全装
./install.sh pi-session-move --link       # 用符号链接代替复制（改仓库即生效）
```

`--dest DIR` 可以装到 `~/.pi/agent/skills/` 以外的地方。默认用**复制**模式，这样仓库被挪走或删掉都不影响已装的副本；
`--link` 建符号链接，适合边改边试。

不需要重启任何东西。pi 在下一个会话开始时就会读到新装的 skill。

## 有哪些 skill

| Skill | 做什么 |
|---|---|
| [`pi-session-move`](pi-session-move/) | 把会话记录挪到别的项目目录：同时改写 header 里的 `cwd`、system prompt 里的 `cwd`、子会话的 `parentSession` 指向，以及 pi-web 的会话索引。 |
| [`desktop-view`](desktop-view/) | 通过 ssh 看远程 Windows 主机：列出打开的窗口（标题、类名、位置、尺寸），或用 `PrintWindow` 抓取单个窗口自己的像素——被遮挡、贴在屏幕外都不影响。 |
| [`rainmeter-skin-layout`](rainmeter-skin-layout/) | 安全地做和改数据驱动的 Rainmeter 皮肤：从常量表生成 `.ini` 而不是手改，把像素算术放到后端，再用校验器加窗口截图验收。 |

每个 skill 目录都是自包含的（`SKILL.md` + 脚本），并且是它自己文档的唯一权威来源——
从那里开始读，或者看各目录下给人看的 `README.md`。

## 目录结构

```
pi-skills/
├── install.sh              # 把 skill 复制/链接进 agent 目录
├── LICENSE
└── <skill-name>/
    ├── SKILL.md            # 给 agent 看的：frontmatter + 完整使用说明
    ├── README.md           # 给人看的：它是什么、为什么、快速上手
    ├── scripts/            # 可选，脚本
    └── examples/           # 可选，skill 自带可运行样例时
```

目录名必须与 `SKILL.md` frontmatter 里的 `name` 字段一致。

## License

MIT —— 见 [LICENSE](LICENSE)。
