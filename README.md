# Radical Bot

## Features
- **Manage the Minecraft server process**
    - **Start/stop the server**
    - **Update the server**
    - **Restart the server**
    - **Delete the server**
    - **Run commands on the server**
- **Manage Minecraft server backups**
    - **Automatically enable RCON and sign EULA**
    - **Create backups**
    - **Restore backups**
    - **Automatically create backups on a timer**
    - **Listing backups**
    - **Delete backups**
    - **Upload backups to DigitalOcean**
- Manage Minecraft server config
    - Get current config files
    - Replace config files remotely
- **Manage Server Profiles**
    - **Link Discord accounts w/ Minecraft accounts**
    - **Whitelist users**
    - **Trust users**
    - **Automatically create MC server teams**
    - **Synchronize profiles from Discord with the MC server**
- Manage Minecraft server plugins
    - Plugin addition/removal
    - Plugin updating
    - List plugins
- Manage Minecraft server datapacks
    - List datapacks
    - Datapack addition/removal
    - Datapack updating
- Manage Minecraft modpack
    - post updates
    - get link

To-Do:
    - Refactor backups to use class objects
    - Refactor command handling back into cogs; remove optional interaction parameter; simplify code
    - Automatic backups aren't running? Why?
    - Warn players when server is shutting off... delay (can be overridden)

Future Plans?
- Multi-world support?
    - Similar to Realms functionality?