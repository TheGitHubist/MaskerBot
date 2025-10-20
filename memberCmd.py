import discord
import os
import aiohttp
import io
import json
import random
import string
import datetime
from discord.ext import commands
from config import ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID, USER_IDS_FILE, CONFIG_FILE, INFOS_FILE

class MemberCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='send')
    async def send(self, ctx, *, args: str = None):
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
            avatar_bytes = await self.bot.user.avatar.read() if self.bot.user.avatar else None
            webhook = await channel.create_webhook(name=username, avatar=avatar_bytes)
            avatar_url = self.bot.user.avatar.url if self.bot.user.avatar else None
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

    @commands.command(name='generateID')
    async def generate_id(self, ctx):
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

    @commands.command(name='adminRequest')
    async def admin_request(self, ctx, *, content: str = None):
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

    @commands.command(name='helpDisplay')
    async def help_command(self, ctx):
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
            print(f"Error reloading infos: {e}")

        # Determine user role
        is_owner = ctx.author == ctx.guild.owner
        is_super_admin = is_owner or (SUPER_ADMIN_ROLE_ID and any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles))
        is_admin = is_owner or any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles)
        is_member = is_owner or any(role.id in MEMBER_ROLE_ID for role in ctx.author.roles)

        print("is member:", is_member, "is admin:", is_admin, "is super admin:", is_super_admin, "for author:", ctx.author.name)

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
            embed.add_field(name="MM setWelcomeHere", value="Set this channel as the welcome channel and display the welcome message.", inline=False)
            embed.add_field(name="MM setRole <type> <roles>", value="Set roles for superAdmin, admin, or member.", inline=False)
            embed.add_field(name="MM addRole <type> <roles>", value="Add roles to admin or member.", inline=False)
            embed.add_field(name="MM removeFromRole <type> <roles>", value="Remove roles from admin or member.", inline=False)
            embed.add_field(name="MM setAllowedCategory", value="Set the category of this channel as the allowed category.", inline=False)
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

async def setup(bot):
    await bot.add_cog(MemberCmd(bot))
