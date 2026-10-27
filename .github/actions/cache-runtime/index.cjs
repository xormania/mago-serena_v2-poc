// GitHub provides runtime credentials to JavaScript actions, not ordinary run
// steps. Export only cache variables; never dump ACTIONS_* or provider secrets.
const fs = require('node:fs');

const required = ['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL'];
const allowed = [...required, 'ACTIONS_CACHE_URL', 'ACTIONS_CACHE_SERVICE_V2'];
if (!process.env.GITHUB_ENV || required.some(key => !process.env[key])) {
  throw new Error('Required GitHub cache runtime is unavailable');
}
const lines = allowed.filter(key => process.env[key]).map(key => {
  const value = process.env[key];
  if (/[\r\n]/.test(value)) throw new Error('Invalid GitHub cache runtime value');
  return `${key}=${value}`;
});
// Register the ephemeral cache token with the runner's masking mechanism before
// any later subprocess can log it. This workflow command is not ordinary output.
process.stdout.write(`::add-mask::${process.env.ACTIONS_RUNTIME_TOKEN.replaceAll('%', '%25')}\n`);
fs.appendFileSync(process.env.GITHUB_ENV, lines.join('\n') + '\n', 'utf8');
console.log('Prepared GitHub cache access; runtime values withheld.');
