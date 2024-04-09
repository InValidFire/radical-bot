import logging
import asyncio
from datetime import datetime
from pathlib import Path
from .config import Cloud

logger = logging.getLogger(__file__)


__all__ = [
    "AWSException",
    "upload_backup"
]


class AWSException(Exception):
    pass


async def upload_backup(aws_config: Cloud, backup_path: Path):
    command = ("s3", "cp", str(backup_path),
               f"s3://{aws_config.bucket_name}/{backup_path.name}", "--acl", "public-read")
    await __run_aws_command(aws_config, command)


async def delete_cloud_backup(aws_config: Cloud, backup_name: str):
    command = ("s3", "rm", f"s3://{aws_config.bucket_name}/{backup_name}")
    try:
        await __run_aws_command(aws_config, command)
    except Exception as e:
        logger.error("Failed to delete backup '%s': %s", backup_name, e)


async def get_cloud_backups(aws_config: Cloud) -> list:
    backups_resp = await __run_aws_command(aws_config, ("s3", "ls", f"s3://{aws_config.bucket_name}"))
    backups = []
    if len(backups_resp[0]) == 0:
        return backups
    for backup in backups_resp[0].split("\n"):
        if not backup:  # skip empty lines
            continue
        backup_name = backup.split()[-1]
        backup_datetime = datetime.strptime(" ".join(backup_name.split("_")[1:]), "%Y-%m-%d %H-%M-%S.zip")
        backup_time = backup_datetime.strftime("%H:%M:%S")
        backup_date = backup_datetime.strftime("%Y-%m-%d")
        backup_size = round(int(backup.split()[2])/1024/1024, 2)
        backup_link = f"{aws_config.endpoint_url}/{aws_config.bucket_name}/{backup_name}"
        backup_link = f"[{backup_size} MiB]({backup_link})"
        backups.append((backup_name, backup_date, backup_time, backup_link))
    logger.info("Cloud backups [%s]: %s", len(backups), backups)
    return backups


async def __run_aws_command(aws_config: Cloud, command: tuple) -> tuple[str, str, int]:
    """
    Run an AWS CLI command.

    Args:
        bot: The bot instance.
        command: The command to run.

    Returns:
        A tuple containing the stdout, stderr, and return code of the command.
    """
    process = await asyncio.create_subprocess_exec(
        "aws", *command,
        env={"AWS_ACCESS_KEY_ID": aws_config.access_key_id,
             "AWS_SECRET_ACCESS_KEY": aws_config.access_key_secret,
             "AWS_DEFAULT_REGION": aws_config.region_name,
             "AWS_ENDPOINT_URL": aws_config.endpoint_url},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    logger.info("AWS command: %s", command)
    logger.info("AWS stdout: %s", stdout.decode("utf-8").strip())
    logger.info("AWS stderr: %s", stderr.decode("utf-8").strip())
    if process.returncode != 0:
        raise AWSException(f"AWS Error: {stderr.decode('utf-8').strip()}")
    return stdout.decode("utf-8"), stderr.decode("utf-8"), process.returncode
