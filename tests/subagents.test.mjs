import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  ALLOWED_ISOLATED_SKILLS,
  buildSkillPrompt,
  buildSpecVerifierPrompt,
  buildTestVerifierPrompt,
  filterSkillsByName,
  parseIsolatedSkillArgs,
  readDiffSource,
  readRequiredArtifact,
  resolveTargetCwd,
  summarizeRun,
  validateIsolatedSkillName,
} from '../.pi/extensions/subagents/helpers.mjs';

test('resolveTargetCwd defaults to current cwd when args are blank', () => {
  assert.equal(resolveTargetCwd('   ', '/repo/current'), '/repo/current');
});

test('resolveTargetCwd resolves relative paths against current cwd', () => {
  assert.equal(resolveTargetCwd('../other', '/repo/current'), '/repo/other');
});

test('buildSkillPrompt targets the requested skill and repo path only', () => {
  assert.equal(
    buildSkillPrompt('module-boundary', '/repo/current'),
    '/skill:module-boundary /repo/current',
  );
});


test('validateIsolatedSkillName allows only allowlisted audit skills', () => {
  assert.deepEqual(ALLOWED_ISOLATED_SKILLS, ['module-boundary', 'spec-verifier', 'test-verifier']);
  assert.equal(validateIsolatedSkillName('spec-verifier'), 'spec-verifier');
  assert.throws(() => validateIsolatedSkillName('feature-development'), /allowlisted/i);
});


test('parseIsolatedSkillArgs extracts skill name and optional cwd override', () => {
  assert.deepEqual(
    parseIsolatedSkillArgs('spec-verifier ../repo', '/workspace/current'),
    { skillName: 'spec-verifier', cwd: '/workspace/repo' },
  );
  assert.deepEqual(
    parseIsolatedSkillArgs('module-boundary', '/workspace/current'),
    { skillName: 'module-boundary', cwd: '/workspace/current' },
  );
});

test('filterSkillsByName keeps only the requested skill', () => {
  const filtered = filterSkillsByName(
    [
      { name: 'module-boundary' },
      { name: 'test-verifier' },
    ],
    'module-boundary',
  );

  assert.deepEqual(filtered, [{ name: 'module-boundary' }]);
});

test('buildSpecVerifierPrompt embeds full skill text, spec contents, and diff contents', () => {
  const prompt = buildSpecVerifierPrompt({
    cwd: '/repo/current',
    skillText: '# Spec Verifier Skill\nbody',
    specPath: 'specs/subagents.md',
    specText: '# Spec\ntext',
    diffSource: 'HEAD~1..HEAD',
    diffText: 'diff --git a/file b/file',
  });

  assert.match(prompt, /\/skill:spec-verifier \/repo\/current/);
  assert.match(prompt, /# Spec Verifier Skill\nbody/);
  assert.match(prompt, /specs\/subagents\.md/);
  assert.match(prompt, /# Spec\ntext/);
  assert.match(prompt, /HEAD~1\.\.HEAD/);
  assert.match(prompt, /diff --git a\/file b\/file/);
});


test('buildTestVerifierPrompt embeds full skill text, spec, test, and red output contents', () => {
  const prompt = buildTestVerifierPrompt({
    cwd: '/repo/current',
    skillText: '# Test Verifier Skill\nbody',
    specPath: 'specs/subagents.md',
    specText: '# Spec\ntext',
    testPath: 'tests/test_subagents.py',
    testText: 'def test_example():\n    assert False',
    redOutputPath: '/tmp/red.txt',
    redOutputText: 'FAILED (errors=1)',
  });

  assert.match(prompt, /\/skill:test-verifier \/repo\/current/);
  assert.match(prompt, /# Test Verifier Skill\nbody/);
  assert.match(prompt, /tests\/test_subagents\.py/);
  assert.match(prompt, /FAILED \(errors=1\)/);
});


test('readRequiredArtifact rejects missing and empty files', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'subagents-test-'));
  const emptyPath = path.join(tmpDir, 'empty.txt');
  fs.writeFileSync(emptyPath, '   ');

  assert.throws(() => readRequiredArtifact(path.join(tmpDir, 'missing.txt'), '/repo/current', 'spec file'), /spec file/i);
  assert.throws(() => readRequiredArtifact(emptyPath, '/repo/current', 'red output'), /red output/i);
});


test('readDiffSource reads diff text from a file and rejects empty diffs', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'subagents-test-'));
  const diffPath = path.join(tmpDir, 'diff.patch');
  const emptyDiffPath = path.join(tmpDir, 'empty.patch');
  fs.writeFileSync(diffPath, 'diff --git a/x b/x\n');
  fs.writeFileSync(emptyDiffPath, '\n');

  assert.equal(
    readDiffSource(diffPath, '/repo/current', () => {
      throw new Error('git should not be invoked for diff files');
    }),
    'diff --git a/x b/x\n',
  );
  assert.throws(() => readDiffSource(emptyDiffPath, '/repo/current', () => '   '), /empty diff/i);
});


test('readDiffSource resolves git diff text for commit-ish sources', () => {
  const diffText = readDiffSource('HEAD~1..HEAD', '/repo/current', (command, args, options) => {
    assert.equal(command, 'git');
    assert.deepEqual(args, ['diff', '--stat', '--patch', 'HEAD~1..HEAD']);
    assert.equal(options.cwd, '/repo/current');
    return 'diff --git a/x b/x\n';
  });

  assert.equal(diffText, 'diff --git a/x b/x\n');
});


test('subagent extension registers isolated verifier commands', () => {
  const extensionText = fs.readFileSync(new URL('../.pi/extensions/subagents/index.ts', import.meta.url), 'utf8');
  assert.match(extensionText, /registerCommand\(['"]module-boundary['"]/);
  assert.match(extensionText, /registerCommand\(['"]isolated-skill['"]/);
  assert.match(extensionText, /registerCommand\(['"]spec-verify['"]/);
  assert.match(extensionText, /registerCommand\(['"]test-verify['"]/);
});


test('summarizeRun records skill and cwd for display', () => {
  assert.equal(
    summarizeRun({ skillName: 'module-boundary', cwd: '/repo/current' }),
    'module-boundary @ /repo/current',
  );
});
