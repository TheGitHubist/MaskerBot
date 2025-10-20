import discord
import os
import json
import random
import string
import datetime
import aiohttp
import io
from dotenv import load_dotenv
from discord.ext import commands
from config import USER_IDS_FILE, CONFIG_FILE, INFOS_FILE, ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID, WELCOME_MESSAGE

import memberCmd
import adminCmd
import superAdminCmd

load_dotenv()

client = commands.Bot(command_prefix="MM ", intents=discord.Intents.all())

@client.check
async def global_member_check(ctx):
    # Reload infos to ensure up to date
    try:
        with open(INFOS_FILE, 'r') as f:
            infos = json.load(f)
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
        ALLOWED_CATEGORY_ID = infos.get("allowed_category")
        ALLOWED_ROLE_ID = infos.get("admin_roles", [])
        SUPER_ADMIN_ROLE_ID = infos.get("super_admin_role")
        MEMBER_ROLE_ID = infos.get("member_roles", [])
    except Exception as e:
        print(f"Error reloading infos in global check: {e}")

    # Special case: allow setRole superadmin if no super admin role is set yet
    if ctx.command and ctx.command.name == 'setRole' and SUPER_ADMIN_ROLE_ID is None and 'superadmin' in ctx.message.content.lower():
        return True
    # Special case: allow helpDisplay for everyone
    if ctx.command and ctx.command.name == 'helpDisplay':
        return True
    # Allow if user has member role, admin role, or super admin role
    is_owner = ctx.author == ctx.guild.owner
    if is_owner or (any(role.id in MEMBER_ROLE_ID for role in ctx.author.roles) or
        any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles) or
        (SUPER_ADMIN_ROLE_ID and any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles))):
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

    # Ensure config.json exists
    try:
        with open(CONFIG_FILE, 'r') as f:
            json.load(f)
    except FileNotFoundError:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({}, f, indent=4)
        print(f"Created {CONFIG_FILE}")

    # Ensure infos.json exists and load globals
    try:
        with open(INFOS_FILE, 'r') as f:
            infos = json.load(f)
    except FileNotFoundError:
        infos = {
            "admin_roles": [],
            "super_admin_role": None,
            "member_roles": [],
            "allowed_category": None
        }
        with open(INFOS_FILE, 'w') as f:
            json.dump(infos, f, indent=4)
        print(f"Created {INFOS_FILE}")

    # Set globals
    global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
    ALLOWED_CATEGORY_ID = infos.get("allowed_category")
    ALLOWED_ROLE_ID = infos.get("admin_roles", [])
    SUPER_ADMIN_ROLE_ID = infos.get("super_admin_role")
    MEMBER_ROLE_ID = infos.get("member_roles", [])

    # Load cogs if not already loaded
    if not client.get_cog('MemberCmd'):
        await memberCmd.setup(client)
    if not client.get_cog('AdminCmd'):
        await adminCmd.setup(client)
    if not client.get_cog('SuperAdminCmd'):
        await superAdminCmd.setup(client)

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

    # Send welcome message if welcome channel is set
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        welcome_channel_id = config.get('welcome_channel')
        if welcome_channel_id:
            welcome_channel = member.guild.get_channel(welcome_channel_id)
            if welcome_channel:
                await welcome_channel.send(f"Welcome {member.mention} has joined the server!")
    except Exception as e:
        print(f"Error sending welcome message: {e}")

    # Send rules to DM and personal channel
    rules_message = f"Please send messages only using the command 'MM send [channel]' and only in your personal channel: #{user_id}"
    try:
        await member.send(rules_message)
    except discord.HTTPException:
        print(f"Could not send DM to {member}")

    # Send rules to personal channel
    if category:
        channel = discord.utils.get(category.channels, name=user_id)
        if channel:
            try:
                await channel.send(rules_message)
            except Exception as e:
                print(f"Error sending rules to personal channel for {member}: {e}")

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

        # Delete private channel first
        category = member.guild.get_channel(ALLOWED_CATEGORY_ID)
        if category and user_id:
            channel = discord.utils.get(category.channels, name=user_id)
            if channel:
                try:
                    await channel.delete()
                    print(f"Deleted private channel {user_id} for {member}")
                except Exception as e:
                    print(f"Error deleting channel for {member}: {e}")

        # Then delete the user's data
        del user_ids[user_key]
        # Write back to file
        with open(USER_IDS_FILE, 'w') as f:
            json.dump(user_ids, f, indent=4)
        print(f"Deleted data for {member}")

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

    if is_allowed or ALLOWED_CATEGORY_ID is None:
        # Process commands if allowed
        if message.content.startswith(client.command_prefix):
            await client.process_commands(message)
        return

    # If not allowed
    if ALLOWED_CATEGORY_ID is not None:
        # Delete the message and send DM
        try:
            author = message.author
            await message.delete()
            print(f"Deleted message from {message.author} in {message.channel}")
            try:
                reason = "no message sent without the command :\nMM send [channel] is allowed."
                reason += " And only inside the allowed channel"
                await author.send(f"Deleted message : \n \"{message.content}\" \nin : \n{message.channel}.\nReasons : {reason} \nPlease understand.")
            except discord.HTTPException:
                pass  # DM failed, probably disabled
        except discord.Forbidden:
            print("Bot lacks permission to delete messages.")
        except discord.NotFound:
            print("Message not found or already deleted.")
    else:
        # If no allowed category set, proceed with command if it's a command
        if message.content.startswith(client.command_prefix):
            await client.process_commands(message)

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Invalid command. Type `MM helpDisplay` to see available commands.")
    else:
        await ctx.send(f"An error occurred: {error}")

client.run(os.getenv('DISCORD_TOKEN'))
