import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildSkillPrompt,
  filterSkillsByName,
  resolveTargetCwd,
  summarizeRun,
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

test('summarizeRun records skill and cwd for display', () => {
  assert.equal(
    summarizeRun({ skillName: 'module-boundary', cwd: '/repo/current' }),
    'module-boundary @ /repo/current',
  );
});
