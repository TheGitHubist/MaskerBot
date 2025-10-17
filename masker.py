import discord
import os
import aiohttp
import io
import json
import random
import string
import datetime
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()

client = commands.Bot(command_prefix="MM ", intents=discord.Intents.all())

ALLOWED_CATEGORY_ID = int(os.getenv('ALLOWED_CATEGORY_ID'))
ALLOWED_ROLE_ID = [int(id.strip()) for id in os.getenv('ALLOWED_ROLE_ID').split(',')]
SUPER_ADMIN_ROLE_ID = int(os.getenv('SUPER_ADMIN_ID'))
MEMBER_ROLE_ID = int(os.getenv('MEMBER_ROLE_ID'))
USER_IDS_FILE = 'user_ids.json'

@client.check
async def global_member_check(ctx):
    # Allow if user has member role, admin role, or super admin role
    if (any(role.id == MEMBER_ROLE_ID for role in ctx.author.roles) or
        any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles) or
        any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles)):
        return True
    else:
        embed = discord.Embed(
            title="Access Denied",
            description="You don't have access to commands yet as a non-member. Please contact an admin to gain member status.",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return False

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    # Ensure user_ids.json exists
    try:
        with open(USER_IDS_FILE, 'r') as f:
            json.load(f)
    except FileNotFoundError:
        with open(USER_IDS_FILE, 'w') as f:
            json.dump({}, f, indent=4)
        print(f"Created {USER_IDS_FILE}")

@client.event
async def on_member_join(member):
    # Load existing user IDs
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        user_ids = {}

    # Generate unique user_id
    existing_ids = set()
    for data in user_ids.values():
        if isinstance(data, dict):
            existing_ids.add(data.get("user_id"))
            if data.get("admin_id"):
                existing_ids.add(data.get("admin_id"))
        elif isinstance(data, str):
            existing_ids.add(data)
    user_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    while user_id in existing_ids:
        user_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    # Determine role
    role = "admin" if any(role.id in ALLOWED_ROLE_ID for role in member.roles) else "user"
    admin_id = None
    if role == "admin":
        admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        while admin_id in existing_ids or admin_id == user_id:
            admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    # Save the data with username as key
    user_ids[str(member)] = {
        "user_id": user_id,
        "role": role,
        "admin_id": admin_id,
        "role_history": [{"role": role, "timestamp": datetime.datetime.now().isoformat()}]
    }

    # Write back to file
    with open(USER_IDS_FILE, 'w') as f:
        json.dump(user_ids, f, indent=4)

    # Create private channel for the user
    category = member.guild.get_channel(ALLOWED_CATEGORY_ID)
    if category:
        overwrites = {
            member.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            member.guild.get_role(ALLOWED_ROLE_ID[0]): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            member.guild.get_role(SUPER_ADMIN_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        try:
            await member.guild.create_text_channel(user_id, category=category, overwrites=overwrites)
            print(f"Created private channel {user_id} for {member}")
        except Exception as e:
            print(f"Error creating channel for {member}: {e}")

    print(f"Generated ID for {member}: user_id={user_id}, role={role}, admin_id={admin_id}")

@client.event
async def on_member_remove(member):
    # Load existing user IDs
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        return

    user_key = str(member)
    if user_key in user_ids:
        data = user_ids[user_key]
        user_id = data if isinstance(data, str) else data.get("user_id")
        del user_ids[user_key]
        # Write back to file
        with open(USER_IDS_FILE, 'w') as f:
            json.dump(user_ids, f, indent=4)
        print(f"Deleted data for {member}")

        # Delete private channel
        category = member.guild.get_channel(ALLOWED_CATEGORY_ID)
        if category and user_id:
            channel = discord.utils.get(category.channels, name=user_id)
            if channel:
                try:
                    await channel.delete()
                    print(f"Deleted private channel {user_id} for {member}")
                except Exception as e:
                    print(f"Error deleting channel for {member}: {e}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Don't delete messages from other bots
    if message.author.bot:
        return

    # Check if the message is in the allowed category or author has allowed role
    is_allowed = (message.channel.category and message.channel.category.id == ALLOWED_CATEGORY_ID or
                  (hasattr(message.author, 'roles') and any(role.id in ALLOWED_ROLE_ID for role in message.author.roles)))

    if is_allowed:
        # Process commands if allowed
        if message.content.startswith(client.command_prefix):
            await client.process_commands(message)
        return

    # If not allowed, delete the message
    try:
        author = message.author
        await message.delete()
        print(f"Deleted message from {message.author} in {message.channel}")
        try:
            await author.send(f"Deleted message : \n \"{message.content}\" \nin : \n{message.channel}.\nReasons : no message sent without the command :\nMM send [channel] is allowed. And only inside the allowed channel \nPlease understand.")
        except discord.HTTPException:
            pass  # DM failed, probably disabled
    except discord.Forbidden:
        print("Bot lacks permission to delete messages.")
    except discord.NotFound:
        print("Message not found or already deleted.")

@client.command(name='send')
async def send(ctx, *, args: str = None):
    if not args:
        await ctx.send("Usage: MM send [asAdmin] <channel> <message>")
        return

    # Parse arguments
    parts = args.split()
    as_admin = False
    if parts[0].lower() == 'asadmin':
        as_admin = True
        parts = parts[1:]
        if len(parts) < 2:
            await ctx.send("Usage: MM send [asAdmin] <channel> <message>")
            return

    channel_mention = parts[0]
    message = ' '.join(parts[1:])

    # Get channel from mention
    channel = discord.utils.get(ctx.guild.channels, mention=channel_mention) if ctx.guild else None
    if not channel or not isinstance(channel, discord.TextChannel):
        await ctx.send("Invalid channel.")
        return

    if channel.category and channel.category.id == ALLOWED_CATEGORY_ID:
        return

    # Get user data
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
        user_key = str(ctx.author)
        user_data = user_ids.get(user_key)
        if not user_data:
            await ctx.send("You don't have an ID. Use MM generateID first.")
            return
        user_id = user_data["user_id"]
    except Exception as e:
        await ctx.send("Error loading user IDs.")
        return

    # Determine username
    if as_admin:
        if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
            await ctx.send("You are not allowed to send as admin.")
            return
        admin_id = user_data.get("admin_id")
        if not admin_id:
            await ctx.send("You don't have an admin ID. Use MM generateID to generate one.")
            return
        username = f"admin_{admin_id}"
    else:
        username = f"user_{user_id}"

    files = []
    try:
        for attachment in ctx.message.attachments:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        return
                    data = io.BytesIO(await resp.read())
                    files.append(discord.File(data, filename=attachment.filename))
    except Exception as e:
        pass

    # Create a webhook for the channel
    try:
        avatar_bytes = await client.user.avatar.read() if client.user.avatar else None
        webhook = await channel.create_webhook(name=username, avatar=avatar_bytes)
        avatar_url = client.user.avatar.url if client.user.avatar else None
        if files:
            await webhook.send(content=message, files=files, username=username, avatar_url=avatar_url)
        else:
            await webhook.send(content=message, username=username, avatar_url=avatar_url)
        await webhook.delete()
    except discord.Forbidden:
        try:
            if files:
                await channel.send(content=message, files=files)
            else:
                await channel.send(content=message)
        except discord.Forbidden:
            pass
        except Exception as e:
            pass
    except Exception as e:
        pass

@client.command(name='generateID')
async def generate_id(ctx):
    # Load existing user IDs
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        user_ids = {}

    user_key = str(ctx.author)

    # Check current roles
    has_admin_role = any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles)

    # Generate unique IDs
    existing_ids = set()
    for data in user_ids.values():
        if isinstance(data, dict):
            existing_ids.add(data.get("user_id"))
            if data.get("admin_id"):
                existing_ids.add(data.get("admin_id"))
        elif isinstance(data, str):
            existing_ids.add(data)

    # Check if user already has data
    if user_key in user_ids:
        data = user_ids[user_key]
        updated = False
        if isinstance(data, str):
            # Old format: migrate to new
            old_user_id = data
            role = "admin" if has_admin_role else "user"
            admin_id = None
            if role == "admin":
                admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                while admin_id in existing_ids or admin_id == old_user_id:
                    admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            user_ids[user_key] = {
                "user_id": old_user_id,
                "role": role,
                "admin_id": admin_id,
                "role_history": [{"role": role, "timestamp": datetime.datetime.now().isoformat()}]
            }
            updated = True
            response = f"Your user ID is: {old_user_id}\nRole: {role}"
            if admin_id:
                response += f"\nAdmin ID: {admin_id}"
        else:
            # New format: check if role needs update
            user_id = data["user_id"]
            role = data["role"]
            admin_id = data.get("admin_id")
            role_history = data.get("role_history", [])
            if has_admin_role and role != "admin":
                role = "admin"
                if not admin_id:
                    admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                    while admin_id in existing_ids or admin_id == user_id:
                        admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                data["role"] = role
                data["admin_id"] = admin_id
                role_history.append({"role": role, "timestamp": datetime.datetime.now().isoformat()})
                data["role_history"] = role_history
                updated = True
            response = f"Your user ID is: {user_id}\nRole: {role}"
            if admin_id:
                response += f"\nAdmin ID: {admin_id}"
        if updated:
            # Write back to file
            with open(USER_IDS_FILE, 'w') as f:
                json.dump(user_ids, f, indent=4)
    else:
        # Generate new data
        user_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        while user_id in existing_ids:
            user_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        role = "admin" if has_admin_role else "user"
        admin_id = None
        if role == "admin":
            admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            while admin_id in existing_ids or admin_id == user_id:
                admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        user_ids[user_key] = {
            "user_id": user_id,
            "role": role,
            "admin_id": admin_id,
            "role_history": [{"role": role, "timestamp": datetime.datetime.now().isoformat()}]
        }
        # Write back to file
        with open(USER_IDS_FILE, 'w') as f:
            json.dump(user_ids, f, indent=4)
        response = f"Your user ID is: {user_id}\nRole: {role}"
        if admin_id:
            response += f"\nAdmin ID: {admin_id}"

    await ctx.send(response)

@client.command(name='removeAdmin')
async def remove_admin(ctx, user: discord.Member):
    # Check if executor has super admin role
    if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Check if target has super admin role
    if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
        await ctx.send("You cannot remove admin privileges from a super admin.")
        return

    # Load existing user IDs
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        await ctx.send("No user data found.")
        return

    user_key = str(user)
    if user_key not in user_ids:
        await ctx.send("User not found in database.")
        return

    data = user_ids[user_key]
    if isinstance(data, str):
        await ctx.send("User data is in old format. Please have them use MM generateID to migrate.")
        return

    if data["role"] != "admin":
        await ctx.send("User is not an admin.")
        return

    # Remove admin role from user
    admin_role = discord.utils.get(ctx.guild.roles, id=ALLOWED_ROLE_ID[0])
    if admin_role:
        try:
            await user.remove_roles(admin_role)
        except discord.Forbidden:
            await ctx.send("I lack permissions to remove roles.")
            return
        except Exception as e:
            await ctx.send("An error occurred while removing the role.")
            return

    # Change role to user and remove admin_id
    data["role"] = "user"
    data["admin_id"] = None
    role_history = data.get("role_history", [])
    role_history.append({"role": "user", "timestamp": datetime.datetime.now().isoformat()})
    data["role_history"] = role_history

    # Write back to file
    with open(USER_IDS_FILE, 'w') as f:
        json.dump(user_ids, f, indent=4)

    await ctx.send(f"Removed admin privileges from {user.mention}.")


@client.command(name='makeUser')
async def make_user(ctx, user: discord.Member):
    # Check if executor has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Check if target has super admin role
    if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
        await ctx.send("You cannot grant member role to a super admin.")
        return

    # Add member role to user
    member_role = discord.utils.get(ctx.guild.roles, id=MEMBER_ROLE_ID)
    if member_role:
        try:
            await user.add_roles(member_role)
        except discord.Forbidden:
            await ctx.send("I lack permissions to add roles.")
            return
        except Exception as e:
            await ctx.send("An error occurred while adding the role.")
            return

    # Update user data
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        await ctx.send("No user data found.")
        return

    user_key = str(user)
    if user_key not in user_ids:
        await ctx.send("User not found in database.")
        return

    data = user_ids[user_key]
    if isinstance(data, str):
        await ctx.send("User data is in old format. Please have them use MM generateID to migrate.")
        return

    # Update role to member if not already
    if data["role"] != "member":
        data["role"] = "member"
    role_history = data.get("role_history", [])
    role_history.append({"role": "member", "timestamp": datetime.datetime.now().isoformat()})
    data["role_history"] = role_history

    # Write back to file
    with open(USER_IDS_FILE, 'w') as f:
        json.dump(user_ids, f, indent=4)

    await ctx.send(f"Granted member role to {user.mention}.")


@client.command(name='warnUser')
async def warn_user(ctx, user: discord.Member):
    # Check if executor has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Check if target has super admin role
    if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
        await ctx.send("You cannot warn a super admin.")
        return

    # Get admin_id of executor
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
        user_key = str(ctx.author)
        user_data = user_ids.get(user_key)
        if not user_data or not user_data.get("admin_id"):
            await ctx.send("You don't have an admin ID.")
            return
        admin_id = user_data["admin_id"]
        # Get warned user's data
        user_key_warned = str(user)
        user_data_warned = user_ids.get(user_key_warned)
        if not user_data_warned:
            await ctx.send("Warned user not found in database.")
            return
        user_channel_name = user_data_warned["user_id"]
    except Exception as e:
        await ctx.send("Error loading user IDs.")
        return

    warning_msg = f"You have been warned by admin_{admin_id}."

    # Send in user's private channel
    category = ctx.guild.get_channel(ALLOWED_CATEGORY_ID)
    if category:
        channel = discord.utils.get(category.channels, name=user_channel_name)
        if channel:
            try:
                await channel.send(warning_msg)
            except Exception as e:
                pass

    # Send DM
    try:
        await user.send(warning_msg)
    except discord.HTTPException:
        pass

    await ctx.send(f"Warned {user.mention}.")


@client.command(name='kickUser')
async def kick_user(ctx, user: discord.Member):
    # Check if executor has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Check if target has super admin role
    if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
        await ctx.send("You cannot kick a super admin.")
        return

    try:
        await user.kick(reason="Kicked by admin")
        await ctx.send(f"Kicked {user.mention}.")
    except discord.Forbidden:
        await ctx.send("I lack permissions to kick users.")
    except Exception as e:
        await ctx.send("An error occurred while kicking the user.")


@client.command(name='banUser')
async def ban_user(ctx, user: discord.Member):
    # Check if executor has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Check if target has super admin role
    if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
        await ctx.send("You cannot ban a super admin.")
        return

    try:
        await user.ban(reason="Banned by admin")
        await ctx.send(f"Banned {user.mention}.")
    except discord.Forbidden:
        await ctx.send("I lack permissions to ban users.")
    except Exception as e:
        await ctx.send("An error occurred while banning the user.")


@client.command(name='removeMemberRole')
async def remove_member_role(ctx, user: discord.Member):
    # Check if executor has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Check if target has super admin role
    if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
        await ctx.send("You cannot remove member role from a super admin.")
        return

    # Remove member role from user
    member_role = discord.utils.get(ctx.guild.roles, id=MEMBER_ROLE_ID)
    if member_role:
        try:
            await user.remove_roles(member_role)
        except discord.Forbidden:
            await ctx.send("I lack permissions to remove roles.")
            return
        except Exception as e:
            await ctx.send("An error occurred while removing the role.")
            return

    # Update user data
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        await ctx.send("No user data found.")
        return

    user_key = str(user)
    if user_key not in user_ids:
        await ctx.send("User not found in database.")
        return

    data = user_ids[user_key]
    if isinstance(data, str):
        await ctx.send("User data is in old format. Please have them use MM generateID to migrate.")
        return

    # Update role to user if was member
    if data["role"] == "member":
        data["role"] = "user"
        role_history = data.get("role_history", [])
        role_history.append("user")
        data["role_history"] = role_history

        # Write back to file
        with open(USER_IDS_FILE, 'w') as f:
            json.dump(user_ids, f, indent=4)

    await ctx.send(f"Removed member role from {user.mention}.")


@client.command(name='displayMemberRoleHistory')
async def display_member_role_history(ctx):
    # Check if executor has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        await ctx.send("No user data found.")
        return

    embed = discord.Embed(title="Member Role History", color=0x00ff00)

    now = datetime.datetime.now()

    for user_key, data in user_ids.items():
        if isinstance(data, dict) and data.get("role_history"):
            role_history = data["role_history"]
            member_timestamps = []
            for entry in role_history:
                if isinstance(entry, dict) and entry.get("role") == "member":
                    member_timestamps.append(entry.get("timestamp"))
                elif isinstance(entry, str) and entry == "member":
                    # If old format without timestamp, skip or handle differently
                    pass
            if member_timestamps:
                # Find the earliest member timestamp
                earliest_timestamp = min(member_timestamps)
                try:
                    member_date = datetime.datetime.fromisoformat(earliest_timestamp)
                    days_since = (now - member_date).days
                    embed.add_field(name=user_key, value=f"Member since: {member_date.strftime('%Y-%m-%d %H:%M:%S')}\nDays since: {days_since}", inline=False)
                except ValueError:
                    embed.add_field(name=user_key, value="Invalid timestamp for member role", inline=False)

    await ctx.send(embed=embed)


@client.command(name='displayAdminRoleHistory')
async def display_admin_role_history(ctx):
    # Check if executor has super admin role
    if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        await ctx.send("No user data found.")
        return

    embed = discord.Embed(title="Admin Role History", color=0xff0000)

    now = datetime.datetime.now()

    for user_key, data in user_ids.items():
        if isinstance(data, dict) and data.get("role_history"):
            role_history = data["role_history"]
            admin_timestamps = []
            for entry in role_history:
                if isinstance(entry, dict) and entry.get("role") == "admin":
                    admin_timestamps.append(entry.get("timestamp"))
                elif isinstance(entry, str) and entry == "admin":
                    # If old format without timestamp, skip or handle differently
                    pass
            if admin_timestamps:
                # Find the earliest admin timestamp
                earliest_timestamp = min(admin_timestamps)
                try:
                    admin_date = datetime.datetime.fromisoformat(earliest_timestamp)
                    days_since = (now - admin_date).days
                    embed.add_field(name=user_key, value=f"Admin since: {admin_date.strftime('%Y-%m-%d %H:%M:%S')}\nDays since: {days_since}", inline=False)
                except ValueError:
                    embed.add_field(name=user_key, value="Invalid timestamp for admin role", inline=False)

    await ctx.send(embed=embed)


@client.command(name='makeAdmin')
async def make_admin(ctx, user: discord.Member):
    # Check if executor has super admin role
    if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Check if target has super admin role
    if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
        await ctx.send("You cannot grant admin privileges to a super admin.")
        return

    # Load existing user IDs
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        await ctx.send("No user data found.")
        return

    user_key = str(user)
    if user_key not in user_ids:
        await ctx.send("User not found in database.")
        return

    data = user_ids[user_key]
    if isinstance(data, str):
        await ctx.send("User data is in old format. Please have them use MM generateID to migrate.")
        return

    if data["role"] == "admin":
        await ctx.send("User is already an admin.")
        return

    # Add admin role to user
    admin_role = discord.utils.get(ctx.guild.roles, id=ALLOWED_ROLE_ID[0])
    if admin_role:
        try:
            await user.add_roles(admin_role)
        except discord.Forbidden:
            await ctx.send("I lack permissions to add roles.")
            return
        except Exception as e:
            await ctx.send("An error occurred while adding the role.")
            return

    # Generate admin_id
    existing_ids = set()
    for d in user_ids.values():
        if isinstance(d, dict):
            existing_ids.add(d.get("user_id"))
            if d.get("admin_id"):
                existing_ids.add(d.get("admin_id"))
        elif isinstance(d, str):
            existing_ids.add(d)
    admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    while admin_id in existing_ids or admin_id == data["user_id"]:
        admin_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    # Update data
    data["role"] = "admin"
    data["admin_id"] = admin_id
    role_history = data.get("role_history", [])
    role_history.append("admin")
    data["role_history"] = role_history

    # Write back to file
    with open(USER_IDS_FILE, 'w') as f:
        json.dump(user_ids, f, indent=4)

    await ctx.send(f"Granted admin privileges to {user.mention}. Admin ID: {admin_id}")


@client.command(name='purgeChannel')
async def purge_channel(ctx, *, args: str = None):
    # Check if user has allowed role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    if not args:
        # No arguments: purge all messages in current channel
        channel = ctx.channel
        try:
            messages = [msg async for msg in channel.history(limit=None)]
            if not messages:
                await ctx.send("No messages to purge in this channel.")
                return
            deleted = await channel.purge(limit=len(messages))
            await ctx.send(f"Purged {len(deleted)} messages from {channel.mention}.", delete_after=5)
        except discord.Forbidden:
            await ctx.send("I lack permissions to purge messages in this channel.")
        except Exception as e:
            await ctx.send("An error occurred while purging messages.")
        return

    # Parse arguments
    parts = args.split(maxsplit=1)
    amount_str = parts[0]
    remaining = parts[1] if len(parts) > 1 else None

    # Determine if first arg is amount or channel
    amount = None
    channel = ctx.channel  # default

    if remaining and remaining.startswith('<#') and remaining.endswith('>'):
        # First is amount, second is channel
        try:
            amount = int(amount_str)
        except ValueError:
            await ctx.send("Invalid amount. The first argument must be a positive integer if a channel is specified.")
            return
        channel_mention = remaining
        channel = discord.utils.get(ctx.guild.channels, mention=channel_mention)
        if not channel or not isinstance(channel, discord.TextChannel):
            await ctx.send("Invalid channel specified.")
            return
    else:
        # First is channel, amount is None (all messages)
        channel_mention = amount_str
        if channel_mention.startswith('<#') and channel_mention.endswith('>'):
            channel = discord.utils.get(ctx.guild.channels, mention=channel_mention)
            if not channel or not isinstance(channel, discord.TextChannel):
                await ctx.send("Invalid channel specified.")
                return
        else:
            # First is amount, no channel
            try:
                amount = int(amount_str)
            except ValueError:
                await ctx.send("Invalid amount. Must be a positive integer.")
                return
            # channel remains ctx.channel

    # Validate amount
    if amount is not None:
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

    # If amount is None, set to total messages
    if amount is None:
        try:
            messages = [msg async for msg in channel.history(limit=None)]
            amount = len(messages)
        except discord.Forbidden:
            await ctx.send("I lack permissions to read message history in this channel.")
            return
    else:
        # Cap amount to actual messages
        try:
            messages = [msg async for msg in channel.history(limit=amount)]
            actual_amount = len(messages)
            if actual_amount < amount:
                amount = actual_amount
        except discord.Forbidden:
            await ctx.send("I lack permissions to read message history in this channel.")
            return

    if amount == 0:
        await ctx.send("No messages to purge.")
        return

    # Perform purge
    try:
        deleted = await channel.purge(limit=amount)
        await ctx.send(f"Purged {len(deleted)} messages from {channel.mention}.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("I lack permissions to purge messages in this channel.")
    except discord.NotFound:
        await ctx.send("Some messages could not be found (may have been deleted already).")
    except Exception as e:
        await ctx.send("An error occurred while purging messages.")

@client.command(name='makeChannel')
async def make_channel(ctx, category_name: str, channel_name: str, *, args: str = None):
    # Check if user has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Parse optional flags
    voc = False
    admin_only = False
    if args:
        parts = args.lower().split()
        voc = 'voc' in parts
        admin_only = 'adminonly' in parts

    # Check permissions for flags
    if admin_only and not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("Only super admins can use the adminOnly flag.")
        return

    # Find category
    category = discord.utils.get(ctx.guild.categories, name=category_name)
    if not category:
        await ctx.send("Category not found.")
        return

    # Set permissions
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.guild.get_role(ALLOWED_ROLE_ID[0]): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    }

    if admin_only:
        # Restrict to admins and super admins only
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            ctx.guild.get_role(ALLOWED_ROLE_ID[0]): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            ctx.guild.get_role(SUPER_ADMIN_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

    try:
        if voc:
            channel = await ctx.guild.create_voice_channel(channel_name, category=category, overwrites=overwrites)
            await ctx.send(f"Created voice channel {channel.mention} in category {category.name}.")
        else:
            channel = await ctx.guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
            await ctx.send(f"Created text channel {channel.mention} in category {category.name}.")
    except Exception as e:
        await ctx.send(f"Error creating channel: {e}")

@client.command(name='removeChannel')
async def remove_channel(ctx, category_name: str, channel_name: str):
    # Check if user has admin role
    if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Find category
    category = discord.utils.get(ctx.guild.categories, name=category_name)
    if not category:
        await ctx.send("Category not found.")
        return

    # Find channel in category
    channel = discord.utils.get(category.channels, name=channel_name)
    if not channel:
        await ctx.send("Channel not found in that category.")
        return

    try:
        await channel.delete()
        await ctx.send(f"Removed channel {channel_name} from category {category_name}.")
    except Exception as e:
        await ctx.send(f"Error removing channel: {e}")

@client.command(name='makeCategory')
async def make_category(ctx, category_name: str, admin_only: str = None):
    # Check if user has super admin role
    if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # If admin_only flag is used, check if super admin (already checked, but redundant)
    if admin_only and admin_only.lower() == 'adminonly':
        pass  # Already super admin

    # Set permissions
    overwrites = {}  # Default: allow members

    if admin_only and admin_only.lower() == 'adminonly':
        # Restrict to admins and super admins only
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            ctx.guild.get_role(ALLOWED_ROLE_ID[0]): discord.PermissionOverwrite(view_channel=True),
            ctx.guild.get_role(SUPER_ADMIN_ROLE_ID): discord.PermissionOverwrite(view_channel=True)
        }

    try:
        category = await ctx.guild.create_category(category_name, overwrites=overwrites)
        await ctx.send(f"Created category {category.name}.")
    except Exception as e:
        await ctx.send(f"Error creating category: {e}")

@client.command(name='removeCategory')
async def remove_category(ctx, category_name: str):
    # Check if user has super admin role
    if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
        await ctx.send("You are not allowed to use this command.")
        return

    # Find category
    category = discord.utils.get(ctx.guild.categories, name=category_name)
    if not category:
        await ctx.send("Category not found.")
        return

    try:
        await category.delete()
        await ctx.send(f"Removed category {category_name}.")
    except Exception as e:
        await ctx.send(f"Error removing category: {e}")

@client.command(name='adminRequest')
async def admin_request(ctx, *, content: str = None):
    if not content:
        await ctx.send("Usage: MM adminRequest <content>")
        return

    # Check if user has member role or higher
    has_member_role = any(role.id == MEMBER_ROLE_ID for role in ctx.author.roles)
    has_admin_role = any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles)
    if not (has_member_role or has_admin_role):
        await ctx.send("You must have member role or higher to use this command.")
        return

    # Load user data
    try:
        with open(USER_IDS_FILE, 'r') as f:
            user_ids = json.load(f)
    except FileNotFoundError:
        await ctx.send("No user data found.")
        return

    user_key = str(ctx.author)
    user_data = user_ids.get(user_key)
    if not user_data or isinstance(user_data, str):
        await ctx.send("You don't have valid user data. Use MM generateID first.")
        return

    # Check weekly cooldown
    last_request = user_data.get("last_admin_request")
    if last_request:
        try:
            last_dt = datetime.datetime.fromisoformat(last_request)
            now = datetime.datetime.now()
            if (now - last_dt).days < 7:
                days_left = 7 - (now - last_dt).days
                await ctx.send(f"You can only make one admin request per week. {days_left} days left.")
                return
        except ValueError:
            pass  # Invalid timestamp, proceed

    # Get list of admins
    admins = [uk for uk, d in user_ids.items() if isinstance(d, dict) and d.get("role") == "admin"]
    if not admins:
        await ctx.send("No admins available to handle requests.")
        return

    # Select random admin
    random_admin_key = random.choice(admins)
    admin_data = user_ids[random_admin_key]
    admin_user_id = admin_data["user_id"]
    admin_id = admin_data.get("admin_id")

    # Determine requester's username
    requester_user_id = user_data["user_id"]
    if user_data.get("admin_id"):
        username = f"admin_{user_data['admin_id']}"
    else:
        username = f"user_{requester_user_id}"

    # Get admin member
    admin_member = ctx.guild.get_member_named(random_admin_key)
    if not admin_member:
        await ctx.send("Selected admin not found in guild.")
        return

    # Send DM to admin
    message = f"Admin request by {username} :\n\n{content}"
    try:
        await admin_member.send(f"```{message}```")
        await ctx.send(f"Your request have successfully sent to admin_{admin_id}")
    except discord.HTTPException:
        await ctx.send("Failed to send DM to the admin.")

    # Update last request timestamp
    user_data["last_admin_request"] = datetime.datetime.now().isoformat()
    with open(USER_IDS_FILE, 'w') as f:
        json.dump(user_ids, f, indent=4)


@client.command(name='helpDisplay')
async def help_command(ctx):
    # Determine user role
    is_super_admin = any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles)
    is_admin = any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles)
    is_member = any(role.id == MEMBER_ROLE_ID for role in ctx.author.roles)

    embed = discord.Embed(title="MaskerBot Commands", color=0x00ff00)

    if is_super_admin:
        embed.add_field(name="MM send [asAdmin] <channel> <message>", value="Send a message to a channel anonymously. Use 'asAdmin' to send as admin.", inline=False)
        embed.add_field(name="MM generateID", value="Generate or retrieve your user ID and role.", inline=False)
        embed.add_field(name="MM purgeChannel [amount] [channel]", value="Purge messages from a channel. Specify amount and/or channel.", inline=False)
        embed.add_field(name="MM makeChannel <category> <channel> [voc] [adminOnly]", value="Create a private channel in a category. Use 'voc' to create a voice channel. Use 'adminOnly' to restrict to admins only.", inline=False)
        embed.add_field(name="MM removeChannel <category> <channel>", value="Remove a channel from a category.", inline=False)
        embed.add_field(name="MM makeCategory <category> [adminOnly]", value="Create a category. Use 'adminOnly' to restrict to admins only.", inline=False)
        embed.add_field(name="MM removeCategory <category>", value="Remove a category.", inline=False)
        embed.add_field(name="MM removeAdmin <user>", value="Remove admin privileges from a user.", inline=False)
        embed.add_field(name="MM makeAdmin <user>", value="Grant admin privileges to a user.", inline=False)
        embed.add_field(name="MM makeUser <user>", value="Grant member role to a user.", inline=False)
        embed.add_field(name="MM warnUser <user>", value="Warn a user by sending a message in their private channel and DM.", inline=False)
        embed.add_field(name="MM kickUser <user>", value="Kick a user from the server.", inline=False)
        embed.add_field(name="MM banUser <user>", value="Ban a user from the server.", inline=False)
        embed.add_field(name="MM removeMemberRole <user>", value="Remove member role from a user.", inline=False)
        embed.add_field(name="MM displayMemberRoleHistory", value="Display role history for all users with roles.", inline=False)
        embed.add_field(name="MM displayAdminRoleHistory", value="Display admin role history for all users.", inline=False)
        embed.add_field(name="MM adminRequest <content>", value="Send an admin request to a random admin. Limited to one per week.", inline=False)
        embed.add_field(name="MM helpDisplay", value="Display this help message.", inline=False)
    elif is_admin:
        embed.add_field(name="MM send [asAdmin] <channel> <message>", value="Send a message to a channel anonymously. Use 'asAdmin' to send as admin.", inline=False)
        embed.add_field(name="MM generateID", value="Generate or retrieve your user ID and role.", inline=False)
        embed.add_field(name="MM purgeChannel [amount] [channel]", value="Purge messages from a channel. Specify amount and/or channel.", inline=False)
        embed.add_field(name="MM makeChannel <category> <channel> [voc]", value="Create a private channel in a category. Use 'voc' to create a voice channel.", inline=False)
        embed.add_field(name="MM removeChannel <category> <channel>", value="Remove a channel from a category.", inline=False)
        embed.add_field(name="MM makeUser <user>", value="Grant member role to a user.", inline=False)
        embed.add_field(name="MM warnUser <user>", value="Warn a user by sending a message in their private channel and DM.", inline=False)
        embed.add_field(name="MM kickUser <user>", value="Kick a user from the server.", inline=False)
        embed.add_field(name="MM banUser <user>", value="Ban a user from the server.", inline=False)
        embed.add_field(name="MM removeMemberRole <user>", value="Remove member role from a user.", inline=False)
        embed.add_field(name="MM displayMemberRoleHistory", value="Display role history for all users with roles.", inline=False)
        embed.add_field(name="MM adminRequest <content>", value="Send an admin request to a random admin. Limited to one per week.", inline=False)
        embed.add_field(name="MM helpDisplay", value="Display this help message.", inline=False)
    else:
        embed.add_field(name="MM send <channel> <message>", value="Send a message to a channel anonymously.", inline=False)
        embed.add_field(name="MM generateID", value="Generate or retrieve your user ID and role.", inline=False)
        if is_member:
            embed.add_field(name="MM adminRequest <content>", value="Send an admin request to a random admin. Limited to one per week.", inline=False)
        embed.add_field(name="MM helpDisplay", value="Display this help message.", inline=False)

    await ctx.send(embed=embed)

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Invalid command. Type `MM helpDisplay` to see available commands.")
    else:
        await ctx.send(f"An error occurred: {error}")

client.run(os.getenv('DISCORD_TOKEN'))
