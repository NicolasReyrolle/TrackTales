const assert = require('node:assert/strict');
const test = require('node:test');
const detect = require('./detect-dependency-release.cjs');

function harness({ commits = [], pulls = {}, files = {}, tags = 'v2026.11.3',
  ancestor = true, release = {}, status = 200, types = ['bdist_wheel', 'sdist'] } = {}) {
  const outputs = {};
  const calls = [];
  const git = (...args) => {
    if (args[0] === 'rev-parse') return 'snapshot';
    if (args[0] === 'tag') return tags;
    if (args[0] === 'merge-base') {
      if (!ancestor) throw new Error('not ancestor');
      return '';
    }
    if (args[0] === 'rev-list') {
      assert.equal(args[2], 'v2026.11.3..snapshot');
      return commits.join('\n');
    }
    throw new Error(`Unexpected git command: ${args}`);
  };
  const github = {
    rest: {
      repos: { getReleaseByTag: async () => ({ data: release }), listPullRequestsAssociatedWithCommit() {} },
      pulls: { listFiles() {} },
    },
    async paginate(method, options) {
      if (method === github.rest.repos.listPullRequestsAssociatedWithCommit) {
        calls.push(options.commit_sha);
        return pulls[options.commit_sha] || [];
      }
      return (files[options.pull_number] || []).map((filename) => ({ filename }));
    },
  };
  const fetch = async () => ({
    ok: status === 200, status,
    json: async () => ({ urls: types.map((packagetype) => ({ packagetype })) }),
  });
  return {
    git, github, fetch, calls, outputs,
    context: { repo: { owner: 'owner', repo: 'repo' } },
    core: { info() {}, setOutput(key, value) { outputs[key] = value; } },
  };
}

function pull(number, sha, overrides = {}) {
  return {
    number, user: { login: 'dependabot[bot]' }, base: { ref: 'main' },
    merged_at: '2026-11-28T00:00:00Z', merge_commit_sha: sha, ...overrides,
  };
}

test('releases a merged Dependabot runtime update, including mixed manifest changes', async () => {
  const h = harness({
    commits: ['dev', 'runtime'],
    pulls: { dev: [pull(1, 'dev')], runtime: [pull(2, 'runtime')] },
    files: { 1: ['requirements-triage.txt'], 2: ['requirements-dev.txt', 'requirements.txt'] },
  });
  await detect(h);
  assert.equal(h.outputs.should_release, 'true');
  assert.deepEqual(h.calls, ['dev', 'runtime']);
});

test('ignores dev-only updates and unrelated or unmerged PRs', async () => {
  const h = harness({
    commits: ['dev', 'human', 'wrong-base', 'unmerged', 'different-merge'],
    pulls: {
      dev: [pull(1, 'dev')],
      human: [pull(2, 'human', { user: { login: 'someone' } })],
      'wrong-base': [pull(3, 'wrong-base', { base: { ref: 'develop' } })],
      unmerged: [pull(4, 'unmerged', { merged_at: null })],
      'different-merge': [pull(5, 'other')],
    },
    files: { 1: ['requirements-triage.txt'], 2: ['requirements.txt'], 3: ['requirements.txt'] },
  });
  await detect(h);
  assert.equal(h.outputs.should_release, 'false');
});

test('does not repeat a release when the snapshot has no commits after the published tag', async () => {
  const h = harness();
  await detect(h);
  assert.equal(h.outputs.should_release, 'false');
  assert.deepEqual(h.calls, []);
});

test('blocks incomplete or unverifiable previous releases', async () => {
  for (const [options, message] of [
    [{ tags: '' }, /No CalVer release tag/],
    [{ ancestor: false }, /not an ancestor/],
    [{ release: { draft: true } }, /not a published GitHub release/],
    [{ status: 404 }, /Cannot verify.*PyPI/],
    [{ types: ['bdist_wheel'] }, /missing a wheel or source distribution/],
  ]) {
    const h = harness(options);
    await assert.rejects(detect(h), message);
    assert.deepEqual(h.outputs, {});
  }
});

test('propagates GitHub and PyPI errors instead of treating them as no updates', async () => {
  const h = harness();
  h.github.rest.repos.getReleaseByTag = async () => { throw new Error('API unavailable'); };
  await assert.rejects(detect(h), /API unavailable/);
  h.github.rest.repos.getReleaseByTag = async () => ({ data: {} });
  h.fetch = async () => { throw new Error('network unavailable'); };
  await assert.rejects(detect(h), /network unavailable/);
});
