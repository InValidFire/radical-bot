from pathlib import Path
from uuid import UUID
from typing import Union
import json
import logging

import aiofiles
import aiohttp

from .mcrcon import team_join, team_leave, op, deop, whitelist_add, whitelist_remove
from .config import Rcon

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


async def mc_whitelist(player: Player, rcon_config: Rcon):
    await team_join("Whitelisted", player.mc_username, rcon_config, "green")
    await whitelist_add(player.mc_username, rcon_config)
    player.is_whitelisted = True


async def mc_unwhitelist(player: Player, rcon_config: Rcon):
    await team_leave("Whitelisted", player.mc_username, rcon_config)
    await whitelist_remove(player.mc_username, rcon_config)
    player.is_whitelisted = False


async def mc_trust(player: Player, rcon_config: Rcon):
    await team_join("Trusted", player.mc_username, rcon_config, "blue")
    player.is_trusted = True


async def mc_untrust(player: Player, rcon_config: Rcon):
    await team_leave("Trusted", player.mc_username, rcon_config)
    await whitelist_remove(player.mc_username, rcon_config)
    player.is_trusted = False


async def mc_staff(player: Player, rcon_config: Rcon):
    await team_join("Staff", player.mc_username, rcon_config, "yellow")
    await op(player.mc_username, rcon_config)
    player.is_staff = True


async def mc_unstaff(player: Player, rcon_config: Rcon):
    await team_leave("Staff", player.mc_username, rcon_config)
    await deop(player.mc_username, rcon_config)
    player.is_staff = False


async def mc_owner(player: Player, rcon_config: Rcon):
    await team_join("Owner", player.mc_username, rcon_config, "red")
    await whitelist_add(player.mc_username, rcon_config)
    await op(player.mc_username, rcon_config)
    player.is_owner = True


async def mc_unowner(player: Player, rcon_config: Rcon):
    await team_leave("Owner", player.mc_username, rcon_config)
    await whitelist_remove(player.mc_username, rcon_config)
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

    def is_whitelisted(self, discord_id: str) -> bool:
        return discord_id in self._playerdata

    async def save(self):
        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(self._playerdata, indent=4))

    async def add_owner(self, discord_id: str):
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_owner(player, self.rcon_config)
        self._playerdata[discord_id] = player.as_dict()
        await self.save()

    async def remove_owner(self, discord_id: str):
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_unowner(player, self.rcon_config)
        self._playerdata[discord_id] = player.as_dict()
        await self.save()

    async def add_staff(self, discord_id: str):
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_staff(player, self.rcon_config)
        self._playerdata[discord_id] = player.as_dict()
        await self.save()

    async def remove_staff(self, discord_id: str):
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found.")
        await mc_unstaff(player, self.rcon_config)
        player.is_staff = False
        self._playerdata[discord_id] = player.as_dict()
        await self.save()

    async def add(self, discord_id: str, query: str):
        player = await Player.lookup_player(query)
        if player is None:
            raise ValueError("Player not found.")
        self._playerdata[discord_id] = player.as_dict()
        await self.save()

    async def whitelist(self, discord_id: str):
        player = self.get(discord_id)
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_whitelist(player, self.rcon_config)
        self._playerdata[discord_id] = player.as_dict()
        await self.save()

    async def unwhitelist(self, discord_id: str):
        player = Player.from_dict(self._playerdata[discord_id])
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_unwhitelist(player, self.rcon_config)
        self._playerdata[discord_id] = player.as_dict()
        await self.save()

    async def trust(self, discord_id: str):
        player = Player.from_dict(self._playerdata[discord_id])
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_trust(player, self.rcon_config)
        player.is_trusted = True
        self._playerdata[discord_id] = player.as_dict()

        await self.save()

    async def untrust(self, discord_id: str):
        player = Player.from_dict(self._playerdata[discord_id])
        if player is None:
            raise ValueError("Player not found in player data.")
        await mc_untrust(player, self.rcon_config)
        self._playerdata[discord_id] = player.as_dict()

        await self.save()

    async def remove(self, discord_id: str):
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
        player = Player.from_dict(self._playerdata.pop(discord_id))
        await self.save()

    def get(self, discord_id: str) -> Player | None:
        player = Player.from_dict(self._playerdata.get(discord_id))
        if player is None:
            raise ValueError("Player not found in player data.")
        return player

    def get_all(self) -> list[tuple[int, Player]]:
        return [(int(k), Player.from_dict(v)) for k, v in self._playerdata.items()]
