const assert = require('node:assert/strict');
const test = require('node:test');

const updateDependabot = require('./update-dependabot.cjs');

function createHarness(pulls, behindBy, updateBranch = async () => {}) {
  const calls = { list: [], compare: [], update: [], errors: [], failures: [] };
  const github = {
    paginate: async (_method, options) => {
      calls.list.push(options);
      return pulls;
    },
    rest: {
      pulls: {
        list() {},
        async updateBranch(options) {
          calls.update.push(options);
          await updateBranch(options);
        },
      },
      repos: {
        async compareCommitsWithBasehead(options) {
          calls.compare.push(options);
          return { data: { behind_by: behindBy[options.basehead] } };
        },
      },
    },
  };
  const core = {
    info() {},
    warning() {},
    error(message) { calls.errors.push(message); },
    setFailed(message) { calls.failures.push(message); },
  };
  return { github, core, calls, context: { repo: { owner: 'owner', repo: 'repo' } } };
}

function pull(number, author, sha, repository = 'owner/repo') {
  return { number, user: { login: author }, head: { sha, repo: { full_name: repository } } };
}

test('updates only behind Dependabot branches from this repository', async () => {
  const harness = createHarness([
    pull(1, 'dependabot[bot]', 'behind'),
    pull(2, 'dependabot[bot]', 'current'),
    pull(3, 'someone', 'other'),
    pull(4, 'dependabot[bot]', 'fork', 'other/repo'),
  ], { 'main...behind': 2, 'main...current': 0 });

  await updateDependabot(harness);

  assert.deepEqual(harness.calls.list, [{
    owner: 'owner', repo: 'repo', state: 'open', base: 'main', per_page: 100,
  }]);
  assert.deepEqual(harness.calls.compare.map(({ basehead }) => basehead), [
    'main...behind', 'main...current',
  ]);
  assert.deepEqual(harness.calls.update, [{
    owner: 'owner', repo: 'repo', pull_number: 1, expected_head_sha: 'behind',
  }]);
  assert.deepEqual(harness.calls.failures, []);
});

test('reports individual failures and continues updating other PRs', async () => {
  const harness = createHarness([
    pull(1, 'dependabot[bot]', 'first'),
    pull(2, 'dependabot[bot]', 'second'),
  ], { 'main...first': 1, 'main...second': 1 }, async ({ pull_number }) => {
    if (pull_number === 1) throw new Error('conflict');
  });

  await updateDependabot(harness);

  assert.deepEqual(harness.calls.update.map(({ pull_number }) => pull_number), [1, 2]);
  assert.match(harness.calls.errors[0], /#1.*conflict/);
  assert.equal(harness.calls.failures.length, 1);
});

test('fails explicitly when comparison data is missing', async () => {
  const harness = createHarness([pull(1, 'dependabot[bot]', 'unknown')], {});

  await updateDependabot(harness);

  assert.deepEqual(harness.calls.update, []);
  assert.match(harness.calls.errors[0], /#1/);
  assert.equal(harness.calls.failures.length, 1);
});
