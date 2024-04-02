import os
from rcon.source import rcon

async def run_command(command: str) -> str:
    """
    Run a command on the Minecraft server using RCON.
    
    Args:
        command (str): The command to run on the server.
        
    Returns:
        str: The response from the server.
    """
    if os.getenv("RCON_PASSWORD") is None:
        print("RCON_PASSWORD environment variable not found.")
        exit(1)
    elif os.getenv("RCON_PORT") is None:
        print("RCON_PORT environment variable not found.")
        exit(1)
    elif os.getenv("RCON_HOST") is None:
        print("RCON_HOST environment variable not found.")
        exit(1)
    with await rcon(os.getenv("RCON_HOST"), os.getenv("RCON_PORT"), os.getenv("RCON_PASSWORD")) as server_conn:
        response = server_conn.run(command)
    return response