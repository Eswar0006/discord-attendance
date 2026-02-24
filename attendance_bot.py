from flask import Flask
from threading import Thread
import os
import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, date, time
import pytz

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# =========================
# CONFIGURATION
# =========================

TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Set your bot token as an environment variable
TIMEZONE = pytz.timezone("Asia/Kolkata")  # IST

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATABASE SETUP
# =========================

conn = sqlite3.connect("attendance.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS activity (
    user_id TEXT,
    username TEXT,
    timestamp TEXT,
    activity_type TEXT
)
""")
conn.commit()

# =========================
# TRACK MESSAGE ACTIVITY
# =========================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
    INSERT INTO activity (user_id, username, timestamp, activity_type)
    VALUES (?, ?, ?, ?)
    """, (str(message.author.id), str(message.author), now, "message"))

    conn.commit()

    await bot.process_commands(message)

# =========================
# TRACK VOICE JOIN
# =========================

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    # If user joins voice channel
    if before.channel is None and after.channel is not None:

        now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

        c.execute("""
        INSERT INTO activity (user_id, username, timestamp, activity_type)
        VALUES (?, ?, ?, ?)
        """, (str(member.id), str(member), now, "voice"))

        conn.commit()

# =========================
# ATTENDANCE AFTER 6 PM
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def takeattendance(ctx):

    now = datetime.now(TIMEZONE)
    today = now.date()
    six_pm = datetime.combine(today, time(18, 0, 0))
    eight_pm = datetime.combine(today, time(20, 0, 0))
    six_pm = TIMEZONE.localize(six_pm)
    eight_pm = TIMEZONE.localize(eight_pm)

    members = [m for m in ctx.guild.members if not m.bot]

    response = f"Attendance After 6 PM ({today})\n\n"

    for member in members:
        c.execute("""
        SELECT 1 FROM activity
        WHERE user_id = ?
        AND timestamp >= ?
        LIMIT 1
        """, (str(member.id), six_pm.strftime("%Y-%m-%d %H:%M:%S")))

        record = c.fetchone()

        if record:
            status = "PRESENT"
        else:
            status = "ABSENT"

        response += f"{member.name} - {status}\n"

    await ctx.send(response)

# =========================
# RUN BOT
# =========================

keep_alive()
bot.run(TOKEN)

