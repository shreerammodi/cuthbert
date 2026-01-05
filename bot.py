import csv
import json
import os
import random

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

class PairingBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # For faster testing, sync to a specific guild (replace with your server ID)
        guild = discord.Object(id=os.getenv('GUILD_ID'))
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)

        # Global sync (slower but works everywhere)
        # await self.tree.sync()

bot = PairingBot()

def load_rankings():
    debaters = []
    with open('rankings.csv', 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 50:
                break
            debaters.append({
                'rank': row['Rank'],
                'school': row['School'],
                'name': row['Name'],
                'rating': row['Rating']
            })
    return debaters

def load_judges():
    with open('judges.json', 'r') as f:
        return json.load(f)

def load_conflicts():
    with open('conflicts.json', 'r') as f:
        return json.load(f)

def select_judges(tournament, conflict_list=None, count=1):
    """Select random judges from a tournament, excluding conflicts"""
    judges_data = load_judges()
    conflicts_data = load_conflicts()

    if tournament not in judges_data:
        available_tournaments = ', '.join(judges_data.keys())
        raise ValueError(f"Tournament '{tournament}' not found. Available tournaments: {available_tournaments}")

    available_judges = judges_data[tournament].copy()

    # Filter out conflicted judges
    if conflict_list and conflict_list in conflicts_data:
        conflicted_judges = conflicts_data[conflict_list]
        available_judges = [j for j in available_judges if j not in conflicted_judges]

    if len(available_judges) < count:
        raise ValueError(f"Not enough non-conflicted judges available (need {count}, have {len(available_judges)})")

    # Select random judges without replacement
    return random.sample(available_judges, count)

async def tournament_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for tournament parameter"""
    judges_data = load_judges()
    tournaments = list(judges_data.keys())
    return [
        app_commands.Choice(name=tournament.capitalize(), value=tournament)
        for tournament in tournaments
        if current.lower() in tournament.lower()
    ]

async def conflicts_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for conflicts parameter"""
    conflicts_data = load_conflicts()
    conflict_lists = list(conflicts_data.keys())
    return [
        app_commands.Choice(name=conflict.capitalize(), value=conflict)
        for conflict in conflict_lists
        if current.lower() in conflict.lower()
    ]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.tree.command(name="generate-pairing", description="Generate a random debate pairing")

@app_commands.describe(
    panel="Whether to use a panel of 3 judges instead of 1",
    tournament="Which tournament's judges to use",
    conflicts="Which conflict list to apply"
)

@app_commands.autocomplete(
    tournament=tournament_autocomplete,
    conflicts=conflicts_autocomplete
)

async def generate_pairing(
    interaction: discord.Interaction,
    panel: bool = False,
    tournament: str = "emory",
    conflicts: str = "om"
):
    try:
        # Load data
        rankings = load_rankings()
        judges_data = load_judges()
        conflicts_data = load_conflicts()

        # Get available options for autocomplete
        available_tournaments = list(judges_data.keys())
        available_conflicts = list(conflicts_data.keys())

        # Validate tournament
        if tournament not in available_tournaments:
            await interaction.response.send_message(
                f"Invalid tournament. Available: {', '.join(available_tournaments)}",
                ephemeral=True
            )
            return

        # Validate conflicts if provided
        if conflicts and conflicts not in available_conflicts:
            await interaction.response.send_message(
                f"Invalid conflict list. Available: {', '.join(available_conflicts)}",
                ephemeral=True
            )
            return

        # Generate pairing
        opponent = random.choice(rankings)
        side = random.choice(['Aff', 'Neg'])
        opponent_side = 'Neg' if side == 'Aff' else 'Aff'

        judge_count = 3 if panel else 1
        judges = select_judges(tournament, conflicts, judge_count)

        # Format the message as an embed
        judge_label = "Judges" if len(judges) > 1 else "Judge"
        judge_list = ", ".join(judges)

        embed = discord.Embed(
            title="Debate Pairing",
            color=discord.Color.blue()
        )
        embed.add_field(name=side, value=interaction.user.name, inline=True)
        embed.add_field(name=opponent_side, value=opponent['name'], inline=True)
        embed.add_field(name=judge_label, value=judge_list, inline=False)

        # Respond in the current channel with the embed
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"Error: {e}")
        await interaction.response.send_message(
            f"Error: {str(e)}",
            ephemeral=True
        )

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
