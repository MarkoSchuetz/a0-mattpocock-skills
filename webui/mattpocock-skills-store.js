import { createStore } from "/js/AlpineStore.js";
import * as api from "/js/api.js";
import {
  toastFrontendSuccess,
  toastFrontendError,
  toastFrontendWarning,
} from "/components/notifications/notification-store.js";

const API = "plugins/mattpocock_skills/sync_upstream";
const SHORT = 12;

function shortSha(sha) {
  return sha ? sha.slice(0, SHORT) : "—";
}

export const store = createStore("mattpocockSkillsStore", {
  status: "idle",
  result: null,
  lastRun: null,

  init() {},

  onOpen() {},

  cleanup() {},

  get busy() {
    return this.status === "syncing";
  },

  get currentCommitShort() {
    return shortSha(this.result?.current_commit || this.lastRun?.current_commit);
  },

  async resyncUpstream() {
    if (this.busy) return;

    this.status = "syncing";
    this.result = null;

    try {
      const response = await api.fetchApi(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "resync" }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Re-sync failed");
      }

      this.result = data;
      this.lastRun = data;
      this.status = "idle";

      if (data.warning) {
        toastFrontendWarning(data.warning, "Matt Pocock Skills");
        return;
      }

      const prefix = data.changed ? "Upstream updated" : "Already current";
      toastFrontendSuccess(
        `${prefix} — ${data.skills_count} skills, ${data.commands_count} commands at ${shortSha(
          data.current_commit,
        )}`,
        "Matt Pocock Skills",
      );

      if (data.command_error) {
        toastFrontendWarning(
          `Commands not fully synced: ${data.command_error}`,
          "Matt Pocock Skills",
        );
      }
    } catch (error) {
      this.status = "idle";
      toastFrontendError(`Re-sync failed: ${error.message}`, "Matt Pocock Skills");
    }
  },
});
