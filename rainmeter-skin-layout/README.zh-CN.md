# rainmeter-skin-layout

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)
![Rainmeter](https://img.shields.io/badge/Rainmeter-skin-orange)

[English](README.md) | 简体中文

一个 [pi](https://github.com/earendil-works/pi) skill，用来做和改**数据驱动的 Rainmeter 皮肤**——
就是内容来自 API 或文件（日历、待办清单、时间线）而不是在创作时就固定下来的那种。

这里的价值不是一份模板，而是一串只有撞上去才知道的约束：`WebParser` 一个 measure 最多 99 个捕获组、
皮肤没有滚动容器所以"滚动"得重新定义、某些刷新命令会把 WebParser 卡死到必须重启整个进程、
`Update` 与 `UpdateRate` 是耦合的，以及写错就会把所有字形搞乱的 ini 编码要求。

## 两条规则

1. **生成 ini，永远不要手改它。** 重复的段落是同一份模板套 N 遍；手改会静默漏掉另外 N−1 份。
2. **所有像素算术留在后端。** 皮肤里是固定的"槽位"，每个选项都绑定到一个 measure，由后端决定东西放哪里。
   于是重叠处理、时长到像素的换算、裁剪，都待在一个你能调试的地方。

## 安装

```bash
./install.sh rainmeter-skin-layout   # 在 pi-skills 仓库根目录执行
```

手工安装就是把本目录复制到 `~/.pi/agent/skills/rainmeter-skin-layout`。

pi 在启动时扫描 skills 目录，所以**新开一个会话**即可生效；也可以用 `/skill:rainmeter-skin-layout` 强制调用。
不需要其他配置——这个 skill 是文档加一个可运行示例，不依赖任何特定机器。

## 示例

`examples/minimal/` 是这套模式的完整自包含实例——约 480 行 Python，无外部依赖：

```bash
cd examples/minimal
python3 layout.py -o Minimal.ini     # 生成皮肤
python3 check.py Minimal.ini --demo  # 校验它；同时解析示例 payload
```

它被故意做得很小（一列、8 小时、3 个槽位），但覆盖了每一处关键：重复的模板、带 assert 的捕获组预算、
整除约束、必须能从常量重新推导出来的几何，以及必须刚好解析出预期组数的 payload。

## 真正难的地方

大部分难度不在 Rainmeter 语法，而在于**布局 bug 是静默的**。某段文字读了隔壁行的值、网格线偏了两个像素、
某个标签的墨迹被上面的元素盖住——这些都不会报错。它们只是看起来有点不对，等人类发现时才暴露。

所以这个 skill 大半篇幅花在两件事上：哪些约束是硬限制，以及怎么造一个**从常量重新推导布局**、
而不是重新读文件的校验器。示例里的校验器能抓到（其中包括）：

- 同一个 `StringIndex` 被用了两次，或指向 pattern 末尾之外
- 某个槽位引用了邻居的 measure
- 网格线不在它推导出来的位置上
- 画布尺寸不再等于底板加内边距

skill 里有一条检查项：**验证校验器本身**——把上面每一条都故意造一次。
失败路径从未执行过的校验器，给出的信心是它没挣到的。

## 相关

配套的 **desktop-view** skill 能通过 ssh 抓取单个窗口的像素，包括被遮挡和在屏幕外的情况。
这里"改动流程"的最后一步是"抓窗口、量像素来验收"，而那个 skill 就是拿到截图的方式。

## License

MIT —— 见 [LICENSE](LICENSE)。
