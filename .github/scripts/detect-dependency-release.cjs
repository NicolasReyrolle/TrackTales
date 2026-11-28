const { execFileSync } = require('node:child_process');

module.exports = async function detectDependencyRelease({
  github, context, core,
  git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim(),
  fetch = globalThis.fetch,
}) {
  const { owner, repo } = context.repo;
  const source = git('rev-parse', 'HEAD');
  const tags = git('tag', '--list', 'v*', '--sort=-version:refname').split('\n');
  const tag = tags.find((value) => /^v\d{4}\.\d+\.\d+$/.test(value));
  if (!tag) throw new Error('No CalVer release tag found; automatic release requires a published baseline.');

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
  for (const sha of commits) {
    const pulls = await github.paginate(github.rest.repos.listPullRequestsAssociatedWithCommit, {
      owner, repo, commit_sha: sha, per_page: 100,
    });
    for (const pull of pulls) {
      if (pull.user?.login !== 'dependabot[bot]' || pull.base?.ref !== 'main' ||
          !pull.merged_at || pull.merge_commit_sha !== sha) continue;
      const files = await github.paginate(github.rest.pulls.listFiles, {
        owner, repo, pull_number: pull.number, per_page: 100,
      });
      if (files.some((file) => file.filename === 'requirements.txt')) {
        core.info(`Dependabot PR #${pull.number} changed requirements.txt since ${tag}.`);
        core.setOutput('should_release', 'true');
        return;
      }
    }
  }
  core.info(`No unreleased Dependabot runtime dependency updates since ${tag}.`);
  core.setOutput('should_release', 'false');
};
