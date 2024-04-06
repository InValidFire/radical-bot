from rcon.source import rcon
from .config import Rcon


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
