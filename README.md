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

# Allowed Category ID (ID of the category where private channels are created)
ALLOWED_CATEGORY_ID=123456789012345678

# Allowed Role IDs (comma-separated list of role IDs that have admin privileges)
ALLOWED_ROLE_ID=987654321098765432,876543210987654321

# Super Admin Role ID (ID of the super admin role)
SUPER_ADMIN_ID=112233445566778899

# Member Role ID (ID of the member role)
MEMBER_ROLE_ID=998877665544332211
```

**Note:** Replace the placeholder values with your actual Discord server IDs and token. You can find these by enabling Developer Mode in Discord (User Settings > Advanced > Developer Mode), then right-clicking on roles, categories, etc., to copy their IDs.

## Running the Bot

1. Ensure your virtual environment is activated (if using one).
2. Run the bot:

```bash
python masker.py
```

The bot will log in and be ready to respond to commands prefixed with `MM `.

## Usage

### Commands

- `MM send [asAdmin] <channel> <message>`: Send an anonymous message to a channel.
- `MM generateID`: Generate or retrieve your user ID and role.
- `MM makeUser <user>`: Grant member role to a user (Admin only).
- `MM warnUser <user>`: Warn a user (Admin only).
- `MM kickUser <user>`: Kick a user (Admin only).
- `MM banUser <user>`: Ban a user (Admin only).
- `MM removeMemberRole <user>`: Remove member role from a user (Admin only).
- `MM displayMemberRoleHistory`: Display role history (Admin only).
- `MM purgeChannel [amount] [channel]`: Purge messages from a channel (Admin only).
- `MM makeChannel <category> <channel> [voc] [adminOnly]`: Create a channel (Admin only).
- `MM removeChannel <category> <channel>`: Remove a channel (Admin only).
- `MM makeCategory <category> [adminOnly]`: Create a category (Super Admin only).
- `MM removeCategory <category>`: Remove a category (Super Admin only).
- `MM makeAdmin <user>`: Grant admin privileges (Super Admin only).
- `MM removeAdmin <user>`: Remove admin privileges (Super Admin only).
- `MM helpDisplay`: Display available commands based on your role.

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
