const DANGEROUS_PATTERNS = [
  /\brm\s+-rf\b/i,
  /\bgit\s+push\b[\s\S]*?\s--force(?:\b|-with-lease\b)/i,
];

export function shouldConfirmBashCommand(command) {
  if (typeof command !== 'string') return false;
  return DANGEROUS_PATTERNS.some((pattern) => pattern.test(command));
}

export function getConfirmationMessage(command) {
  return `⚠️ Dangerous bash command detected:\n\n${command}\n\nAllow this command?`;
}
