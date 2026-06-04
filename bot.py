import discord
import os
import json
import urllib.request
from collections import defaultdict

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

ALLOWED_CHANNELS = []
MAX_MESSAGES_PER_DAY = 20

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

usage = defaultdict(int)
histories = defaultdict(list)

SYSTEM_PROMPT = """Tu es l'assistant IA de la communauté ChinaVibe. Tu aides les membres sur l'achat-revente, le sourcing depuis la Chine, les marges, Vinted, Leboncoin, TikTok Shop, Shopify, la logistique DDP, le légal et administratif en France. Réponds en français, de manière directe et pratique."""

def ask_claude(messages):
    data = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": messages
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["content"][0]["text"]

@client.event
async def on_ready():
    print(f"Bot connecte : {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    bot_mentioned = client.user in message.mentions
    in_allowed_channel = (
        not ALLOWED_CHANNELS or
        message.channel.id in ALLOWED_CHANNELS or
        message.channel.name in ALLOWED_CHANNELS
    )

    if not (bot_mentioned or in_allowed_channel):
        return

    user_id = str(message.author.id)
    user_text = message.content.replace(f"<@{client.user.id}>", "").strip()

    if not user_text:
        await message.reply("Pose-moi une question sur l'achat-revente ou le sourcing Chine !")
        return

    if usage[user_id] >= MAX_MESSAGES_PER_DAY:
        await message.reply(f"Tu as atteint ta limite de {MAX_MESSAGES_PER_DAY} questions aujourd'hui. Reviens demain !")
        return

    async with message.channel.typing():
        histories[user_id].append({"role": "user", "content": user_text})
        if len(histories[user_id]) > 12:
            histories[user_id] = histories[user_id][-12:]

        try:
            reply_text = ask_claude(histories[user_id])
            histories[user_id].append({"role": "assistant", "content": reply_text})
            usage[user_id] += 1
            restant = MAX_MESSAGES_PER_DAY - usage[user_id]

            if len(reply_text) > 1900:
                parts = [reply_text[i:i+1900] for i in range(0, len(reply_text), 1900)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await message.reply(part)
                    else:
                        await message.channel.send(part)
                await message.channel.send(f"*— {restant} questions restantes aujourd'hui*")
            else:
                await message.reply(f"{reply_text}\n\n*— {restant} questions restantes aujourd'hui*")

        except Exception as e:
            await message.reply("Une erreur s'est produite. Reessaie dans quelques secondes.")
            print(f"Erreur : {e}")

client.run(DISCORD_TOKEN)
