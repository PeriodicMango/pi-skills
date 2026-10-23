# pi-session-move

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB)

[English](README.md) | 简体中文

把一个 pi 会话挪到别的项目目录——按正确的方式挪。

pi 把会话存在 `~/.pi/agent/sessions/--<encoded-cwd>--/` 下，而一个会话"属于哪个项目"其实
**同时存在于两个地方**：它所在的文件夹，以及它 header 行里记录的 `cwd`。只改文件夹名字没有任何效果——
会话仍然在旧项目里恢复，Web UI 也仍然把它归在旧项目下。复制文件夹还会静默破坏子会话的
`parentSession` 链接，并让会话索引指向已经不存在的路径。

这个 skill 用一条命令做完上面四件事，并且不需要重启 Web UI 就能让索引保持一致。

同时兼容 **pi CLI** 与 **pi-web**：会话索引的处理针对的是 pi-web 的缓存，而且工具从不重启 Web 服务
（那会杀掉正在运行的会话——见下文）。

## 快速开始

```bash
./install.sh pi-session-move
S=~/.pi/agent/skills/pi-session-move/scripts/session_move.py

python3 $S list --cwd /home/user/proj              # 这个项目里有什么
python3 $S move --to /home/user/proj/sub --dry-run 01a13cb5
python3 $S move --to /home/user/proj/sub 01a13cb5 2026-10-15T02-36
python3 $S fix-parents --dry-run                   # 手工改过文件之后跑一次
```

## 它改了什么

对被移动的每个会话：

| 字段 | 原因 |
|---|---|
| 文件位置 → `sessions/--<encoded cwd>--/` | pi 按这个目录找项目 |
| header 里的 `cwd` | 恢复时的权威来源——`SessionManager.open()` 读它 |
| `message.sections.cwd` | system prompt 里记录的同一件事 |
| 其他会话的 `parentSession` | 子会话指向父会话的绝对路径 |
| `pi-web-session-index.json` | 清掉指向已不存在路径的条目 |

没改动的行按字节原样复制，只有被改的行会重新序列化，所以 diff 最小，而且会话正文永远不会被改写。

## 两个值得知道的事实

**挪完文件不要重启 pi-web。** 当 agent 跑在 pi-web 内部时，那个服务**就是**正在跑这段对话的进程——
重启它会杀掉进行中的工具调用，那一轮的结果就丢了。索引在下次扫描会话列表时会自己重建；刷新页面即可。

**子会话可能一个项目关键词都不含。** 一个 research 子会话的 prompt 是"……描述约束自动化招聘的法律制度……"，
里面既没有产品名也没有课程名，但它属于这个项目。找同类子会话要靠时间戳簇和 `parentSession`，不能只靠 grep。

完整细节、存储内部机制和踩坑清单都在 [`SKILL.md`](SKILL.md)——那才是 agent 真正读取的文件。

## 环境要求

Python 3.8+、POSIX 路径、`pi` / `pi-web` 的会话布局（2026 年 10 月对着
`@earendil-works/pi-coding-agent` 与 `@agegr/pi-web` 验证过）。

## License

MIT —— 见 [LICENSE](LICENSE)。
