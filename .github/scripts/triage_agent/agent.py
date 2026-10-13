import os

from github import Github

from .analysis import analyze_issue
from .models import TriageAnalysis


class IssueTriageAgent:
    def __init__(self, github_token: str, issue_number: int, repo_name: str):
        self.gh = Github(github_token)
        self.repo = self.gh.get_repo(repo_name)
        self.issue = self.repo.get_issue(number=issue_number)

    def analyze(self) -> TriageAnalysis:
        return analyze_issue(self.issue.title, self.issue.body or "")

    def execute_triage(self):
        analysis = self.analyze()

        # 1. Apply labels
        requested_labels = set(
            analysis.suggested_labels + [analysis.classification, f"severity:{analysis.severity}"]
        )
        available_labels = {label.name for label in self.repo.get_labels()}
        labels = requested_labels & available_labels
        if labels:
            self.issue.add_to_labels(*labels)

        # 2. Post structured comment
        comment_body = (
            f"🤖 **Automated Triage Analysis**\n\n"
            f"{analysis.formatted_comment}\n\n"
            f"---  \n"
            f"**Testable with pytest:** "
            f"{'Yes' if analysis.is_testable else 'No (Missing XML/GPX sample)'}"
        )
        self.issue.create_comment(comment_body)


if __name__ == "__main__":
    token = os.environ["GITHUB_TOKEN"]
    issue_num = int(os.environ["ISSUE_NUMBER"])
    repository = os.environ["REPO_NAME"]

    agent = IssueTriageAgent(token, issue_num, repository)
    agent.execute_triage()
