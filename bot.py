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
        try:
            guild_id = os.getenv('GUILD_ID')
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.clear_commands(guild=guild)
                print(f"Syncing commands to guild {guild_id}...")
                await self.tree.sync(guild=guild)
                print(f"Commands synced successfully to guild {guild_id}")
            else:
                print("No GUILD_ID set, syncing globally...")
                await self.tree.sync()
                print("Commands synced globally")
        except Exception as e:
            print(f"Error during setup_hook: {e}")
            print("Bot will continue but commands may not be available")

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

def load_tournaments():
    with open('tournaments.json', 'r') as f:
        return json.load(f)

def load_conflicts():
    with open('conflicts.json', 'r') as f:
        return json.load(f)

def select_judges(tournaments_data, conflicts_data, tournament, conflict_list=None, count=1):
    """Select random judges from a tournament, excluding conflicts"""
    if tournament not in tournaments_data:
        available_tournaments = ', '.join(tournaments_data)
        raise ValueError(f"Tournament '{tournament}' not found. Available tournaments: {available_tournaments}")

    available_judges = tournaments_data[tournament]["judges"].copy()

    # Filter out conflicted judges
    if conflict_list and conflict_list in conflicts_data:
        conflicted_judges = conflicts_data[conflict_list]
        available_judges = [j for j in available_judges if j not in conflicted_judges]

    if len(available_judges) < count:
        raise ValueError(f"Not enough non-conflicted judges available (need {count}, have {len(available_judges)})")

    return random.sample(available_judges, count)

async def tournament_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for tournament parameter"""
    tournaments_data = load_tournaments()
    return [
        app_commands.Choice(name=tournament.capitalize(), value=tournament)
        for tournament in tournaments_data
        if current.lower() in tournament.lower()
    ]

async def conflicts_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for conflicts parameter"""
    conflicts_data = load_conflicts()
    return [
        app_commands.Choice(name=conflict.capitalize(), value=conflict)
        for conflict in conflicts_data
        if current.lower() in conflict.lower()
    ]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.tree.command(name="generate-pairing", description="Generate a random debate pairing")

@app_commands.describe(
    panel="Whether to use a panel of 3 judges instead of 1",
    tournament="Which tournament's competitors and judges to use",
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
        # Load data once
        rankings = load_rankings()
        tournaments_data = load_tournaments()
        conflicts_data = load_conflicts()

        # Validate inputs
        if tournament not in tournaments_data:
            await interaction.response.send_message(
                f"Invalid tournament. Available: {', '.join(tournaments_data)}",
                ephemeral=True
            )
            return

        if conflicts not in conflicts_data:
            await interaction.response.send_message(
                f"Invalid conflict list. Available: {', '.join(conflicts_data)}",
                ephemeral=True
            )
            return

        # Filter rankings to only include tournament entries
        try:
            tournaments_data[tournament]["entries"]
            tournament_entries = set(tournaments_data[tournament]["entries"])
            eligible_opponents = [r for r in rankings if r['name'] in tournament_entries]
        except:
            eligible_opponents = rankings

        if not eligible_opponents:
            await interaction.response.send_message(
                "No eligible opponents found in both top 50 rankings and tournament entries.",
                ephemeral=True
            )
            return

        # Generate pairing
        opponent = random.choice(eligible_opponents)
        side = random.choice(['Aff', 'Neg'])
        opponent_side = 'Neg' if side == 'Aff' else 'Aff'

        # Select judges
        judge_count = 3 if panel else 1
        judges = select_judges(tournaments_data, conflicts_data, tournament, conflicts, judge_count)

        # Create and send embed
        embed = discord.Embed(
            title="Debate Pairing",
            color=discord.Color.blue()
        )
        embed.add_field(name=side, value=interaction.user.name, inline=True)
        embed.add_field(name=opponent_side, value=opponent['name'], inline=True)
        embed.add_field(
            name="Judges" if panel else "Judge",
            value=", ".join(judges),
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"Error: {e}")
        await interaction.response.send_message(
            f"Error: {str(e)}",
            ephemeral=True
        )

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
