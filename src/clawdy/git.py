import os
import subprocess
from pathlib import Path

_GIT_TIMEOUT = 30
_GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


# Check if a directory is a git repository.
#
# Args:
#     repo_path: Filesystem path to check.
#
# Returns:
#     True if .git directory exists, False otherwise.
def is_git_repo(repo_path: str) -> bool:
    return Path(repo_path, ".git").is_dir()


# Pull latest changes from the remote.
#
# Args:
#     repo_path: Path to the git repository.
#
# Returns:
#     Stdout from git pull.
#
# Raises:
#     subprocess.CalledProcessError: If git pull fails.
#     subprocess.TimeoutExpired: If git pull exceeds timeout.
def pull(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "pull"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
        env=_GIT_ENV,
    )
    return result.stdout


# Stage all changes and commit with a message.
#
# Args:
#     repo_path: Path to the git repository.
#     message: Commit message.
#
# Raises:
#     subprocess.CalledProcessError: If git add or commit fails.
#     subprocess.TimeoutExpired: If a git command exceeds timeout.
def commit(repo_path: str, message: str) -> None:
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
        env=_GIT_ENV,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
        env=_GIT_ENV,
    )


# Push local commits to the remote.
#
# Args:
#     repo_path: Path to the git repository.
#
# Raises:
#     subprocess.CalledProcessError: If git push fails.
#     subprocess.TimeoutExpired: If git push exceeds timeout.
def push(repo_path: str) -> None:
    subprocess.run(
        ["git", "push"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
        env=_GIT_ENV,
    )


# Discard all uncommitted changes and reset to HEAD.
#
# Args:
#     repo_path: Path to the git repository.
def reset_hard(repo_path: str) -> None:
    subprocess.run(
        ["git", "reset", "--hard", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
        env=_GIT_ENV,
    )


# Get the porcelain status of the repository.
#
# Args:
#     repo_path: Path to the git repository.
#
# Returns:
#     Output of git status --porcelain.
def status(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT,
        env=_GIT_ENV,
    )
    return result.stdout
