"""Sync slash commands for mattpocock skills into the global _commands scope.

Creates one <slug>.command.yaml + <slug>.txt pair per installed skill in
/a0/usr/plugins/_commands/commands/, tracked with ownership markers so the
plugin can remove exactly what it created on uninstall.
"""
import os, re, json, glob

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = "/a0/usr/skills"
MARKER = ".mattpocock_skills.json"
CMD_DIR = "/a0/usr/plugins/_commands/commands"
CMD_MARKER = ".mattpocock_skills_command.json"

TEMPLATE = (
    "Load the skill \"{name}\" with the skills_tool (action: load, "
    "skill_name: \"{name}\"), then follow its full instructions to handle "
    "the user's request below.\n\n"
    "User request / arguments:\n\n{raw}"
)


def _installed_skills():
    """Yield (name, description) for each skill this plugin installed."""
    for skill_md in sorted(glob.glob(os.path.join(SKILLS_DIR, "*", "SKILL.md"))):
        d = os.path.dirname(skill_md)
        if not os.path.isfile(os.path.join(d, MARKER)):
            continue
        name = os.path.basename(d)
        with open(skill_md, encoding="utf-8") as f:
            text = f.read()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        desc = f"Run the {name} skill."
        if m:
            fm = m.group(1)
            dm = re.search(r"^description:\s*(.+)$", fm, re.M)
            if dm:
                desc = dm.group(1).strip().strip('"')
        yield name, desc


def sync():
    os.makedirs(CMD_DIR, exist_ok=True)
    created = []
    for name, desc in _installed_skills():
        yaml_path = os.path.join(CMD_DIR, f"{name}.command.yaml")
        txt_path = os.path.join(CMD_DIR, f"{name}.txt")
        marker_path = os.path.join(CMD_DIR, f"{name}{CMD_MARKER}")
        # never clobber a user-created command
        if os.path.exists(yaml_path) and not os.path.exists(marker_path):
            continue
        yaml_content = (
            f"name: {name}\n"
            f"description: {json.dumps(desc)}\n"
            f"template_path: {name}.txt\n"
            "type: text\n"
            'argument_hint: "<request or context to apply the skill to>"\n'
        )
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(TEMPLATE.format(name=name, raw="{raw}"))
        with open(marker_path, "w", encoding="utf-8") as f:
            json.dump({"source": "mattpocock_skills plugin", "command": name}, f)
        created.append(name)
    return created


def remove():
    removed = []
    for marker_path in glob.glob(os.path.join(CMD_DIR, f"*{CMD_MARKER}")):
        name = os.path.basename(marker_path)[: -len(CMD_MARKER)]
        for p in (
            os.path.join(CMD_DIR, f"{name}.command.yaml"),
            os.path.join(CMD_DIR, f"{name}.txt"),
            marker_path,
        ):
            if os.path.exists(p):
                os.remove(p)
        removed.append(name)
    return removed
