import test from 'node:test';
import assert from 'node:assert/strict';

import {
  shouldConfirmBashCommand,
  getConfirmationMessage,
} from '../.pi/extensions/bash-confirmation/helpers.mjs';

test('requires confirmation for rm -rf commands', () => {
  assert.equal(shouldConfirmBashCommand('rm -rf build'), true);
  assert.equal(shouldConfirmBashCommand('sudo rm -rf /tmp/foo'), true);
});

test('requires confirmation for git push --force commands', () => {
  assert.equal(shouldConfirmBashCommand('git push --force origin main'), true);
  assert.equal(shouldConfirmBashCommand('git push --force-with-lease origin main'), true);
});

test('does not require confirmation for safe bash commands', () => {
  assert.equal(shouldConfirmBashCommand('git push origin main'), false);
  assert.equal(shouldConfirmBashCommand('rm -r build'), false);
  assert.equal(shouldConfirmBashCommand('echo "hello"'), false);
});

test('builds a readable confirmation message with the command', () => {
  const message = getConfirmationMessage('git push --force origin main');
  assert.match(message, /git push --force origin main/);
  assert.match(message, /Allow this command\?/);
});
