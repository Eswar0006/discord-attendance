
import os
import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, date, time
import pytz
import asyncio

print("BOT FILE LOADED SUCCESSFULLY")
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
# BACKGROUND ATTENDANCE REFRESH
# =========================

@tasks.loop(minutes=5)
async def refresh_attendance():
    await bot.wait_until_ready()
    guilds = bot.guilds
    now_dt = datetime.now(TIMEZONE)
    today = now_dt.date()
    six_pm = TIMEZONE.localize(datetime.combine(today, time(18, 0, 0)))
    eight_pm = TIMEZONE.localize(datetime.combine(today, time(20, 0, 0)))
    if not (six_pm <= now_dt <= eight_pm):
        return
    for guild in guilds:
        for member in guild.members:
            if member.bot:
                continue
            # Check if user has activity in window
            c.execute("""
            SELECT 1 FROM activity
            WHERE user_id = ?
            AND timestamp >= ?
            AND timestamp <= ?
            LIMIT 1
            """, (str(member.id), six_pm.strftime("%Y-%m-%d %H:%M:%S"), eight_pm.strftime("%Y-%m-%d %H:%M:%S")))
            record = c.fetchone()
            if record:
                c.execute("""
                INSERT OR IGNORE INTO attendance (user_id, username, date, present)
                VALUES (?, ?, ?, 1)
                """, (str(member.id), str(member), today.strftime("%Y-%m-%d")))
                conn.commit()

@bot.event
async def on_ready():
    refresh_attendance.start()

# =========================
# DATABASE SETUP
# =========================

conn = sqlite3.connect("attendance.db", check_same_thread=False)
c = conn.cursor()


c.execute("""
CREATE TABLE IF NOT EXISTS activity (
    user_id TEXT,
    username TEXT,
    timestamp TEXT,
    activity_type TEXT
)
""")

# New attendance table
c.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    user_id TEXT,
    username TEXT,
    date TEXT,
    present INTEGER,
    PRIMARY KEY (user_id, date)
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

    # Only record attendance for the user who sends 'attendance'
    if message.content.strip().lower() == "attendance":
        now_dt = datetime.now(TIMEZONE)
        today = now_dt.date()
        six_pm = TIMEZONE.localize(datetime.combine(today, time(18, 0, 0)))
        eight_pm = TIMEZONE.localize(datetime.combine(today, time(20, 0, 0)))
        if six_pm <= now_dt <= eight_pm:
            c.execute("""
            INSERT OR IGNORE INTO attendance (user_id, username, date, present)
            VALUES (?, ?, ?, 1)
            """, (str(message.author.id), str(message.author), today.strftime("%Y-%m-%d")))
            conn.commit()
            await message.channel.send(f"Attendance noted : {message.author.name}")
        else:
            await message.channel.send("Attendance can only be noted between 6 PM and 8 PM.")
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
        now_dt = datetime.now(TIMEZONE)
        now = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        c.execute("""
        INSERT INTO activity (user_id, username, timestamp, activity_type)
        VALUES (?, ?, ?, ?)
        """, (str(member.id), str(member), now, "voice"))
        conn.commit()

        # Mark attendance if within 6pm-8pm
        today = now_dt.date()
        six_pm = TIMEZONE.localize(datetime.combine(today, time(18, 0, 0)))
        eight_pm = TIMEZONE.localize(datetime.combine(today, time(20, 0, 0)))
        if six_pm <= now_dt <= eight_pm:
            c.execute("""
            INSERT OR IGNORE INTO attendance (user_id, username, date, present)
            VALUES (?, ?, ?, 1)
            """, (str(member.id), str(member), today.strftime("%Y-%m-%d")))
            conn.commit()

# =========================
# ATTENDANCE AFTER 6 PM
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def takeattendance(ctx):

    now = datetime.now(TIMEZONE)
    today = now.date()
    response = f"Attendance Noted Members ({today})\n\n"
    c.execute("""
    SELECT username FROM attendance WHERE date = ? AND present = 1
    """, (today.strftime("%Y-%m-%d"),))
    records = c.fetchall()
    if records:
        for record in records:
            response += f"{record[0]}\n"
    else:
        response += "No attendance noted yet."
    await ctx.send(response)

# =========================
# RUN BOT
# =========================

bot.run(TOKEN)
