from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
import logging


from .config import Minecraft

logger = logging.getLogger(__file__)


def zip_directory(zip_file: Path, directory: Path):
    """
    Create a zip file of a directory.

    Args:
        zip_file: The zip file to create.
        directory: The directory to zip.

    Raises:
        ValueError: If the directory does not exist.
    """
    logger.info("Creating backup at %s of directory %s.", zip_file, directory)
    if not directory.is_dir():
        raise ValueError(directory)
    # create a zip file with compression, requires zlib to be installed
    with ZipFile(zip_file, "w", compression=ZIP_DEFLATED) as zf:
        for file in directory.rglob("*"):
            if file.is_dir():
                continue
            logger.info("Checking file: %s.", file)
            zf.write(file, str(file.relative_to(directory)))
            logger.info("Added %s to backup.", file)


def get_local_backups(server_config: Minecraft) -> list[tuple[str, str, str, float]]:
    """Get a list of all local backups.

    Args:
        bot: The bot instance.

    Returns:
        A list of all local backups. Each item contains the name, date, time, and size of each backup."""
    backups = []
    for backup in server_config.backup_dir.iterdir():
        backup_datetime = datetime.strptime(" ".join(backup.stem.split("_")[1:]), "%Y-%m-%d %H-%M-%S")
        backup_time = backup_datetime.strftime("%H:%M:%S")
        backup_date = backup_datetime.strftime("%Y-%m-%d")
        backup_size = round(backup.stat().st_size/1024/1024, 2)
        backups.append((backup.name, backup_date, backup_time, backup_size))
    return backups


def delete_local_backup(path: Path):
    if path.exists() and path.is_file():
        path.unlink()
    else:
        raise FileNotFoundError(path)
