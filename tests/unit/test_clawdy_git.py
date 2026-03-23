import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.clawdy.git import pull, commit, push, is_git_repo, status


class TestIsGitRepo:
    def test_valid_git_repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert is_git_repo(str(tmp_path)) is True

    def test_not_a_git_repo(self, tmp_path):
        assert is_git_repo(str(tmp_path)) is False

    def test_nonexistent_path(self):
        assert is_git_repo("/nonexistent/path") is False


class TestPull:
    @patch("src.clawdy.git.subprocess.run")
    def test_pull_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date.\n")
        result = pull(str(tmp_path))
        assert result == "Already up to date.\n"
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0] == ["git", "pull"]
        assert args[1]["cwd"] == str(tmp_path)

    @patch("src.clawdy.git.subprocess.run")
    def test_pull_failure_raises(self, mock_run, tmp_path):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git pull", stderr="error")
        with pytest.raises(subprocess.CalledProcessError):
            pull(str(tmp_path))


class TestCommit:
    @patch("src.clawdy.git.subprocess.run")
    def test_commit_stages_and_commits(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        commit(str(tmp_path), "test message")
        assert mock_run.call_count == 2
        add_call = mock_run.call_args_list[0]
        assert add_call[0][0] == ["git", "add", "-A"]
        commit_call = mock_run.call_args_list[1]
        assert "test message" in commit_call[0][0]


class TestPush:
    @patch("src.clawdy.git.subprocess.run")
    def test_push_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        push(str(tmp_path))
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "push"]


class TestStatus:
    @patch("src.clawdy.git.subprocess.run")
    def test_status_returns_output(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout=" M file.md\n")
        result = status(str(tmp_path))
        assert result == " M file.md\n"
