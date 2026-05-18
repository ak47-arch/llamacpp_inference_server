import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export const ALLOWED_ISOLATED_SKILLS = ['module-boundary', 'spec-verifier', 'test-verifier'];

export function resolveTargetCwd(args, currentCwd) {
  const trimmed = (args || '').trim();
  if (!trimmed) return currentCwd;
  return path.resolve(currentCwd, trimmed);
}

export function validateIsolatedSkillName(skillName) {
  const normalized = String(skillName || '').trim();
  if (!ALLOWED_ISOLATED_SKILLS.includes(normalized)) {
    throw new Error(
      `Skill '${normalized || '(empty)'}' is not allowlisted for isolated execution. Allowed skills: ${ALLOWED_ISOLATED_SKILLS.join(', ')}`,
    );
  }
  return normalized;
}

export function parseIsolatedSkillArgs(args, currentCwd) {
  const trimmed = String(args || '').trim();
  if (!trimmed) {
    throw new Error('Usage: /isolated-skill <skill-name> [cwd]');
  }

  const [skillName, cwdOverride] = trimmed.split(/\s+/, 2);
  return {
    skillName: validateIsolatedSkillName(skillName),
    cwd: cwdOverride ? path.resolve(currentCwd, cwdOverride) : currentCwd,
  };
}

export function buildSkillPrompt(skillName, cwd) {
  return `/skill:${skillName} ${cwd}`;
}

export function filterSkillsByName(skills, skillName) {
  return skills.filter((skill) => skill.name === skillName);
}

export function summarizeRun({ skillName, cwd }) {
  return `${skillName} @ ${cwd}`;
}

export function readRequiredArtifact(filePath, currentCwd, label) {
  const resolvedPath = path.resolve(currentCwd, String(filePath || '').trim());
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Required ${label} not found: ${resolvedPath}`);
  }
  const text = fs.readFileSync(resolvedPath, 'utf8');
  if (!text.trim()) {
    throw new Error(`Required ${label} is empty: ${resolvedPath}`);
  }
  return text;
}

export function readDiffSource(diffSource, currentCwd, runGit = defaultRunGitDiff) {
  const trimmed = String(diffSource || '').trim();
  if (!trimmed) {
    throw new Error('Diff source is required');
  }

  const candidatePath = path.resolve(currentCwd, trimmed);
  let text;
  if (fs.existsSync(candidatePath)) {
    text = fs.readFileSync(candidatePath, 'utf8');
  } else {
    const args = trimmed.includes('..') || trimmed.includes('...')
      ? ['diff', '--stat', '--patch', trimmed]
      : ['show', '--stat', '--patch', trimmed];
    text = runGit('git', args, { cwd: currentCwd, encoding: 'utf8' });
  }

  if (!String(text || '').trim()) {
    throw new Error(`Resolved empty diff from source: ${trimmed}`);
  }
  return text;
}

function defaultRunGitDiff(command, args, options) {
  return execFileSync(command, args, options);
}

export function parseSpecVerifyArgs(args) {
  const trimmed = String(args || '').trim();
  const parts = trimmed.split(/\s+/, 2);
  if (parts.length < 2 || !parts[0] || !parts[1]) {
    throw new Error('Usage: /spec-verify <spec-path> <diff-source>');
  }
  return {
    specPath: parts[0],
    diffSource: parts[1],
  };
}

export function parseTestVerifyArgs(args) {
  const trimmed = String(args || '').trim();
  const parts = trimmed.split(/\s+/, 3);
  if (parts.length < 3 || !parts[0] || !parts[1] || !parts[2]) {
    throw new Error('Usage: /test-verify <spec-path> <test-path> <red-output-path>');
  }
  return {
    specPath: parts[0],
    testPath: parts[1],
    redOutputPath: parts[2],
  };
}

export function buildSpecVerifierPrompt({ cwd, skillText, specPath, specText, diffSource, diffText }) {
  return [
    buildSkillPrompt('spec-verifier', cwd),
    '',
    'You are running in an isolated read-only verifier session.',
    'Use only the artifacts included below. Do not assume parent-session context.',
    '',
    '## Verifier Skill Text',
    skillText,
    '',
    `## Spec File: ${specPath}`,
    specText,
    '',
    `## Diff Source: ${diffSource}`,
    diffText,
  ].join('\n');
}

export function buildTestVerifierPrompt({ cwd, skillText, specPath, specText, testPath, testText, redOutputPath, redOutputText }) {
  return [
    buildSkillPrompt('test-verifier', cwd),
    '',
    'You are running in an isolated read-only verifier session.',
    'Use only the artifacts included below. Do not assume parent-session context.',
    '',
    '## Verifier Skill Text',
    skillText,
    '',
    `## Spec File: ${specPath}`,
    specText,
    '',
    `## Test File: ${testPath}`,
    testText,
    '',
    `## Red Output File: ${redOutputPath}`,
    redOutputText,
  ].join('\n');
}
