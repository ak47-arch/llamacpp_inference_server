import path from 'node:path';

export function resolveTargetCwd(args, currentCwd) {
  const trimmed = (args || '').trim();
  if (!trimmed) return currentCwd;
  return path.resolve(currentCwd, trimmed);
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
