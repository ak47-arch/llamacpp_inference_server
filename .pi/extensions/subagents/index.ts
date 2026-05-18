import type { ExtensionAPI, Skill } from '@mariozechner/pi-coding-agent';
import {
  createAgentSession,
  DefaultResourceLoader,
  getAgentDir,
  readOnlyTools,
  SessionManager,
} from '@mariozechner/pi-coding-agent';

import {
  buildSkillPrompt,
  buildSpecVerifierPrompt,
  buildTestVerifierPrompt,
  filterSkillsByName,
  parseIsolatedSkillArgs,
  parseSpecVerifyArgs,
  parseTestVerifyArgs,
  readDiffSource,
  readRequiredArtifact,
  resolveTargetCwd,
  summarizeRun,
  validateIsolatedSkillName,
} from './helpers.mjs';

type RunSkillOptions = {
  cwd: string;
  skillName: string;
  promptText?: string;
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

  let output = '';
  const unsubscribe = session.subscribe((event) => {
    if (event.type === 'message_update' && event.assistantMessageEvent.type === 'text_delta') {
      output += event.assistantMessageEvent.delta;
    }
  });

  try {
    await session.prompt(options.promptText ?? buildSkillPrompt(options.skillName, options.cwd));
    return output.trim();
  } finally {
    unsubscribe();
    session.dispose();
  }
}

async function runReportedSkillSession(pi: ExtensionAPI, ctx: any, options: RunSkillOptions) {
  const summary = summarizeRun({ skillName: options.skillName, cwd: options.cwd });
  ctx.ui.setStatus('subagent', `Running ${summary}`);
  ctx.ui.notify(`Starting isolated subagent: ${summary}`, 'info');

  try {
    const report = await runIsolatedSkillSession(options);

    if (!report) {
      ctx.ui.notify(`Subagent completed with no output: ${summary}`, 'warning');
      return;
    }

    pi.sendMessage({
      customType: 'subagent-report',
      content: `# Subagent Report\n\nRun: ${summary}\n\n${report}`,
      display: true,
      details: {
        skillName: options.skillName,
        cwd: options.cwd,
        isolated: true,
        tools: 'readOnlyTools',
      },
    });
    ctx.ui.notify(`Subagent finished: ${summary}`, 'success');
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    ctx.ui.notify(`Subagent failed: ${message}`, 'error');
  } finally {
    ctx.ui.setStatus('subagent', undefined);
  }
}

function assertIdle(ctx: any): boolean {
  if (!ctx.isIdle()) {
    ctx.ui.notify('Wait for the current turn to finish before starting a subagent.', 'warning');
    return false;
  }
  return true;
}

export default function subagentsExtension(pi: ExtensionAPI) {
  pi.registerCommand('module-boundary', {
    description: 'Run the module-boundary skill in an isolated child session',
    handler: async (args, ctx) => {
      if (!assertIdle(ctx)) return;

      const targetCwd = resolveTargetCwd(args, ctx.cwd);
      await runReportedSkillSession(pi, ctx, {
        cwd: targetCwd,
        skillName: 'module-boundary',
        model: ctx.model,
      });
    },
  });

  pi.registerCommand('isolated-skill', {
    description: 'Run an allowlisted read-only audit skill in an isolated child session',
    handler: async (args, ctx) => {
      if (!assertIdle(ctx)) return;

      try {
        const parsed = parseIsolatedSkillArgs(args, ctx.cwd);
        await runReportedSkillSession(pi, ctx, {
          cwd: parsed.cwd,
          skillName: validateIsolatedSkillName(parsed.skillName),
          model: ctx.model,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        ctx.ui.notify(message, 'error');
      }
    },
  });

  pi.registerCommand('spec-verify', {
    description: 'Run the spec-verifier skill in an isolated child session with explicit artifacts',
    handler: async (args, ctx) => {
      if (!assertIdle(ctx)) return;

      try {
        const targetCwd = ctx.cwd;
        const { specPath, diffSource } = parseSpecVerifyArgs(args);
        const skillText = readRequiredArtifact('.agents/skills/spec-verifier/SKILL.md', targetCwd, 'spec-verifier skill file');
        const specText = readRequiredArtifact(specPath, targetCwd, 'spec file');
        const diffText = readDiffSource(diffSource, targetCwd);
        const promptText = buildSpecVerifierPrompt({
          cwd: targetCwd,
          skillText,
          specPath,
          specText,
          diffSource,
          diffText,
        });

        await runReportedSkillSession(pi, ctx, {
          cwd: targetCwd,
          skillName: 'spec-verifier',
          promptText,
          model: ctx.model,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        ctx.ui.notify(message, 'error');
      }
    },
  });

  pi.registerCommand('test-verify', {
    description: 'Run the test-verifier skill in an isolated child session with explicit artifacts',
    handler: async (args, ctx) => {
      if (!assertIdle(ctx)) return;

      try {
        const targetCwd = ctx.cwd;
        const { specPath, testPath, redOutputPath } = parseTestVerifyArgs(args);
        const skillText = readRequiredArtifact('.agents/skills/test-verifier/SKILL.md', targetCwd, 'test-verifier skill file');
        const specText = readRequiredArtifact(specPath, targetCwd, 'spec file');
        const testText = readRequiredArtifact(testPath, targetCwd, 'test file');
        const redOutputText = readRequiredArtifact(redOutputPath, targetCwd, 'red output');
        const promptText = buildTestVerifierPrompt({
          cwd: targetCwd,
          skillText,
          specPath,
          specText,
          testPath,
          testText,
          redOutputPath,
          redOutputText,
        });

        await runReportedSkillSession(pi, ctx, {
          cwd: targetCwd,
          skillName: 'test-verifier',
          promptText,
          model: ctx.model,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        ctx.ui.notify(message, 'error');
      }
    },
  });
}
