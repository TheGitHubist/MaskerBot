import discord
import os
import json
import datetime
from discord.ext import commands
from config import ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID, USER_IDS_FILE, CONFIG_FILE, INFOS_FILE

class AdminCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='purgeChannel')
    async def purge_channel(self, ctx, *, args: str = None):
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

    @commands.command(name='makeChannel')
    async def make_channel(self, ctx, category_name: str, channel_name: str, *, args: str = None):
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
            print(f"Error reloading infos in makeChannel: {e}")

        # Check if member roles are set
        if not MEMBER_ROLE_ID:
            await ctx.send("Member roles must be set before using this command.")
            return

        # Parse optional flags first to determine as_admin
        voc = False
        admin_only = False
        as_admin = False
        if args:
            parts = args.lower().split()
            voc = 'voc' in parts
            admin_only = 'adminonly' in parts
            as_admin = 'asadmin' in parts

        # Check permissions: members and higher if not asAdmin, admin required for asAdmin
        has_member = any(role.id in MEMBER_ROLE_ID for role in ctx.author.roles)
        has_admin = any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles)
        if as_admin:
            if not has_admin:
                await ctx.send("You are not allowed to use the asAdmin flag.")
                return
        else:
            if not (has_member or has_admin):
                await ctx.send("You are not allowed to use this command.")
                return

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
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False)
        }

        # Add member roles to overwrites by default
        for role_id in MEMBER_ROLE_ID:
            role = ctx.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # Add admin roles to overwrites
        for role_id in ALLOWED_ROLE_ID:
            role = ctx.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        if as_admin:
            # as_admin flag doesn't change permissions in this implementation, but kept for compatibility
            pass

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

    @commands.command(name='removeChannel')
    async def remove_channel(self, ctx, category_name: str, channel_name: str):
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

    @commands.command(name='makeUser')
    async def make_user(self, ctx, user: discord.Member):
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

    @commands.command(name='warnUser')
    async def warn_user(self, ctx, user: discord.Member):
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

    @commands.command(name='kickUser')
    async def kick_user(self, ctx, user: discord.Member):
        # Check if executor has admin role
        if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
            await ctx.send("You are not allowed to use this command.")
            return

        # Check if target has super admin role
        if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
            await ctx.send("You cannot kick a super admin.")
            return

        # Delete private channel before kicking
        try:
            with open(USER_IDS_FILE, 'r') as f:
                user_ids = json.load(f)
            user_key = str(user)
            user_data = user_ids.get(user_key)
            if user_data and isinstance(user_data, dict):
                user_id = user_data["user_id"]
                category = ctx.guild.get_channel(ALLOWED_CATEGORY_ID)
                if category:
                    channel = discord.utils.get(category.channels, name=user_id)
                    if channel:
                        try:
                            await channel.delete()
                            print(f"Deleted private channel {user_id} for {user}")
                        except Exception as e:
                            print(f"Error deleting channel for {user}: {e}")
        except Exception as e:
            print(f"Error loading user data for {user}: {e}")

        try:
            await user.kick(reason="Kicked by admin")
            await ctx.send(f"Kicked {user.mention}.")
        except discord.Forbidden:
            await ctx.send("I lack permissions to kick users.")
        except Exception as e:
            await ctx.send("An error occurred while kicking the user.")

    @commands.command(name='banUser')
    async def ban_user(self, ctx, user: discord.Member):
        # Check if executor has admin role
        if not any(role.id in ALLOWED_ROLE_ID for role in ctx.author.roles):
            await ctx.send("You are not allowed to use this command.")
            return

        # Check if target has super admin role
        if any(role.id == SUPER_ADMIN_ROLE_ID for role in user.roles):
            await ctx.send("You cannot ban a super admin.")
            return

        # Delete private channel before banning
        try:
            with open(USER_IDS_FILE, 'r') as f:
                user_ids = json.load(f)
            user_key = str(user)
            user_data = user_ids.get(user_key)
            if user_data and isinstance(user_data, dict):
                user_id = user_data["user_id"]
                category = ctx.guild.get_channel(ALLOWED_CATEGORY_ID)
                if category:
                    channel = discord.utils.get(category.channels, name=user_id)
                    if channel:
                        try:
                            await channel.delete()
                            print(f"Deleted private channel {user_id} for {user}")
                        except Exception as e:
                            print(f"Error deleting channel for {user}: {e}")
        except Exception as e:
            print(f"Error loading user data for {user}: {e}")

        try:
            await user.ban(reason="Banned by admin")
            await ctx.send(f"Banned {user.mention}.")
        except discord.Forbidden:
            await ctx.send("I lack permissions to ban users.")
        except Exception as e:
            await ctx.send("An error occurred while banning the user.")

    @commands.command(name='removeMemberRole')
    async def remove_member_role(self, ctx, user: discord.Member):
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

    @commands.command(name='displayMemberRoleHistory')
    async def display_member_role_history(self, ctx):
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

async def setup(bot):
    await bot.add_cog(AdminCmd(bot))
