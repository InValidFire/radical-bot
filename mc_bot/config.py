import json
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

from discord.ext import commands
from discord import TextChannel


@dataclass
class Rcon:
    host: str
    port: int
    password: str


@dataclass
class Cloud:
    region_name: str = None
    bucket_name: str = None
    endpoint_url: str = None
    access_key_id: str = None
    access_key_secret: str = None


@dataclass
class Minecraft:
    server_ram: str
    server_dir: Path
    backup_dir: Path
    rcon: Rcon


@dataclass
class Discord:
    bot_token: str
    bot_channel: TextChannel
    error_channel: TextChannel


@dataclass
class General:
    mode: str
    update_mode: str
    update_branch: str


@dataclass
class Config:
    discord: Discord
    minecraft: Minecraft
    cloud: Cloud
    general: General


def _load_jsonc(filepath: Path) -> defaultdict:
    """
    Process a .jsonc file and return a JSON object. Comments are removed.

    Args:
        filepath (Path): The path to the JSON file.
    """
    json_text = filepath.open().read()
    for line in json_text.splitlines():
        if line.startswith("//"):
            json_text = json_text.replace(line, "")
        json_text = json_text.replace(line, line.split("// ")[0])
    return json.loads(json_text, object_hook=defaultdict_from_dict)


def handle_missing_key():
    return None


def defaultdict_from_dict(d: dict):
    """
    Convert a dict to a defaultdict.

    Args:
        d (dict): The dictionary to convert.

    Returns:
        defaultdict: The converted defaultdict.
    """
    dd = defaultdict(handle_missing_key)
    for k, v in d.items():
        if isinstance(v, dict):
            dd[k] = defaultdict_from_dict(v)
        else:
            dd[k] = v
    return dd


def load_config(bot: commands.Bot, filepath: Path) -> Config:
    """
    Load the configuration from a JSON or JSONC file.

    Args:
        filepath (Path): The path to the JSON file.

    Returns:
        Config: The configuration object.
    """
    data = _load_jsonc(filepath)
    discord = Discord(data["discord"]["bot_token"],
                      bot.get_channel(data["discord"]["bot_channel_id"]),
                      bot.get_channel(data["discord"]["error_channel_id"]))
    rcon = Rcon(data["minecraft"]["rcon"]["host"],
                data["minecraft"]["rcon"]["port"],
                data["minecraft"]["rcon"]["password"])
    minecraft = Minecraft(data["minecraft"]["server_ram"],
                          Path("data").joinpath(data["minecraft"]["server_dir"]),
                          Path("data").joinpath(data["minecraft"]["backup_dir"]),
                          rcon)
    general = General(data["general"]["mode"],
                      data["general"]["update_mode"],
                      data["general"]["update_branch"])
    cloud = Cloud()
    if data.get("cloud") is not None:
        cloud.region_name = data["cloud"]["region_name"]
        cloud.bucket_name = data["cloud"]["bucket_name"]
        cloud.endpoint_url = data["cloud"]["endpoint_url"]
        cloud.access_key_id = data["cloud"]["access_key_id"]
        cloud.access_key_secret = data["cloud"]["access_key_secret"]
    config = Config(discord, minecraft, cloud, general)
    return config
