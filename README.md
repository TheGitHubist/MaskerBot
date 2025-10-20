# MaskerBot

MaskerBot is a Discord bot designed for server management, allowing users to send anonymous messages, manage roles, and perform administrative tasks. It supports role-based permissions to ensure secure operations.

## Features

- Anonymous messaging to channels
- User role management (Member, Admin, Super Admin)
- Channel and category creation/removal
- Message purging
- User warnings, kicks, and bans
- Private channels for users
- Role history tracking

## Prerequisites

- Python 3.8 or higher
- A Discord account and a bot token from the [Discord Developer Portal](https://discord.com/developers/applications)
- Server roles and category IDs (obtainable via Discord's developer mode)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd MaskerBot
```

### 2. Set Up a Virtual Environment (Recommended)

It's highly recommended to use a virtual environment to manage dependencies and avoid conflicts with system-wide packages.

```bash
# Create a virtual environment
python -m venv MaskerEnv

# Activate the virtual environment
# On Windows:
MaskerEnv\Scripts\activate
# On macOS/Linux:
source MaskerEnv/bin/activate
```

### 3. Install Dependencies

Install the required Python packages:

```bash
pip install discord.py python-dotenv
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory of the project. This file should contain your bot's configuration. Here's an example inspired by the bot's requirements:

```env
# Discord Bot Token (required)
DISCORD_TOKEN=your_discord_bot_token_here
```

**Note:** Replace the placeholder values with your actual Discord server IDs and token. You can find these by enabling Developer Mode in Discord (User Settings > Advanced > Developer Mode), then right-clicking on roles, categories, etc., to copy their IDs.

## Running the Bot

1. Ensure your virtual environment is activated (if using one).
2. Run the bot:

```bash
python masker.py
```

The bot will log in and be ready to respond to commands prefixed with `MM `.

## Setup in Discord Server

Before using the bot, you need to configure roles and categories in your Discord server. These commands must be run by someone with the appropriate permissions (Super Admin for initial setup).

### Initial Setup Commands

1. **Set Super Admin Role** (Anyone can run this if no super admin is set):
   ```
   MM setRole superAdmin <@SuperAdminRole>
   ```
   Example: `MM setRole superAdmin @SuperAdmin`

2. **Set Admin Roles** (Super Admin only):
   ```
   MM setRole admin <@AdminRole1> <@AdminRole2> ...
   ```
   Example: `MM setRole admin @Admin @Moderator`

3. **Set Member Roles** (Super Admin only):
   ```
   MM setRole member <@MemberRole1> <@MemberRole2> ...
   ```
   Example: `MM setRole member @Member @Verified`

4. **Set Allowed Category** (Super Admin only):
   ```
   MM setAllowedCategory
   ```
   Run this command in the category where private user channels should be created.

5. **Set Welcome Channel** (Super Admin only, optional):
   ```
   MM setWelcomeHere
   ```
   Run this command in the channel where welcome messages should be sent.

### Additional Setup Commands (Super Admin only)

- `MM addRole admin <@NewAdminRole>`: Add additional admin roles.
- `MM addRole member <@NewMemberRole>`: Add additional member roles.
- `MM removeFromRole admin <@RoleToRemove>`: Remove admin roles.
- `MM removeFromRole member <@RoleToRemove>`: Remove member roles.

## Usage

### Commands

#### General Commands (Available to all users)
- `MM generateID`: Generate or retrieve your user ID and role.
- `MM helpDisplay`: Display available commands based on your role.

#### Member Commands (Members and above)
- `MM send [asAdmin] <channel> <message>`: Send an anonymous message to a channel.

#### Admin Only Commands
- `MM makeUser <user>`: Grant member role to a user.
- `MM warnUser <user>`: Warn a user.
- `MM kickUser <user>`: Kick a user.
- `MM banUser <user>`: Ban a user.
- `MM removeMemberRole <user>`: Remove member role from a user.
- `MM displayMemberRoleHistory`: Display role history.
- `MM purgeChannel [amount] [channel]`: Purge messages from a channel.
- `MM makeChannel <category> <channel> [voc] [adminOnly]`: Create a channel.
- `MM removeChannel <category> <channel>`: Remove a channel.

#### Super Admin Only Commands
- `MM setRole superAdmin <@SuperAdminRole>`: Set the super admin role (initial setup).
- `MM setRole admin <@AdminRole1> <@AdminRole2> ...`: Set admin roles.
- `MM setRole member <@MemberRole1> <@MemberRole2> ...`: Set member roles.
- `MM addRole admin <@NewAdminRole>`: Add additional admin roles.
- `MM addRole member <@NewMemberRole>`: Add additional member roles.
- `MM removeFromRole admin <@RoleToRemove>`: Remove admin roles.
- `MM removeFromRole member <@RoleToRemove>`: Remove member roles.
- `MM setAllowedCategory`: Set the allowed category for private channels.
- `MM setWelcomeHere`: Set the welcome channel.
- `MM makeCategory <category> [adminOnly]`: Create a category.
- `MM removeCategory <category>`: Remove a category.
- `MM makeAdmin <user>`: Grant admin privileges.
- `MM removeAdmin <user>`: Remove admin privileges.
- `MM displayAdminRoleHistory`: Display admin role history.

### Permissions

- **User**: Basic commands like sending messages and generating ID.
- **Admin**: Additional management commands (e.g., makeUser, warnUser).
- **Super Admin**: Full access, including category management and admin role changes.

## Troubleshooting

- **Bot not responding**: Ensure the `DISCORD_TOKEN` is correct and the bot has the necessary permissions in your server.
- **Permission errors**: Check that the role IDs in `.env` match your server's roles.
- **Import errors**: Make sure all dependencies are installed in the virtual environment.

## Contributing

Feel free to submit issues or pull requests to improve the bot.

## License

This project is licensed under the MIT License.
