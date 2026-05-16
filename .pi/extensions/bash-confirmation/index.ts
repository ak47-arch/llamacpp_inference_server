import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

import {
  getConfirmationMessage,
  shouldConfirmBashCommand,
} from "./helpers.mjs";

export default function bashConfirmationExtension(pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;

    const command = typeof event.input?.command === "string" ? event.input.command : "";
    if (!shouldConfirmBashCommand(command)) return undefined;

    if (!ctx.hasUI) {
      return {
        block: true,
        reason: "Dangerous bash command blocked because confirmation UI is unavailable",
      };
    }

    const ok = await ctx.ui.confirm("Dangerous bash command", getConfirmationMessage(command));
    if (!ok) {
      return { block: true, reason: "Blocked by user" };
    }

    return undefined;
  });
}
