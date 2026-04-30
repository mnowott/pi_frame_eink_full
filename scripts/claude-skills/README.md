# scripts/claude-skills/

Canonical, version-controlled copies of Claude Code skills used by this
project. The runtime location for skills is `~/.claude/skills/<name>/`,
but `.claude/` is gitignored at the repo root, so the source-of-truth
copies live here.

## Available skills

| Name | Purpose | Path |
|------|---------|------|
| `assume-aws-admin` | Source `scripts/aws/assume_admin.sh` to assume the imageuiapp-admin STS role before AWS commands that need more than S3-only permissions. | `assume-aws-admin/SKILL.md` |

## Activate a skill

```bash
SKILL=assume-aws-admin
mkdir -p ~/.claude/skills/${SKILL}
ln -sfn "$(pwd)/scripts/claude-skills/${SKILL}/SKILL.md" \
        ~/.claude/skills/${SKILL}/SKILL.md
```

After symlinking, Claude Code picks up the skill on next session start.
Symlinks (rather than copies) keep the runtime version in sync with the
repo as you pull updates.
