"""On-demand upstream re-sync for the mattpocock_skills plugin.

POST /api/plugins/mattpocock_skills/sync_upstream

Re-runs the plugin's install pipeline without waiting for a commit in this
repository, so upstream skill changes can be pulled in at any time. This is a
thin wrapper over the same helpers the install() lifecycle hook uses; the
lifecycle stays the source of truth.
"""
from __future__ import annotations

from helpers.api import ApiHandler, Input, Output, Request


class SyncUpstream(ApiHandler):
    """Fetch upstream and re-sync skills plus slash commands."""

    async def process(self, input: Input, request: Request) -> Output:
        from usr.plugins.mattpocock_skills.helpers import commands_sync, upstream

        # Snapshot the currently recorded commit so the response can report
        # exactly what changed, rather than only what was installed.
        previous = upstream.read_config().get("resolved_commit", "")

        try:
            config = upstream.ensure_vendor()
        except Exception as exc:
            return {
                "success": False,
                "error": f"Upstream fetch failed: {exc}",
                "previous_commit": previous,
            }

        upstream.write_config(config)

        try:
            skills = upstream.sync_skills()
        except Exception as exc:
            return {
                "success": False,
                "error": f"Skill sync failed: {exc}",
                "previous_commit": previous,
                "current_commit": config.get("resolved_commit", ""),
            }

        commands = []
        command_error = ""
        try:
            commands = commands_sync.sync()
        except Exception as exc:  # commands are secondary; report, do not fail
            command_error = str(exc)

        current = config.get("resolved_commit", "")
        fetched = bool(config.get("fetched"))

        return {
            "success": True,
            "fetched": fetched,
            "changed": bool(previous and current and previous != current) or not previous,
            "previous_commit": previous,
            "current_commit": current,
            "upstream_version": config.get("upstream_version", ""),
            "synced_at": config.get("synced_at", ""),
            "skills_count": len(skills),
            "commands_count": len(commands),
            "command_error": command_error,
            "warning": (
                ""
                if fetched
                else "Upstream could not be reached; the existing local copy was reused."
            ),
        }
