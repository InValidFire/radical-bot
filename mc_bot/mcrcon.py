import logging

from rcon.source import rcon
from .config import Rcon

logger = logging.getLogger(__name__)


#  we should move away from using this directly in the cog and instead use the functions in this file
async def run_command(command: str, rcon_config: Rcon) -> str:
    """
    Run a command on the Minecraft server using RCON.

    Args:
        command (str): The command to run on the server.

    Returns:
        str: The response from the server.
    """
    response = ""
    try:
        response = await rcon(command, host=rcon_config.host, port=rcon_config.port,
                              passwd=rcon_config.password)
    except OSError as e:
        response = str(f"{e} | {e.errno}")
        if "Errno 111" in str(e):  # for some reason, the errno value is not set, so we catch it this way
            raise ConnectionRefusedError("Connection refused. Is the server running?") from e
    except Exception as e:
        response = str(e)
        raise e
    return response


async def get_players(rcon_config: Rcon) -> list[str]:
    """Get the players on the Minecraft server.

    Args:
        rcon_config (Rcon): The Rcon configuration.

    Returns:
        list[str]: The players on the Minecraft server.
    """
    response = await run_command("list", rcon_config)
    response = response.split(":")
    return response[1].split(", ")


async def get_teams(rcon_config) -> str:
    """Get the ranks on the Minecraft server.

    Args:
        rcon_config (Rcon): The Rcon configuration.

    Returns:
        list[str]: The ranks on the Minecraft server.
    """
    response = await run_command("team list", rcon_config)
    if response == "There are no teams":
        return []
    response = response.split(":")[1].strip()
    response = response.replace("[", "").replace("]", "")  # remove brackets
    response = response.split(", ")
    return response


async def whitelist_add(player: str, rcon_config: Rcon) -> str:
    await run_command(f"whitelist add {player}", rcon_config)


async def whitelist_remove(player: str, rcon_config: Rcon) -> str:
    players = await get_players(rcon_config)
    logger.info(players)
    logger.info(f"Removing {player} from the whitelist.")
    if player in players:
        logger.info(f"Kicking {player} from the server.")
        await run_command(f"kick {player} You have been removed from the whitelist.", rcon_config)
    await run_command(f"whitelist remove {player}", rcon_config)


async def op(player: str, rcon_config: Rcon) -> str:
    await run_command(f"op {player}", rcon_config)


async def deop(player: str, rcon_config: Rcon) -> str:
    await run_command(f"deop {player}", rcon_config)


async def team_join(team: str, player: str, rcon_config: Rcon, color: str) -> str:
    if team not in await get_teams(rcon_config):
        await run_command(f"team add {team}", rcon_config)
        await run_command(f"team modify {team} color {color}", rcon_config)
    await run_command(f"team join {team} {player}", rcon_config)


async def team_leave(team: str, player: str, rcon_config: Rcon) -> str:
    if team in await get_teams(rcon_config):
        await run_command(f"team leave @a[name={player},team={team}]", rcon_config)
