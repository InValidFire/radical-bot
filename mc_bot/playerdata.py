from pathlib import Path
from uuid import UUID
import json

import aiofiles
import aiohttp

from .mcrcon import run_command
from .config import Rcon


class Player:
    def __init__(self, uuid: UUID, mc_username: str, is_trusted: bool = False, is_whitelisted: bool = False):
        self.uuid = uuid
        self.mc_username = mc_username
        self.is_trusted = is_trusted
        self.is_whitelisted = is_whitelisted

    def __repr__(self):
        return f"Player(uuid={self.uuid}, mc_username={self.mc_username}, is_trusted={self.is_trusted},\
is_whitelisted={self.is_whitelisted})"

    def __str__(self):
        return f"{self.mc_username} ({self.uuid})"

    def as_dict(self):
        return {"uuid": str(self.uuid), "mc_username": self.mc_username, "is_trusted": self.is_trusted,
                "is_whitelisted": self.is_whitelisted}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> 'Player':
        return cls(UUID(data['uuid']), data['mc_username'], data['is_trusted'], data['is_whitelisted'])

    @classmethod
    async def lookup_player(cls, query: str) -> 'Player' | None:
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

    def is_whitelisted(self, discord_id: int) -> bool:
        return discord_id in self._playerdata

    async def add(self, discord_id: int, query: str):
        player = await Player.lookup_player(query)
        if player is None:
            raise ValueError(f"Player '{query}' not found.")
        self._playerdata[discord_id] = player.as_dict()
        async with aiofiles.open(self.file_path, 'a') as f:
            await f.write(json.dumps(self._playerdata))

    async def whitelist(self, discord_id: int):
        player = Player.from_dict(self._playerdata[discord_id])
        if player is None:
            raise ValueError(f"Player '{discord_id}' not found.")
        player.is_whitelisted = True
        self._playerdata[discord_id] = player.as_dict()

        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(self._playerdata))
        await run_command(f"whitelist add {player.mc_username}", self.rcon_config)

    async def unwhitelist(self, discord_id: int):
        player = Player.from_dict(self._playerdata[discord_id])
        if player is None:
            raise ValueError(f"Player '{discord_id}' not found.")
        player.is_whitelisted = False
        self._playerdata[discord_id] = player.as_dict()

        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(self._playerdata))
        await run_command(f"whitelist remove {player.mc_username}", self.rcon_config)

    async def trust(self, discord_id: int):
        player = Player.from_dict(self._playerdata[discord_id])
        if player is None:
            raise ValueError(f"Player '{discord_id}' not found.")
        player.is_trusted = True
        self._playerdata[discord_id] = player.as_dict()

        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(self._playerdata))

    async def untrust(self, discord_id: int):
        player = Player.from_dict(self._playerdata[discord_id])
        if player is None:
            raise ValueError(f"Player '{discord_id}' not found.")
        player.is_trusted = False
        self._playerdata[discord_id] = player.as_dict()

        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(self._playerdata))

    async def remove(self, discord_id: int):
        player = Player.from_dict(self._playerdata.pop(discord_id, None))
        if player is None:
            raise ValueError(f"Player '{discord_id}' not found.")
        if player.is_whitelisted:
            await run_command(f"whitelist remove {player.mc_username}", self.rcon_config)

        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(self._playerdata))

    def get(self, discord_id: int) -> Player | None:
        return Player.from_dict(self._playerdata.get(discord_id, None))

    def get_all(self) -> list[tuple[int, Player]]:
        return [(k, Player.from_dict(v)) for k, v in self._playerdata.items()]
