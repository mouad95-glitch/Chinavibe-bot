import discord
import anthropic
import os
from collections import defaultdict

# ── Config
DISCORD_TOKEN   = os.environ["DISCORD_TOKEN"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]

# Channels où le bot répond (laisse vide [] pour répondre partout)
ALLOWED_CHANNELS = []

# Limite : max messages par utilisateur par jour
MAX_MESSAGES_PER_DAY = 20

# ── Setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# Compteur usage par user
usage = defaultdict(int)
histories = defaultdict(list)  # historique par user pour contexte

SYSTEM_PROMPT = """Tu es l'assistant IA de la communauté ChinaVibe — une communauté française d'achat-revente et de sourcing depuis la Chine.

Tu aides les membres sur :
- Trouver et valider des produits à revendre
- Comprendre le sourcing depuis la Chine (Guangzhou, Shenzhen, Alibaba, 1688)
- Calculer les marges et la rentabilité
- Vendre sur Vinted, Leboncoin, TikTok Shop, Shopify
- Éviter les erreurs de débutants
- Comprendre la logistique et la douane (DDP, incoterms)
- Le légal et administratif en France (auto-entrepreneur, déclarations)
- Les stratégies de vente et de négociation

Réponds en français, de manière directe et pratique. Pas de blabla inutile. Donne des conseils concrets que le membre peut appliquer immédiatement.
Si la question ne concerne pas l'achat-revente ou le business, réponds quand même mais reste focus sur l'utilité pour le membre."""


@client.event
async def on_ready():
    print(f"✅ Bot connecté : {client.user}")


@client.event
async def on_message(message):
    # Ignore les messages du bot lui-même
    if message.author == client.user:
        return

    # Vérifie si le bot est mentionné ou si le channel est autorisé
    bot_mentioned = client.user in message.mentions
    in_allowed_channel = (
        not ALLOWED_CHANNELS or
        message.channel.id in ALLOWED_CHANNELS or
        message.channel.name in ALLOWED_CHANNELS
    )

    if not (bot_mentioned or in_allowed_channel):
        return

    user_id = str(message.author.id)
    user_name = message.author.display_name

    # Vérifie la limite d'usage
    if usage[user_id] >= MAX_MESSAGES_PER_DAY:
        await message.reply(
            f"⚠️ Tu as atteint ta limite de {MAX_MESSAGES_PER_DAY} questions aujourd'hui. "
            f"Reviens demain ! 🔄"
        )
        return

    # Nettoie le message (enlève la mention du bot)
    user_text = message.content.replace(f"<@{client.user.id}>", "").strip()

    if not user_text:
        await message.reply("Pose-moi une question sur l'achat-revente ou le sourcing Chine ! 🇨🇳")
        return

    # Affiche "en train d'écrire..."
    async with message.channel.typing():

        # Ajoute au contexte de l'utilisateur (max 6 derniers échanges)
        histories[user_id].append({"role": "user", "content": user_text})
        if len(histories[user_id]) > 12:
            histories[user_id] = histories[user_id][-12:]

        try:
            response = ai.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                messages=histories[user_id]
            )

            reply_text = response.content[0].text

            # Sauvegarde la réponse dans l'historique
            histories[user_id].append({"role": "assistant", "content": reply_text})

            # Incrémente le compteur
            usage[user_id] += 1
            restant = MAX_MESSAGES_PER_DAY - usage[user_id]

            # Discord limite à 2000 caractères par message
            if len(reply_text) > 1900:
                # Découpe en plusieurs messages
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
            await message.reply("❌ Une erreur s'est produite. Réessaie dans quelques secondes.")
            print(f"Erreur API : {e}")


client.run(DISCORD_TOKEN)
