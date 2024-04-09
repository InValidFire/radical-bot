import asyncio
import logging

logger = logging.getLogger(__name__)


class GitError(Exception):
    def __init__(self, *args: object, output=None) -> None:
        self.output = output
        super().__init__(*args)
    pass


async def __run_git_command(*command: str) -> tuple[str, str, int]:
    """Run a git command.

    Args:
        command (str): The command to run.

    Returns:
        tuple[str, str, int]: The stdout, stderr, and return code of the command.

    Raises:
        GitError: If the command fails."""
    logger.debug(f"Running git command: {' '.join(command)}")
    process = await asyncio.create_subprocess_exec("git", *command,
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    logger.debug(f"Process started with PID {process.pid}")
    stdout, stderr = await process.communicate()
    logger.debug(f"Process finished with return code {process.returncode}")
    logger.debug(f"stdout: {stdout.decode('utf-8')}")
    if process.returncode != 0:
        raise GitError(f"Git command '{' '.join(command)}' failed with return code {process.returncode}.",
                       output=stdout.decode("utf-8"))
    return stdout.decode("utf-8"), stderr.decode("utf-8"), process.returncode


async def get_current_branch() -> str:
    """Get the current branch of the repository.

    Returns:
        str: The current branch."""
    stdout, _, _ = await __run_git_command("branch")
    return stdout.split("\n")[0].replace("* ", "")


async def get_branches() -> list[str]:
    """Get all branches in the repository.

    Returns:
        list[str]: A list of branches."""
    stdout, _, _ = await __run_git_command("branch")
    return [branch.replace("* ", "") for branch in stdout.split("\n") if branch]


async def get_commit_info() -> tuple[str, str]:
    """Get the commit hash and message of the current commit.

    Returns:
        tuple[str, str]: The commit hash and message."""
    try:
        stdout, _, _ = await __run_git_command("log", "-1", "--format=%h %s")
    except GitError as e:
        logger.error("Failed to get commit info.")
        logger.error(e)
        return "Unknown", "Unknown"
    return stdout.strip().split(" ", 1)


async def switch_branch(branch: str):
    """Switch to a branch in the repository.

    Args:
        branch (str): The branch to switch to.

    Returns:"""

    logger.log(logging.INFO, f"Switching to branch {branch}.")
    process = await __run_git_command("checkout", branch)
    return process[0], process[1]


async def update(update_mode: str, branch: str = "main"):
    """Update the bot via Git.

    Args:
        update_mode (str): The update mode for the bot.
        branch (str): The branch to update from.

    Returns:
        None"""
    if update_mode == "commits":
        await __run_git_command("fetch")
        process = await __run_git_command("pull", "origin", branch)
        await __run_git_command("checkout", branch)
    else:
        await __run_git_command("fetch")  # tags aren't stored on branches, so we don't need to specify one
        latest_tag, _, _ = await __run_git_command("describe", "--tags", "--abbrev=0")
        process = await __run_git_command("checkout", latest_tag)
    return process[0], process[1]


async def align_tag_version(update_mode: str):
    """Align the bot version with the latest tag in the repository. Only works in tag mode.

    Args:
        bot (MainBot): The bot instance.

    Returns:
        bool: Whether the bot was updated.
    """
    if update_mode != "tags":
        logger.info("Currently in commit mode, no changes necessary.")
        return False
    stdout, _, _ = await __run_git_command("log", "-1", "--format=%h")
    is_a_release, _, _ = await __run_git_command("describe", "--exact-match", stdout.replace("'", ""))
    if len(is_a_release) > 0:
        logger.info("Current commit is a release, no change necessary.")
        return False
    elif len(is_a_release) == 0:
        logger.info("Current commit is not a release, updating.")
        try:
            await update(update_mode)
        except Exception as e:
            logger.error("Failed to update from Git.")
            logger.error(e)
            return False
        return True
    return False


async def get_version_hash(update_mode: str):
    """Get the current version of the bot.

    Returns:
        str: The current version of the bot."""
    if update_mode == "tags":
        process = await __run_git_command("describe", "--tags", "--abbrev=0")
        return f"release: {process[0].strip()}"
    else:
        process = await __run_git_command("log", "-1", "--format=%h")
        return f"commit: {process[0].strip()}"
