import subprocess
from pathlib import Path


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
def pull(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "pull"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
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
def commit(repo_path: str, message: str) -> None:
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )


# Push local commits to the remote.
#
# Args:
#     repo_path: Path to the git repository.
#
# Raises:
#     subprocess.CalledProcessError: If git push fails.
def push(repo_path: str) -> None:
    subprocess.run(
        ["git", "push"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
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
    )
    return result.stdout
