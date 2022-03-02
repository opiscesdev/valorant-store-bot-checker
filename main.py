import os

from dotenv import load_dotenv

from client import ValorantStoreBot

if __name__ == "__main__":
    load_dotenv()
    bot = ValorantStoreBot("")
    bot.run(os.getenv("DISCORD_TOKEN"))
