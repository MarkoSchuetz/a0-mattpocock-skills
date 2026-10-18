"""Fetch, verify and sync mattpocock/skills into the Agent Zero skill library.

The plugin repo ships no copy of the upstream skills. install() clones upstream
at the configured ref into a staging directory, verifies the expected skills are
present, swaps it into the plugin's vendor/ cache, then syncs those skills into
/a0/usr/skills. A failed or partial fetch leaves previously installed skills
untouched.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM_CONFIG = os.path.join(PLUGIN_DIR, "upstream.yaml")
VENDOR_ROOT = os.path.join(PLUGIN_DIR, "vendor")
VENDOR = os.path.join(VENDOR_ROOT, "mattpocock-skills")
SKILLS_DIR = "/a0/usr/skills"
MARKER = ".mattpocock_skills.json"
EXCLUDED = {"setup-matt-pocock-skills", "ask-matt"}
CATEGORIES = ("engineering", "productivity")
DEFAULT_REPO = "https://github.com/mattpocock/skills.git"
DEFAULT_REF = "main"


# --------------------------------------------------------------------------- #
# upstream.yaml (flat key: value; avoids a yaml dependency in the hook path)
# --------------------------------------------------------------------------- #
def read_config() -> dict:
    cfg = {"repo": DEFAULT_REPO, "ref": DEFAULT_REF}
    if not os.path.isfile(UPSTREAM_CONFIG):
        return cfg
    with open(UPSTREAM_CONFIG, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                cfg[key] = value
    return cfg


def write_config(cfg: dict) -> None:
    lines = [
        "# Upstream source for the synced skills.",
        "# repo/ref control what install() fetches; resolved_commit records the",
        "# exact upstream commit that produced the currently synced skills.",
        f"repo: {cfg.get('repo', DEFAULT_REPO)}",
        f"ref: {cfg.get('ref', DEFAULT_REF)}",
        f"resolved_commit: {cfg.get('resolved_commit', '')}",
        f"upstream_version: {cfg.get('upstream_version', '')}",
        f"synced_at: {cfg.get('synced_at', '')}",
        "",
    ]
    with open(UPSTREAM_CONFIG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# --------------------------------------------------------------------------- #
# fetch / verify / swap
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], cwd: str | None = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(f"{' '.join(cmd)} failed: {message}")
    return result.stdout.strip()


def fetch_staging(cfg: dict) -> tuple[str, str]:
    """Clone upstream into a fresh temp dir. Returns (path, commit_sha)."""
    staging = tempfile.mkdtemp(prefix="mattpocock_skills_upstream_")
    repo = cfg["repo"]
    ref = cfg.get("ref") or DEFAULT_REF
    try:
        _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                ref,
                "--",
                repo,
                staging,
            ]
        )
        commit = _run(["git", "rev-parse", "HEAD"], cwd=staging)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging, commit


def verify_staging(root: str) -> dict[str, str]:
    """Confirm a tree contains usable skills. Raises if it does not."""
    skills: dict[str, str] = {}
    for category in CATEGORIES:
        category_dir = os.path.join(root, "skills", category)
        if not os.path.isdir(category_dir):
            raise RuntimeError(f"upstream tree missing skills/{category}/")
        for path in sorted(glob.glob(os.path.join(category_dir, "*"))):
            name = os.path.basename(path)
            if not os.path.isdir(path) or name in EXCLUDED:
                continue
            if os.path.isfile(os.path.join(path, "SKILL.md")):
                skills[name] = path
    if not skills:
        raise RuntimeError("upstream tree contains no usable skills; refusing to swap")
    return skills


def swap_vendor(staging: str) -> None:
    os.makedirs(VENDOR_ROOT, exist_ok=True)
    previous = None
    if os.path.isdir(VENDOR):
        previous = VENDOR + ".old"
        shutil.rmtree(previous, ignore_errors=True)
        os.rename(VENDOR, previous)
    try:
        os.rename(staging, VENDOR)
    except Exception:
        if previous and not os.path.isdir(VENDOR):
            os.rename(previous, VENDOR)
        raise
    if previous:
        shutil.rmtree(previous, ignore_errors=True)


def have_vendor() -> bool:
    try:
        return bool(verify_staging(VENDOR))
    except Exception:
        return False


def ensure_vendor() -> dict:
    """Fetch upstream when possible; fall back to an existing local cache.

    Returns the effective config plus a 'fetched' flag.
    """
    cfg = read_config()
    fetched = False
    try:
        staging, commit = fetch_staging(cfg)
        try:
            verify_staging(staging)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        swap_vendor(staging)
        cfg["resolved_commit"] = commit
        fetched = True
    except Exception as exc:
        if have_vendor():
            print(
                "mattpocock_skills: upstream fetch failed "
                f"({exc}); using existing local copy"
            )
        else:
            raise RuntimeError(
                "mattpocock_skills: cannot fetch upstream and no local copy "
                f"exists: {exc}"
            )

    plugin_json = os.path.join(VENDOR, ".claude-plugin", "plugin.json")
    if os.path.isfile(plugin_json):
        try:
            with open(plugin_json, encoding="utf-8") as f:
                cfg["upstream_version"] = str(json.load(f).get("version", ""))
        except Exception:
            pass
    if fetched:
        cfg["synced_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cfg["fetched"] = fetched
    return cfg


# --------------------------------------------------------------------------- #
# skill sync (atomic per skill) and removal
# --------------------------------------------------------------------------- #
def _ensure_frontmatter(name: str, text: str) -> str:
    if text.lstrip().startswith("---"):
        return text
    frontmatter = (
        "---\n"
        f"name: {name}\n"
        f"description: Ported skill from mattpocock/skills ({name}).\n"
        "---\n\n"
    )
    return frontmatter + text


def sync_skills() -> dict[str, str]:
    skills = verify_staging(VENDOR)
    installed: dict[str, str] = {}
    for name, source in skills.items():
        destination = os.path.join(SKILLS_DIR, name)
        if os.path.isdir(destination) and not os.path.isfile(
            os.path.join(destination, MARKER)
        ):
            print(
                f"mattpocock_skills: skipping '{name}' "
                "(existing non-plugin skill)"
            )
            continue
        tmp = destination + ".mps_tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(source, tmp)
        skill_md = os.path.join(tmp, "SKILL.md")
        with open(skill_md, encoding="utf-8") as f:
            text = f.read()
        with open(skill_md, "w", encoding="utf-8") as f:
            f.write(_ensure_frontmatter(name, text))
        with open(os.path.join(tmp, MARKER), "w", encoding="utf-8") as f:
            json.dump({"source": "mattpocock_skills plugin", "skill": name}, f)
        shutil.rmtree(destination, ignore_errors=True)
        os.rename(tmp, destination)
        installed[name] = destination
    return installed


def remove_skills() -> list[str]:
    removed: list[str] = []
    for marker in glob.glob(os.path.join(SKILLS_DIR, "*", MARKER)):
        directory = os.path.dirname(marker)
        shutil.rmtree(directory, ignore_errors=True)
        removed.append(os.path.basename(directory))
    return removed


def remove_vendor() -> None:
    shutil.rmtree(VENDOR_ROOT, ignore_errors=True)
