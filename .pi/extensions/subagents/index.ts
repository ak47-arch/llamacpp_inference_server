import type { ExtensionAPI, Skill } from "@mariozechner/pi-coding-agent";
import {
  createAgentSession,
  DefaultResourceLoader,
  getAgentDir,
  readOnlyTools,
  SessionManager,
} from "@mariozechner/pi-coding-agent";

import {
  buildSkillPrompt,
  filterSkillsByName,
  resolveTargetCwd,
  summarizeRun,
} from "./helpers.mjs";

type RunSkillOptions = {
  cwd: string;
  skillName: string;
  model?: unknown;
};

async function runIsolatedSkillSession(options: RunSkillOptions): Promise<string> {
  const loader = new DefaultResourceLoader({
    cwd: options.cwd,
    agentDir: getAgentDir(),
    skillsOverride: (current) => ({
      skills: filterSkillsByName(current.skills as Skill[], options.skillName),
      diagnostics: current.diagnostics,
    }),
    promptsOverride: () => ({ prompts: [], diagnostics: [] }),
    agentsFilesOverride: () => ({ agentsFiles: [] }),
    systemPromptOverride: (base) =>
      `${base}\n\nYou are operating in an isolated child session. Use only the files, skills, and instructions available in this session. Do not assume any parent-session context.`,
  });

  await loader.reload();
  const { skills } = loader.getSkills();
  if (skills.length === 0) {
    throw new Error(`Required skill '${options.skillName}' was not discovered for child session`);
  }

  const { session } = await createAgentSession({
    cwd: options.cwd,
    model: options.model,
    resourceLoader: loader,
    sessionManager: SessionManager.inMemory(),
    tools: readOnlyTools,
  });

  let output = "";
  const unsubscribe = session.subscribe((event) => {
    if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
      output += event.assistantMessageEvent.delta;
    }
  });

  try {
    await session.prompt(buildSkillPrompt(options.skillName, options.cwd));
    return output.trim();
  } finally {
    unsubscribe();
    session.dispose();
  }
}

export default function subagentsExtension(pi: ExtensionAPI) {
  pi.registerCommand("module-boundary", {
    description: "Run the module-boundary skill in an isolated child session",
    handler: async (args, ctx) => {
      if (!ctx.isIdle()) {
        ctx.ui.notify("Wait for the current turn to finish before starting a subagent.", "warning");
        return;
      }

      const targetCwd = resolveTargetCwd(args, ctx.cwd);
      const summary = summarizeRun({ skillName: "module-boundary", cwd: targetCwd });
      ctx.ui.setStatus("subagent", `Running ${summary}`);
      ctx.ui.notify(`Starting isolated subagent: ${summary}`, "info");

      try {
        const report = await runIsolatedSkillSession({
          cwd: targetCwd,
          skillName: "module-boundary",
          model: ctx.model,
        });

        if (!report) {
          ctx.ui.notify(`Subagent completed with no output: ${summary}`, "warning");
          return;
        }

        pi.sendMessage({
          customType: "subagent-report",
          content: `# Subagent Report\n\nRun: ${summary}\n\n${report}`,
          display: true,
          details: {
            skillName: "module-boundary",
            cwd: targetCwd,
            isolated: true,
            tools: "readOnlyTools",
          },
        });
        ctx.ui.notify(`Subagent finished: ${summary}`, "success");
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        ctx.ui.notify(`Subagent failed: ${message}`, "error");
      } finally {
        ctx.ui.setStatus("subagent", undefined);
      }
    },
  });
}
