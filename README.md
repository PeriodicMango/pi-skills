# pi-skills

English | [简体中文](README.zh-CN.md)

Agent skills for [pi](https://github.com/earendil-works/pi) (pi-coding-agent / pi-web),
dropped into `~/.pi/agent/skills/`.

A skill is a folder with a `SKILL.md` the agent reads on demand — its `description`
is the only thing loaded up front, the body loads when the task matches. No build
step, no runtime.

## Install

```bash
git clone https://github.com/PeriodicMango/pi-skills.git
cd pi-skills

./install.sh --list                       # what's available
./install.sh pi-session-move              # one skill
./install.sh desktop-view rainmeter-skin-layout   # several at once
./install.sh --all                        # everything
./install.sh pi-session-move --link       # symlink instead (edit the repo, agent sees it)
```

`--dest DIR` installs somewhere other than `~/.pi/agent/skills/`. Copy mode is the
default because it survives the repo being moved or deleted; symlink mode is for
iterating on a skill.

Restart nothing. pi picks skills up on the next session.

## Skills

| Skill | What it does |
|---|---|
| [`pi-session-move`](pi-session-move/) | Move session transcripts between project directories: rewrites the session header `cwd`, the system-prompt `cwd`, `parentSession` links for subagent sessions, and the pi-web session index. |
| [`desktop-view`](desktop-view/) | See a remote Windows host over ssh: list open windows (title, class, position, size) or capture a single window's own pixels via `PrintWindow`, so occlusion and off-screen placement do not matter. |
| [`rainmeter-skin-layout`](rainmeter-skin-layout/) | Build and restyle data-driven Rainmeter skins safely: generate the `.ini` from a constant table instead of hand-editing, keep pixel arithmetic in a backend, and verify with a checker plus a window capture. |

Each skill directory is self-contained (`SKILL.md` + scripts) and is the source of
truth for its own docs — start there, or read the per-skill `README.md` for the
human-facing version.

## Layout

```
pi-skills/
├── install.sh              # copy/link a skill into an agent dir
├── LICENSE
└── <skill-name>/
    ├── SKILL.md            # agent-facing: frontmatter + full usage instructions
    ├── README.md           # human-facing: what it is, why, quick start
    ├── scripts/            # optional helpers
    └── examples/           # optional, when the skill ships runnable samples
```

The folder name must equal the `name` field in `SKILL.md` frontmatter.

## License

MIT — see [LICENSE](LICENSE).
