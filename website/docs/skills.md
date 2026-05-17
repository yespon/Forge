# Skills System

Skills are defined as SKILL.md files with YAML front matter in `skills/public/`.

## Structure
```
skills/public/
  deep-research/
    SKILL.md
  data-analysis/
    SKILL.md
  ...
```

## Creating a Skill
1. Create a directory in `skills/public/`
2. Add a SKILL.md file with YAML front matter:
```yaml
---
name: my-skill
description: "Description of the skill"
allowed-tools:
  - read_file
  - bash
---
## Skill Instructions
Markdown content here...
```
3. Restart the agent or call `SkillLoader.reload()`
