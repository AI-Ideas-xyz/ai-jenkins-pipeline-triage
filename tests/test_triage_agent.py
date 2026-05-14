import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# Stub agent_tools only for the import of triage_agent, then restore sys.modules
# so that test_agent_tools.py always gets the real module regardless of run order.
_saved_agent_tools = sys.modules.get("agent_tools")
sys.modules["agent_tools"] = MagicMock()
import triage_agent
if _saved_agent_tools is not None:
    sys.modules["agent_tools"] = _saved_agent_tools
else:
    sys.modules.pop("agent_tools", None)


class TestRunAgentLoop(unittest.TestCase):
    def test_returns_content_when_no_tool_calls(self):
        client = MagicMock()
        msg = MagicMock()
        msg.tool_calls = None
        msg.content = "RCA report text"
        client.chat.completions.create.return_value.choices = [MagicMock(message=msg)]

        result = triage_agent.run_agent_loop(client, [{"role": "user", "content": "go"}], "tok")
        self.assertEqual(result, "RCA report text")

    def test_executes_tool_call_then_returns_final(self):
        client = MagicMock()

        tc = MagicMock()
        tc.id = "call_abc"
        tc.function.name = "check_duplicate_issue"
        tc.function.arguments = json.dumps({"signature": "[eks-deploy] OOMKilled"})

        msg1 = MagicMock()
        msg1.tool_calls = [tc]

        msg2 = MagicMock()
        msg2.tool_calls = None
        msg2.content = "Final RCA"

        client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=msg1)]),
            MagicMock(choices=[MagicMock(message=msg2)]),
        ]

        with patch.object(
            triage_agent, "dispatch_tool", return_value='{"duplicate": false}'
        ) as mock_dispatch:
            result = triage_agent.run_agent_loop(
                client, [{"role": "user", "content": "go"}], "tok"
            )

        self.assertEqual(result, "Final RCA")
        mock_dispatch.assert_called_once_with(
            "check_duplicate_issue", {"signature": "[eks-deploy] OOMKilled"}, "tok"
        )


class TestBuildPrompt(unittest.TestCase):
    def test_playwright_instructions_injected(self):
        prompt = triage_agent.build_prompt(
            job="my-job",
            branch="main",
            commit="abc123",
            category="playwright-e2e",
            gist_raw_url="https://gist.example",
            actions_run_url="https://actions.example",
            log="sample log content",
        )
        self.assertIn("selector mismatches", prompt)
        self.assertIn("my-job", prompt)
        self.assertNotIn("kubectl commands", prompt)

    def test_eks_instructions_injected(self):
        prompt = triage_agent.build_prompt(
            job="my-job",
            branch="main",
            commit="abc123",
            category="eks-deploy",
            gist_raw_url="https://gist.example",
            actions_run_url="https://actions.example",
            log="sample log content",
        )
        self.assertIn("CrashLoopBackOff", prompt)
        self.assertNotIn("selector mismatches", prompt)

    def test_log_content_included_in_prompt(self):
        prompt = triage_agent.build_prompt(
            job="j",
            branch="b",
            commit="c",
            category="playwright-e2e",
            gist_raw_url="https://g",
            actions_run_url="https://a",
            log="Error: selector .submit-btn not found",
        )
        self.assertIn("Error: selector .submit-btn not found", prompt)

    def test_unknown_category_still_returns_prompt(self):
        prompt = triage_agent.build_prompt(
            job="j",
            branch="b",
            commit="c",
            category="some-new-category",
            gist_raw_url="https://g",
            actions_run_url="https://a",
            log="sample log content",
        )
        self.assertIn("some-new-category", prompt)


if __name__ == "__main__":
    unittest.main()
