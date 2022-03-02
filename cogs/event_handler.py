import traceback

import discord
from discord.ext import commands

import database.guild
from client import ValorantStoreBot
from database.user import UpdateProfileRequired


class EventHandler(commands.Cog):
    def __init__(self, bot: ValorantStoreBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, UpdateProfileRequired):
                u = await self.bot.get_user_promised(error.original.account.user_id)
                await self.bot.update_account_profile(u, error.original.account)
            else:
                orig_error = getattr(error, "original", error)
                error_msg = ''.join(traceback.TracebackException.from_exception(orig_error).format())
                self.bot.logger.error(error_msg)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        database.Guild.get_promised(self.bot.database, guild.id)

        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    description=f"""初めまして、私はValorantのショップにある毎日ローテする４つのスキンをコマンド一つで表示するためのBOTです！ 
いちいちログインして確認するのがめんどくさいので作りました。
store, shop, ショップ 等のコマンドを入力することで取得することができます。
勿論、個人チャットでも使用可能です
サポートサーバーに参加ください！ 
http://valorant.sakura.rip/

Nice to meet you, I'm a BOT for displaying the four skins that rotate daily in Valorant's store with a single command! 
I made this because it's a pain in the ass to have to log in and check every time.
You can get the skins by typing the commands store, shop, store, etc.
Of course, it can also be used in private chat!
Join our support server! 
http://valorant.sakura.rip/""",
                    color=0xff0000)
                embed.set_author(name="Valorant store bot", url="http://valorant.sakura.rip",
                                 icon_url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")
                embed.set_thumbnail(url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")

                await channel.send(embed=embed)
                await channel.send(
                    content="言語を変更することができます！\n[言語]コマンドをご利用ください\n\nNow you can change the language!\nPlease use the\n[language] command")
                return


def setup(bot: ValorantStoreBot):
    bot.add_cog(EventHandler(bot))
