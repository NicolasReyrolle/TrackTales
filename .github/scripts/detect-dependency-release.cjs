const { execFileSync } = require('node:child_process');
const fs = require('node:fs');

const systemRoot = process.env.SystemRoot || String.raw`C:\Windows`;
const programFiles = process.env['ProgramFiles'] || String.raw`C:\Program Files`;

const SAFE_PATH = process.platform === 'win32'
  ? String.raw`${systemRoot}\System32;${programFiles}\Git\cmd`
  : '/usr/bin:/bin';

function getGitExecutable() {
  if (process.platform === 'win32') {
    const winGit = String.raw`${programFiles}\Git\cmd\git.exe`;
    return fs.existsSync(winGit) ? winGit : 'git';
  }
  return fs.existsSync('/usr/bin/git') ? '/usr/bin/git' : 'git';
}

function defaultGit(...args) {
  return execFileSync(getGitExecutable(), args, {
    encoding: 'utf8',
    env: { ...process.env, PATH: SAFE_PATH },
  }).trim();
}

function isMergedDependabotPR(pull, sha) {
  return pull.user?.login === 'dependabot[bot]' &&
    pull.base?.ref === 'main' &&
    Boolean(pull.merged_at) &&
    pull.merge_commit_sha === sha;
}

async function verifyRelease(tag, { github, owner, repo, fetch }) {
  const { data: release } = await github.rest.repos.getReleaseByTag({ owner, repo, tag });
  if (release.draft || release.prerelease) {
    throw new Error(`${tag} is not a published GitHub release; investigate before releasing automatically.`);
  }
  const response = await fetch(`https://pypi.org/pypi/tracktales/${tag.slice(1)}/json`);
  if (!response.ok) {
    throw new Error(`Cannot verify ${tag} on PyPI (HTTP ${response.status}); investigate the previous release.`);
  }
  const metadata = await response.json();
  const types = new Set(metadata.urls.map((file) => file.packagetype));
  if (!types.has('bdist_wheel') || !types.has('sdist')) {
    throw new Error(`${tag} is missing a wheel or source distribution on PyPI; investigate the previous release.`);
  }
}

async function touchesRequirementsTxt(pullNumber, { github, owner, repo }) {
  const files = await github.paginate(github.rest.pulls.listFiles, {
    owner, repo, pull_number: pullNumber, per_page: 100,
  });
  return files.some((file) => file.filename === 'requirements.txt');
}

async function findRuntimeDependencyPR(commits, { github, owner, repo }) {
  for (const sha of commits) {
    const pulls = await github.paginate(github.rest.repos.listPullRequestsAssociatedWithCommit, {
      owner, repo, commit_sha: sha, per_page: 100,
    });
    for (const pull of pulls) {
      if (!isMergedDependabotPR(pull, sha)) continue;
      if (await touchesRequirementsTxt(pull.number, { github, owner, repo })) {
        return pull;
      }
    }
  }
  return null;
}

async function detectDependencyRelease({
  github, context, core,
  git = defaultGit,
  fetch = globalThis.fetch,
}) {
  const { owner, repo } = context.repo;
  const source = git('rev-parse', 'HEAD');
  const tags = git('tag', '--list', 'v*', '--sort=-version:refname').split('\n');
  const tag = tags.find((value) => /^v\d{4}\.\d+\.\d+$/.test(value));
  if (!tag) throw new Error('No CalVer release tag found; automatic release requires a published baseline.');

  await verifyRelease(tag, { github, owner, repo, fetch });

  const baseline = git('rev-parse', `${tag}^{commit}`);
  const common = git('merge-base', tag, source);
  if (common !== baseline) {
    const main = git('rev-parse', 'refs/remotes/origin/main');
    if (common === source && git('merge-base', tag, main) === baseline) {
      core.info(`The snapshot is already covered by ${tag}; the next check will consider newer updates.`);
      core.setOutput('should_release', 'false');
      return;
    }
    throw new Error(`Latest release tag ${tag} is not an ancestor of main's release snapshot.`);
  }

  const commits = git('rev-list', '--first-parent', `${tag}..${source}`).split('\n').filter(Boolean);
  const runtimePull = await findRuntimeDependencyPR(commits, { github, owner, repo });
  if (runtimePull) {
    core.info(`Dependabot PR #${runtimePull.number} changed requirements.txt since ${tag}.`);
    core.setOutput('should_release', 'true');
    return;
  }
  core.info(`No unreleased Dependabot runtime dependency updates since ${tag}.`);
  core.setOutput('should_release', 'false');
}

detectDependencyRelease.defaultGit = defaultGit;
module.exports = detectDependencyRelease;
