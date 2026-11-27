module.exports = async function updateDependabot({ github, context, core }) {
  const { owner, repo } = context.repo;
  const pulls = await github.paginate(github.rest.pulls.list, {
    owner,
    repo,
    state: 'open',
    base: 'main',
    per_page: 100,
  });
  const dependabotPulls = pulls.filter((pull) => {
    if (pull.user?.login !== 'dependabot[bot]') return false;
    if (pull.head.repo?.full_name?.toLowerCase() !== `${owner}/${repo}`.toLowerCase()) {
      core.warning(`Skipping #${pull.number}: head branch is not in this repository.`);
      return false;
    }
    return true;
  });

  const results = await Promise.all(dependabotPulls.map(async (pull) => {
    try {
      const { data } = await github.rest.repos.compareCommitsWithBasehead({
        owner,
        repo,
        basehead: `main...${pull.head.sha}`,
        per_page: 1,
      });
      if (!Number.isInteger(data.behind_by) || data.behind_by < 0) {
        throw new Error('GitHub did not return a valid behind_by count');
      }
      if (data.behind_by === 0) {
        core.info(`#${pull.number} is already up to date.`);
        return false;
      }

      await github.rest.pulls.updateBranch({
        owner,
        repo,
        pull_number: pull.number,
        expected_head_sha: pull.head.sha,
      });
      core.info(`Requested update for #${pull.number} (${data.behind_by} commits behind).`);
      return false;
    } catch (error) {
      core.error(`Failed to update #${pull.number}: ${String(error)}`);
      return true;
    }
  }));

  const failures = results.filter(Boolean).length;

  if (failures > 0) {
    core.setFailed(`Could not update ${failures} Dependabot pull request(s).`);
  }
};
