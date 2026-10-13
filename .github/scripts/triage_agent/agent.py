import os

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from github import Github

from .models import TriageAnalysis
from .prompts import SYSTEM_PROMPT


class IssueTriageAgent:
    def __init__(self, github_token: str, issue_number: int, repo_name: str):
        self.gh = Github(github_token)
        self.repo = self.gh.get_repo(repo_name)
        self.issue = self.repo.get_issue(number=issue_number)

        # GitHub Models endpoints are compatible with Azure AI Inference SDK
        self.llm_client = ChatCompletionsClient(
            endpoint="https://models.github.ai/inference",
            credential=AzureKeyCredential(github_token),
        )

    def analyze(self) -> TriageAnalysis:
        user_content = f"Title: {self.issue.title}\n\nBody:\n{self.issue.body or ''}"

        response = self.llm_client.complete(
            messages=[SystemMessage(content=SYSTEM_PROMPT), UserMessage(content=user_content)],
            model="openai/gpt-4o",
            response_format="json_object",
        )

        raw_json = response.choices[0].message.content
        return TriageAnalysis.model_validate_json(raw_json)

    def execute_triage(self):
        analysis = self.analyze()

        # 1. Apply labels
        labels = set(
            analysis.suggested_labels + [analysis.classification, f"severity:{analysis.severity}"]
        )
        self.issue.add_to_labels(*list(labels))

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
