from pathlib import Path
from uuid import UUID
from typing import Union
import json
import logging

import aiofiles
import aiohttp

from .mcrcon import team_join, team_leave, op, deop, whitelist_add, whitelist_remove
from .config import Rcon

import discord

logger = logging.getLogger(__name__)


class Player:
    def __init__(self, uuid: UUID, mc_username: str, is_trusted: bool = False, is_whitelisted: bool = False,
                 is_owner: bool = False, is_staff: bool = False) -> None:
        self.uuid = uuid
        self.mc_username = mc_username
        self.is_trusted = is_trusted
        self.is_whitelisted = is_whitelisted
        self.is_owner = is_owner
        self.is_staff = is_staff

    def __repr__(self):
        return f"Player(uuid={self.uuid}, mc_username={self.mc_username}, is_trusted={self.is_trusted},\
is_whitelisted={self.is_whitelisted})"

    def __str__(self):
        return f"{self.mc_username} ({self.uuid})"

    def as_dict(self):
        return {"uuid": str(self.uuid), "mc_username": self.mc_username, "is_trusted": self.is_trusted,
                "is_whitelisted": self.is_whitelisted, "is_owner": self.is_owner, "is_staff": self.is_staff}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Union['Player', None]:
        if data is None:
            return None
        player = cls(UUID(data['uuid']), data['mc_username'], data['is_trusted'], data['is_whitelisted'],
                     data['is_owner'], data['is_staff'])
        return player

    @classmethod
    async def lookup_player(cls, query: str) -> Union['Player', None]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://playerdb.co/api/player/minecraft/{query}') as resp:
                if resp.status == 204:
                    return None
                data = await resp.json()
                if data['success'] is False:
                    return None

                # https://playerdb.co/api/player/minecraft/EmberIgnited
                uuid = UUID(data['data']['player']['id'])
                username = data['data']['player']['username']

                return cls(uuid, username)


def create_profile_embed(user: discord.User, player: Player, embed: discord.Embed) -> discord.Embed:
    """Create an embed for a player's profile.

    Args:
        user (discord.User): The user to create the profile for.
        player (Player): The player data.

    Returns:
        PlayersEmbed: The embed for the player's profile.
    """
    embed.add_field(name="Minecraft Username", value=player.mc_username, inline=False)
    embed.add_field(name="Whitelisted", value="Yes" if player.is_whitelisted or player.is_owner else "No")
    embed.add_field(name="Trusted", value="Yes" if player.is_trusted or player.is_owner else "No")
    if player.is_owner:
        embed.add_field(name="Owner", value="Yes")
    if player.is_staff:
        embed.add_field(name="Staff", value="Yes")
    embed.set_footer(text=user.name, icon_url=user.avatar.url)
    return embed


async def mc_whitelist(player: Player, rcon_config: Rcon):
    await team_join("Whitelisted", player.mc_username, rcon_config, "green")
    await whitelist_add(player.mc_username, rcon_config)
    player.is_whitelisted = True


async def mc_unwhitelist(player: Player, rcon_config: Rcon):
    """
    Remove a player from the whitelist in Minecraft.

    Args:
        player (Player): The player to remove.
        rcon_config (Rcon): The Rcon configuration to use.

    Raises:
        ValueError: If the player is not found.
    """
    await team_leave("Whitelisted", player.mc_username, rcon_config)
    await whitelist_remove(player.mc_username, rcon_config)
    player.is_whitelisted = False


async def mc_trust(player: Player, rcon_config: Rcon):
    """
    Add a player to the trusted team in Minecraft.

    Args:
        player (Player): The player to add.
        rcon_config (Rcon): The Rcon configuration to use.

    Raises:
        ValueError: If the player is not found.
    """
    await team_leave("Whitelisted", player.mc_username, rcon_config)
    await team_join("Trusted", player.mc_username, rcon_config, "blue")
    player.is_trusted = True


async def mc_untrust(player: Player, rcon_config: Rcon):
    """
    Remove a player from the trusted team in Minecraft.

    Args:
        player (Player): The player to remove.
        rcon_config (Rcon): The Rcon configuration to use.

    Raises:
        ValueError: If the player is not found.
    """
    await team_leave("Trusted", player.mc_username, rcon_config)
    await team_join("Whitelisted", player.mc_username, rcon_config, "green")
    await whitelist_remove(player.mc_username, rcon_config)
    player.is_trusted = False


async def mc_staff(player: Player, rcon_config: Rcon):
    """
    Add a player to the staff team in Minecraft.

    Args:
        player (Player): The player to add.
        rcon_config (Rcon): The Rcon configuration to use.

    Raises:
        ValueError: If the player is not found.
    """
    await team_leave("Trusted", player.mc_username, rcon_config)
    await team_join("Staff", player.mc_username, rcon_config, "purple")
    await op(player.mc_username, rcon_config)
    player.is_staff = True


async def mc_unstaff(player: Player, rcon_config: Rcon):
    """
    Remove a player from the staff team in Minecraft.

    Args:
        player (Player): The player to remove.
        rcon_config (Rcon): The Rcon configuration to use.

    Raises:
        ValueError: If the player is not found.
    """
    await team_leave("Staff", player.mc_username, rcon_config)
    await deop(player.mc_username, rcon_config)
    player.is_staff = False


async def mc_owner(player: Player, rcon_config: Rcon):
    """
    Add a player to the owner team in Minecraft.

    Args:
        player (Player): The player to add.
        rcon_config (Rcon): The Rcon configuration to use.

    Raises:
        ValueError: If the player is not found."""
    await team_join("Owner", player.mc_username, rcon_config, "light_purple")
    await whitelist_add(player.mc_username, rcon_config)
    await op(player.mc_username, rcon_config)
    player.is_owner = True
    player.is_whitelisted = True


async def mc_unowner(player: Player, rcon_config: Rcon):
    """
    Remove a player from the owner team in Minecraft.

    Args:
        player (Player): The player to remove.
        rcon_config (Rcon): The Rcon configuration to use.

    Raises:
        ValueError: If the player is not found.
    """
    await team_leave("Owner", player.mc_username, rcon_config)
    await deop(player.mc_username, rcon_config)
    player.is_owner = False


class PlayerData:
    def __init__(self, file_path: Path, rcon_config: Rcon):
        self.file_path = file_path
        if not file_path.exists():
            file_path.touch()
            file_path.write_text('{}')
        self._playerdata: dict[int, dict[str, str]] = json.loads(file_path.read_text())
        self.rcon_config = rcon_config

    def __str__(self):
        return str(self._playerdata)

    async def save(self):
        """
        Save the player data to the file.

        Raises:
            FileNotFoundError: If the file is not found.
        """
        async with aiofiles.open(self.file_path, 'w+') as f:
            await f.write(json.dumps(self._playerdata, indent=4))

    async def add_owner(self, discord_id: int):
        """
        Add a player to the owner team.

        Args:
            discord_id (str): The Discord ID of the player to add.

        Raises:
            ValueError: If the player is not found.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_owner(player, self.rcon_config)
        self.set(discord_id, player)
        await self.save()

    async def remove_owner(self, discord_id: int):
        """
        Remove a player from the owner team.

        Args:
            discord_id (str): The Discord ID of the player to remove.

        Raises:
            ValueError: If the player is not found.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_unowner(player, self.rcon_config)
        self.set(discord_id, player)
        await self.save()

    async def add_staff(self, discord_id: int):
        """
        Add a player to the staff team.

        Args:
            discord_id (str): The Discord ID of the player to add.

        Raises:
            ValueError: If the player is not found."""
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_staff(player, self.rcon_config)
        self.set(discord_id, player)
        await self.save()

    async def remove_staff(self, discord_id: int):
        """
        Remove a player from the staff team.

        Args:
            discord_id (str): The Discord ID of the player to remove.

        Raises:
            ValueError: If the player is not found.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_unstaff(player, self.rcon_config)
        player.is_staff = False
        self.set(discord_id, player)
        await self.save()

    async def add(self, discord_id: int, query: str):
        """
        Add a player to the player data. This will create a profile for the player.

        Args:
            discord_id (str): The Discord ID of the player.
            query (str): The Minecraft username of the player.

        Raises:
            ValueError: If the player is not found.
        """
        player = await Player.lookup_player(query)
        if player is None:
            raise ValueError("Player not found.")
        self.set(discord_id, player)
        await self.save()

    async def whitelist(self, discord_id: int):
        """
        Add a player to the whitelist. This will add them to the whitelist on the server and Discord.

        Args:
            discord_id (str): The Discord ID of the player.

        Raises:
            ValueError: If the player is not found in the player data.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_whitelist(player, self.rcon_config)
        self.set(discord_id, player)
        await self.save()

    async def unwhitelist(self, discord_id: int):
        """
        Unwhitelist a player. This will remove them from the whitelist on the server and Discord.

        Args:
            discord_id (str): The Discord ID of the player.

        Raises:
            ValueError: If the player is not found in the player data.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_unwhitelist(player, self.rcon_config)
        self.set(discord_id, player)
        await self.save()

    async def trust(self, discord_id: int):
        """
        Trust a player. This will add them to the trusted team on the server and Discord.

        Args:
            discord_id (str): The Discord ID of the player.

        Raises:
            ValueError: If the player is not found in the player data.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_trust(player, self.rcon_config)
        player.is_trusted = True
        self.set(discord_id, player)

        await self.save()

    async def untrust(self, discord_id: int):
        """
        Untrust a player. This will remove them from the trusted team on the server and Discord.

        Args:
            discord_id (str): The Discord ID of the player.

        Raises:
            ValueError: If the player is not found in the player data.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_untrust(player, self.rcon_config)
        self.set(discord_id, player)

        await self.save()

    async def remove(self, discord_id: int):
        """
        Remove a player from the player data.

        Args:
            discord_id (str): The Discord ID of the player to remove.

        Raises:
            ValueError: If the player is not found in the player data.
        """
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found in player data.")
        if player.is_owner:
            await self.remove_owner(discord_id)
        if player.is_staff:
            await self.remove_staff(discord_id)
        if player.is_trusted:
            await self.untrust(discord_id)
        if player.is_whitelisted:
            await self.unwhitelist(discord_id)
        player = Player.from_dict(self._playerdata.pop(str(discord_id)))
        await self.save()

    def get(self, discord_id: int) -> Player | None:
        """
        Get a player object from the player data. If the player is not found, return None.

        Args:
            discord_id (str): The Discord ID of the player.

        Raises:
            ValueError: If the player is not found in the player data.

        Returns:
            Player | None: The player object if found, otherwise None."""
        player = Player.from_dict(self._playerdata.get(str(discord_id)))
        if player is None:
            raise ValueError("Player not found in player data.")
        return player

    def get_all(self) -> list[tuple[int, Player]]:
        return [(int(k), Player.from_dict(v)) for k, v in self._playerdata.items()]

    def set(self, discord_id: int, player: Player):
        self._playerdata[str(discord_id)] = player.as_dict()
