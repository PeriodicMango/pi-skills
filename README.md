# pi-skills

Agent skills for [pi](https://github.com/earendil-works/pi-coding-agent) (pi-coding-agent / pi-web),
dropped into `~/.pi/agent/skills/`.

A skill is a folder with a `SKILL.md` the agent reads on demand — its `description`
is the only thing loaded up front, the body loads when the task matches. No build
step, no runtime.

## Install

```bash
git clone https://github.com/PeriodicMango/pi-skills.git
cd pi-skills

./install.sh --list                  # what's available
./install.sh pi-session-move         # copy into ~/.pi/agent/skills/
./install.sh pi-session-move --link  # symlink instead (edit the repo, agent sees it)
```

`--dest DIR` installs somewhere other than `~/.pi/agent/skills/`. Copy mode is the
default because it survives the repo being moved or deleted; symlink mode is for
iterating on a skill.

Restart nothing. pi picks skills up on the next session.

## Skills

| Skill | What it does |
|---|---|
| [`pi-session-move`](pi-session-move/) | Move session transcripts between project directories: rewrites the session header `cwd`, the system-prompt `cwd`, `parentSession` links for subagent sessions, and the pi-web session index. |

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
    └── scripts/            # optional helpers
```

The folder name must equal the `name` field in `SKILL.md` frontmatter.

## License

MIT — see [LICENSE](LICENSE).
