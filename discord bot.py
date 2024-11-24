import discord
from discord.ext import commands
import sqlite3
import os

# Define intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent

# Initialize bot with intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Connect to the SQLite database
conn = sqlite3.connect('users.db')
c = conn.cursor()

# Create tables for user stats, recipes, and skills if they don't exist
c.execute('''DROP TABLE IF EXISTS stats''')  # This will delete the existing table
c.execute('''CREATE TABLE IF NOT EXISTS stats (
    discord_id INTEGER PRIMARY KEY,
    health INTEGER,
    mana INTEGER,
    stamina INTEGER,
    strength INTEGER,
    dexterity INTEGER,
    constitution INTEGER,
    intelligence INTEGER,
    wisdom INTEGER,
    mentality INTEGER
)''')
conn.commit()


# Register user
@bot.command()
async def register(ctx, char_name: str, skill_level: int = None):
    if skill_level is None:
        await ctx.send("Please provide a skill level. Usage: `!register <char_name> <skill_level>`")
        return
    
    discord_id = ctx.author.id
    c.execute("INSERT OR REPLACE INTO users (discord_id, char_name, skill_level) VALUES (?, ?, ?)", 
              (discord_id, char_name, skill_level))
    conn.commit()
    await ctx.send(f"{char_name} registered with skill level {skill_level}.")

# Dictionary of valid skills (strength, dexterity, and intelligence are no longer part of skills)
valid_skills = {
    "gathering": ["mining", "skinning", "logging", "harvesting", "fishing"],
    "crafting": ["weaponsmithing", "armoring", "cooking", "engineering", "alchemy", "jewelry crafting", "furnishing"],
    "processing": ["smelting", "leatherworking", "woodworking"],
    "life": ["music", "riding"],
    # Removed strength, dexterity, and intelligence from here
}

# Add a recipe
@bot.command()
async def add_recipe(ctx, recipe_name: str, required_skill: int):
    c.execute("INSERT OR REPLACE INTO recipes (name, required_skill) VALUES (?, ?)", 
              (recipe_name, required_skill))
    conn.commit()
    await ctx.send(f"Recipe '{recipe_name}' added with required skill level {required_skill}.")

# Look up a recipe and find eligible crafters
@bot.command()
async def recipe(ctx, recipe_name: str):
    c.execute("SELECT required_skill FROM recipes WHERE name=?", (recipe_name,))
    result = c.fetchone()
    if result:
        required_skill = result[0]
        c.execute("SELECT char_name FROM users WHERE skill_level >= ?", (required_skill,))
        crafters = [row[0] for row in c.fetchall()]
        if crafters:
            await ctx.send(f"Recipe '{recipe_name}' requires skill level {required_skill}. Crafters available: {', '.join(crafters)}")
        else:
            await ctx.send(f"No crafters with the required skill level for '{recipe_name}'.")
    else:
        await ctx.send("Recipe not found.")

# Command for adding skills
@bot.command()
async def add_skill(ctx, skill_name: str, level: int):
    # Convert skill_name to lowercase for case-insensitivity
    skill_name = skill_name.lower()

    # Check if the skill belongs to any category
    category_found = False
    for category, skills in valid_skills.items():
        if skill_name in skills:
            skill_category = category
            category_found = True
            break
    
    if not category_found:
        await ctx.send(f"Invalid skill '{skill_name}'. Please provide a valid skill. Valid skills are:\n"
                       f"**Gathering**: {', '.join(valid_skills['gathering'])}\n"
                       f"**Crafting**: {', '.join(valid_skills['crafting'])}\n"
                       f"**Processing**: {', '.join(valid_skills['processing'])}\n"
                       f"**Life**: {', '.join(valid_skills['life'])}")
        return

    # Store the skill and level in the database
    discord_id = ctx.author.id
    c.execute("INSERT OR REPLACE INTO skills (discord_id, skill_category, skill_name, level) VALUES (?, ?, ?, ?)", 
              (discord_id, skill_category, skill_name, level))
    conn.commit()

    await ctx.send(f"Skill '{skill_name}' in category '{skill_category}' added with level {level}.")

# Command for adding stats
@bot.command()
async def add_stat(ctx, stat_name: str, value: int):
    stat_name = stat_name.lower()

    valid_stats = ["health", "mana", "stamina", "strength", "dexterity", "constitution", "intelligence", "wisdom", "mentality"]

    if stat_name not in valid_stats:
        await ctx.send(f"Invalid stat '{stat_name}'. Valid stats are: {', '.join(valid_stats)}")
        return

    discord_id = ctx.author.id

    # Check if the stat already exists, and update if it does
    c.execute(f"SELECT * FROM stats WHERE discord_id=?", (discord_id,))
    result = c.fetchone()

    if result:
        # Update existing stat
        c.execute(f"UPDATE stats SET {stat_name}=? WHERE discord_id=?", (value, discord_id))
    else:
        # Insert new stat if user doesn't have stats
        # Initialize all stats to None initially
        c.execute("INSERT INTO stats (discord_id, health, mana, stamina, strength, dexterity, constitution, intelligence, wisdom, mentality) VALUES (?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
                  (discord_id,))
        # Now update the specific stat
        c.execute(f"UPDATE stats SET {stat_name}=? WHERE discord_id=?", (value, discord_id))

    conn.commit()

    await ctx.send(f"{stat_name.title()} set to {value}.")




# Define valid stats globally so they can be used across different commands
valid_stats = ["health", "mana", "stamina", "strength", "dexterity", "constitution", "intelligence", "wisdom", "mentality"]

# View stats command (updated to support viewing other users' profiles)
@bot.command()
async def view(ctx, user: discord.Member = None):
    # If no user is mentioned, default to the command author
    if user is None:
        user = ctx.author

    discord_id = user.id

    # Fetch user stats from the database
    c.execute("SELECT * FROM stats WHERE discord_id=?", (discord_id,))
    stats = c.fetchone()

    # Prepare stats message
    stats_message = f"Stats for {user.name}:\n"
    if stats:
        # Check if stats have all values
        for i, stat in enumerate(stats[1:], start=1):  # Skipping discord_id (index 0)
            stat_name = valid_stats[i-1]  # The stat name from the valid_stats list
            stat_value = stat if stat is not None else 'Not set'
            stats_message += f"{stat_name.capitalize()}: {stat_value}\n"
    else:
        stats_message += "No stats found.\n"

    await ctx.send(stats_message)

#allow the user to delete their profile
@bot.command()
async def delete_profile(ctx):
    """Deletes the user's profile after confirmation"""
    discord_id = ctx.author.id
    
    # Check if the user has a profile (i.e., they have stats or a registered character)
    c.execute("SELECT * FROM stats WHERE discord_id=?", (discord_id,))
    user_stats = c.fetchone()
    c.execute("SELECT * FROM users WHERE discord_id=?", (discord_id,))
    user_info = c.fetchone()

    if not user_stats and not user_info:
        await ctx.send("You don't have a profile to delete.")
        return

    # Ask for confirmation
    await ctx.send(f"Are you sure you want to delete your profile, {ctx.author.name}? This action cannot be undone. Type `confirm` to proceed.")

    # Wait for the user to confirm
    def check(message):
        return message.author == ctx.author and message.content.lower() == 'confirm'

    try:
        # Wait for user input (confirmation) for 30 seconds
        await bot.wait_for('message', check=check, timeout=30)
    except asyncio.TimeoutError:
        await ctx.send("Profile deletion timed out. No changes were made.")
        return

    # If confirmed, delete user profile from both the 'stats' and 'users' tables
    c.execute("DELETE FROM stats WHERE discord_id=?", (discord_id,))
    c.execute("DELETE FROM users WHERE discord_id=?", (discord_id,))
    c.execute("DELETE FROM skills WHERE discord_id=?", (discord_id,))

    # Commit the changes to the database
    conn.commit()

    await ctx.send(f"Your profile has been successfully deleted, {ctx.author.name}.")

#lets the owner(me) delete all profiles in the server
@bot.command()
async def delete_all_profiles(ctx):
    """Deletes all profiles in the server (for debugging purposes)"""
    # Your Discord ID (replace this with your actual Discord ID)
    owner_id = 420002871829069834  # Replace with your actual Discord ID

    if ctx.author.id != owner_id:
        await ctx.send("You do not have permission to delete all profiles.")
        return

    # Confirm action
    await ctx.send("Are you sure you want to delete all profiles in this server? This action cannot be undone. Type `confirm` to proceed.")

    # Wait for confirmation
    def check(message):
        return message.author == ctx.author and message.content.lower() == 'confirm'

    try:
        # Wait for user input (confirmation) for 30 seconds
        await bot.wait_for('message', check=check, timeout=30)
    except asyncio.TimeoutError:
        await ctx.send("Profile deletion timed out. No changes were made.")
        return

    # Delete all profiles from the 'stats', 'users', and 'skills' tables
    c.execute("DELETE FROM stats")
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM skills")

    # Commit the changes to the database
    conn.commit()

    await ctx.send("All profiles have been successfully deleted.")



# Run the bot
bot.run('MTMwNjgxNzQ1NzM2ODk5Mzg4Mg.GWLT5f.O1DX2lY5Q7uQDZZhz7vr1e6bnoG3MWx5hYn0pw')
