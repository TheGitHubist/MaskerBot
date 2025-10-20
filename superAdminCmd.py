import discord
import os
import json
import datetime
import random
import string
from discord.ext import commands
from config import ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID, USER_IDS_FILE, CONFIG_FILE, INFOS_FILE

class SuperAdminCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='makeCategory')
    async def make_category(self, ctx, category_name: str, admin_only: str = None):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
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

    @commands.command(name='removeCategory')
    async def remove_category(self, ctx, category_name: str):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
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

    @commands.command(name='removeAdmin')
    async def remove_admin(self, ctx, user: discord.Member):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
        # Check if member roles are set
        if not MEMBER_ROLE_ID:
            await ctx.send("Member roles must be set before using this command.")
            return

        # Check if admin roles are set
        if not ALLOWED_ROLE_ID:
            await ctx.send("Admin roles must be set before using this command.")
            return

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

    @commands.command(name='makeAdmin')
    async def make_admin(self, ctx, user: discord.Member):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
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

    @commands.command(name='displayAdminRoleHistory')
    async def display_admin_role_history(self, ctx):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
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

    @commands.command(name='setWelcomeHere')
    async def set_welcome_here(self, ctx):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
        # Check if executor has super admin role
        if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
            await ctx.send("You are not allowed to use this command.")
            return

        # Load config
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        # Set welcome channel
        config['welcome_channel'] = ctx.channel.id

        # Write back to file
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)

        # Send welcome message in the channel
        await ctx.send("Welcome channel set to this channel.")

    @commands.command(name='setRole')
    async def set_role(self, ctx, role_type: str, *, roles: str = None):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
        # Reload infos to ensure up to date
        try:
            with open(INFOS_FILE, 'r') as f:
                infos = json.load(f)
            ALLOWED_CATEGORY_ID = infos.get("allowed_category")
            ALLOWED_ROLE_ID = infos.get("admin_roles", [])
            SUPER_ADMIN_ROLE_ID = infos.get("super_admin_role")
            MEMBER_ROLE_ID = infos.get("member_roles", [])
        except Exception as e:
            print(f"Error reloading infos in setRole: {e}")

        # Check if super admin is set
        if SUPER_ADMIN_ROLE_ID is None:
            if role_type.lower() != 'superadmin':
                await ctx.send("No super admin role set. Only MM setRole superAdmin is allowed.")
                return
            # Allow anyone to set superAdmin if not set
        else:
            # Check if user is super admin
            if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
                await ctx.send("You are not allowed to use this command.")
                return

        if not roles:
            await ctx.send("Usage: MM setRole [superAdmin/admin/member] <roles>")
            return

        # Parse roles
        role_ids = []
        for part in roles.split():
            if part.startswith('<@&') and part.endswith('>'):
                role_id = int(part[3:-1])
                role = ctx.guild.get_role(role_id)
                if role:
                    role_ids.append(role.id)
            else:
                role = discord.utils.get(ctx.guild.roles, name=part)
                if role:
                    role_ids.append(role.id)

        if not role_ids:
            await ctx.send("No valid roles found.")
            return

        # Load infos
        try:
            with open(INFOS_FILE, 'r') as f:
                infos = json.load(f)
        except FileNotFoundError:
            infos = {"admin_roles": [], "super_admin_role": None, "member_roles": [], "allowed_category": None}

        if role_type.lower() == 'superadmin':
            if len(role_ids) != 1:
                await ctx.send("Super admin must be a single role.")
                return
            infos["super_admin_role"] = role_ids[0]
        elif role_type.lower() == 'admin':
            infos["admin_roles"] = role_ids
        elif role_type.lower() == 'member':
            infos["member_roles"] = role_ids
        else:
            await ctx.send("Invalid role type. Use superAdmin, admin, or member.")
            return

        # Save infos
        with open(INFOS_FILE, 'w') as f:
            json.dump(infos, f, indent=4)

        ALLOWED_CATEGORY_ID = infos.get("allowed_category")
        ALLOWED_ROLE_ID = infos.get("admin_roles", [])
        SUPER_ADMIN_ROLE_ID = infos.get("super_admin_role")
        MEMBER_ROLE_ID = infos.get("member_roles", [])

        await ctx.send(f"Set {role_type} roles successfully.")

    @commands.command(name='addRole')
    async def add_role(self, ctx, role_type: str, *, roles: str = None):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
        # Check if super admin is set
        if SUPER_ADMIN_ROLE_ID is None:
            await ctx.send("No super admin role set. Cannot use this command.")
            return

        # Check if user is super admin
        if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
            await ctx.send("You are not allowed to use this command.")
            return

        if not roles:
            await ctx.send("Usage: MM addRole [admin/member] <roles>")
            return

        # Parse roles
        role_ids = []
        for part in roles.split():
            if part.startswith('<@&') and part.endswith('>'):
                role_id = int(part[3:-1])
                role = ctx.guild.get_role(role_id)
                if role:
                    role_ids.append(role.id)
            else:
                role = discord.utils.get(ctx.guild.roles, name=part)
                if role:
                    role_ids.append(role.id)

        if not role_ids:
            await ctx.send("No valid roles found.")
            return

        # Load infos
        try:
            with open(INFOS_FILE, 'r') as f:
                infos = json.load(f)
        except FileNotFoundError:
            infos = {"admin_roles": [], "super_admin_role": None, "member_roles": [], "allowed_category": None}

        if role_type.lower() == 'admin':
            current = infos.get("admin_roles", [])
            for rid in role_ids:
                if rid not in current:
                    current.append(rid)
            infos["admin_roles"] = current
        elif role_type.lower() == 'member':
            current = infos.get("member_roles", [])
            for rid in role_ids:
                if rid not in current:
                    current.append(rid)
            infos["member_roles"] = current
        else:
            await ctx.send("Invalid role type. Use admin or member.")
            return

        # Save infos
        with open(INFOS_FILE, 'w') as f:
            json.dump(infos, f, indent=4)
        ALLOWED_CATEGORY_ID = infos.get("allowed_category")
        ALLOWED_ROLE_ID = infos.get("admin_roles", [])
        SUPER_ADMIN_ROLE_ID = infos.get("super_admin_role")
        MEMBER_ROLE_ID = infos.get("member_roles", [])

        await ctx.send(f"Added roles to {role_type} successfully.")

    @commands.command(name='removeFromRole')
    async def remove_from_role(self, ctx, role_type: str, *, roles: str = None):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
        # Check if super admin is set
        if SUPER_ADMIN_ROLE_ID is None:
            await ctx.send("No super admin role set. Cannot use this command.")
            return

        # Check if user is super admin
        if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
            await ctx.send("You are not allowed to use this command.")
            return

        if not roles:
            await ctx.send("Usage: MM removeFromRole [admin/member] <roles>")
            return

        # Parse roles
        role_ids = []
        for part in roles.split():
            if part.startswith('<@&') and part.endswith('>'):
                role_id = int(part[3:-1])
                role = ctx.guild.get_role(role_id)
                if role:
                    role_ids.append(role.id)
            else:
                role = discord.utils.get(ctx.guild.roles, name=part)
                if role:
                    role_ids.append(role.id)

        if not role_ids:
            await ctx.send("No valid roles found.")
            return

        # Load infos
        try:
            with open(INFOS_FILE, 'r') as f:
                infos = json.load(f)
        except FileNotFoundError:
            infos = {"admin_roles": [], "super_admin_role": None, "member_roles": [], "allowed_category": None}

        if role_type.lower() == 'admin':
            current = infos.get("admin_roles", [])
            infos["admin_roles"] = [rid for rid in current if rid not in role_ids]
        elif role_type.lower() == 'member':
            current = infos.get("member_roles", [])
            infos["member_roles"] = [rid for rid in current if rid not in role_ids]
        else:
            await ctx.send("Invalid role type. Use admin or member.")
            return

        # Save infos
        with open(INFOS_FILE, 'w') as f:
            json.dump(infos, f, indent=4)

        ALLOWED_CATEGORY_ID = infos.get("allowed_category")
        ALLOWED_ROLE_ID = infos.get("admin_roles", [])
        SUPER_ADMIN_ROLE_ID = infos.get("super_admin_role")
        MEMBER_ROLE_ID = infos.get("member_roles", [])

        await ctx.send(f"Removed roles from {role_type} successfully.")

    @commands.command(name='setAllowedCategory')
    async def set_allowed_category(self, ctx):
        global ALLOWED_CATEGORY_ID, ALLOWED_ROLE_ID, SUPER_ADMIN_ROLE_ID, MEMBER_ROLE_ID
        # Check if super admin is set
        if SUPER_ADMIN_ROLE_ID is None:
            await ctx.send("No super admin role set. Cannot use this command.")
            return

        # Check if user is super admin
        if not any(role.id == SUPER_ADMIN_ROLE_ID for role in ctx.author.roles):
            await ctx.send("You are not allowed to use this command.")
            return

        if not ctx.channel.category:
            await ctx.send("This channel is not in a category.")
            return

        category_id = ctx.channel.category.id

        # Load infos
        try:
            with open(INFOS_FILE, 'r') as f:
                infos = json.load(f)
        except FileNotFoundError:
            infos = {"admin_roles": [], "super_admin_role": None, "member_roles": [], "allowed_category": None}

        infos["allowed_category"] = category_id

        # Save infos
        with open(INFOS_FILE, 'w') as f:
            json.dump(infos, f, indent=4)

        ALLOWED_CATEGORY_ID = infos.get("allowed_category")
        ALLOWED_ROLE_ID = infos.get("admin_roles", [])
        SUPER_ADMIN_ROLE_ID = infos.get("super_admin_role")
        MEMBER_ROLE_ID = infos.get("member_roles", [])

        await ctx.send(f"Set allowed category to {ctx.channel.category.name}.")

async def setup(bot):
    await bot.add_cog(SuperAdminCmd(bot))
