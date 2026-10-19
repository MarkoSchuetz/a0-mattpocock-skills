"""Lifecycle hooks for the mattpocock_skills plugin.

No upstream skill content is committed to this repository. install() fetches
mattpocock/skills at the ref configured in upstream.yaml, verifies the clone,
caches it under vendor/, and syncs the skills into /a0/usr/skills. The
framework calls install() again after every plugin update, so upstream changes
arrive without any manual step.
"""
import os

from usr.plugins.mattpocock_skills.helpers import upstream


def _notify(kind: str, message: str, display_time: int = 6) -> None:
    """Best-effort WebUI notification; never breaks the lifecycle hook."""
    try:
        from helpers.notification import (
            NotificationPriority,
            NotificationType,
        )
        from agent import AgentContext

        type_map = {
            "info": NotificationType.INFO,
            "success": NotificationType.SUCCESS,
            "warning": NotificationType.WARNING,
            "error": NotificationType.ERROR,
            "progress": NotificationType.PROGRESS,
        }
        AgentContext.get_notification_manager().add_notification(
            type_map.get(kind, NotificationType.INFO),
            NotificationPriority.NORMAL,
            message,
            "Matt Pocock Skills",
            "",
            display_time,
            "mattpocock_skills",
        )
    except Exception:
        pass


def install():
    """Fetch upstream, sync skills, then sync the matching slash commands."""
    _notify(
        "progress",
        "Contacting GitHub to fetch the latest skills — this can take up to a minute.",
        10,
    )

    config = upstream.ensure_vendor()
    upstream.write_config(config)

    installed = upstream.sync_skills()
    print(
        f"mattpocock_skills: synced {len(installed)} skills "
        f"from upstream {config.get('resolved_commit', 'unknown')[:12]}"
    )

    try:
        from usr.plugins.mattpocock_skills.helpers import commands_sync

        commands = commands_sync.sync()
        print(f"mattpocock_skills: synced {len(commands)} slash commands")
    except Exception as exc:  # command sync must not fail the skill install
        print(f"mattpocock_skills: command sync failed: {exc}")

    commit = config.get("resolved_commit", "")[:12] or "unknown"
    if config.get("fetched"):
        _notify(
            "success",
            f"Synced {len(installed)} skills at upstream {commit}.",
            8,
        )
    else:
        _notify(
            "warning",
            "GitHub could not be reached; the previously synced skills were kept.",
            10,
        )

    return {"skills": installed, "config": config}


def pre_update():
    """Nothing to stop: install() re-fetches and re-syncs atomically."""
    pass


def uninstall():
    """Remove synced skills, their commands, and the vendored cache."""
    removed = upstream.remove_skills()
    print(f"mattpocock_skills: removed {len(removed)} skills")

    try:
        from usr.plugins.mattpocock_skills.helpers import commands_sync

        removed_commands = commands_sync.remove()
        print(f"mattpocock_skills: removed {len(removed_commands)} slash commands")
    except Exception as exc:
        print(f"mattpocock_skills: command removal failed: {exc}")

    upstream.remove_vendor()
    print("mattpocock_skills: removed vendored upstream cache")
