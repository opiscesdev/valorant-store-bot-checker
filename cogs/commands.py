import asyncio
import collections
import random
from datetime import timedelta, datetime
from typing import Union, Callable, Dict, List

import discord
import pytz
from discord import Interaction
from discord.embeds import EmptyEmbed
from discord.ext import commands
from discord.ext.commands import Context

from client import ValorantStoreBot
from database import User, Weapon, Guild, SkinLog
from database.user import RiotAccount
from sqlalchemy import func as sqlalchemy_func

from valclient.auth import InvalidCredentialError, RateLimitedError


class CommandsHandler(commands.Cog):
    def __init__(self, bot: ValorantStoreBot):
        self.bot = bot

    @commands.command("help", aliases=["ヘルプ"])
    async def help_message(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        with open(user.get_text("assets/help_ja.txt", "assets/help_en.txt"), encoding="utf-8") as f:
            await ctx.send(f.read())

    async def list_account_and_execute(self, ctx: Context, func: Callable):
        user = User.get_promised(self.bot.database, ctx.message.author.id)

        view = discord.ui.View(timeout=60)
        accounts = user.riot_accounts
        if len(accounts) == 0:
            await ctx.send(user.get_text("アカウント情報が登録されていません\n[登録]コマンドを利用して登録してください",
                                         "Your account information has not been registered yet \nAdd your account information using the [register] command."))
            return
        if len(accounts) == 1:
            async def interaction_handler(*args, **kwargs):
                content = kwargs.get("content")
                if content is not None:
                    await ctx.send(content=kwargs.get("content"))

            if not accounts[0]._game_name:
                await ctx.send(user.get_text("登録されている情報を更新しています....", "updating the registered information"))
                await self.bot.update_account_profile(user, accounts[0])
            await func(view)(type("Interaction", (object,), {
                "data": {"values": [accounts[0].game_name]},
                "user": type("User", (object,), {"id": ctx.message.author.id}),
                "response": type("InteractionResponse", (object,), {"send_message": interaction_handler})
            }))
            return
        for acc in accounts:
            if not acc._game_name:
                await ctx.send(user.get_text("登録されている情報を更新しています....", "updating the registered information"))
                await self.bot.update_account_profile(user, acc)

        menu = discord.ui.Select(options=[
            discord.SelectOption(
                label=account.game_name
            ) for account in accounts
        ])

        menu.callback = func(view)
        view.add_item(menu)
        await ctx.send(content=user.get_text("実行するアカウント情報を選択してください", "Select the account to execute"),
                       view=view)
        await view.wait()

    @commands.command("ranking", aliases=["ランキング"])
    async def skin_ranking(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        logs: List[SkinLog] = self.bot.database.query(SkinLog).filter(
            sqlalchemy_func.DATE(SkinLog.date) == datetime.today().date()).all()
        if len(logs) == 0:
            await ctx.send(user.get_text(
                "まだ今日は誰もBOTを利用していないようです。データが見つかりませんでした。",
                "No one seems to be using the BOT today yet. No data was found."
            ))
            return
        data = [log.skin_uuid for log in logs]
        skin_data, _ = zip(*collections.Counter(data).most_common())
        await self._send_store_content(skin_data[:4], user, ctx)

    @commands.command("autosend", aliases=["自動送信"])
    async def setup_auto_send(self, ctx: Context):

        def wrapper(view: discord.ui.View):
            async def select_auto_send_time(interaction: Interaction):
                await interaction.response.send_message(content="processing your request....wait a moment...")
                account: RiotAccount = self.bot.database.query(RiotAccount).filter(
                    RiotAccount._game_name == interaction.data["values"][0]).first()
                user = User.get_promised(self.bot.database, ctx.message.author.id)
                if not user.is_premium:
                    await ctx.send(user.get_text("この機能はプレミアムユーザー限定です。\n詳細は「プレミアム」コマンドを参照してください",
                                                 "This feature is only available to Premium users.\ntype [premium] commands for details"))
                    view.stop()
                    return

                def message_check(msg: discord.Message):
                    if msg.channel.id != ctx.channel.id:
                        return False
                    if msg.author.id != ctx.message.author.id:
                        return False
                    return True

                await ctx.send(user.get_text(
                    "https://ja.wikipedia.org/wiki/ISO_3166-1\nこの一覧から、住んでいる国のうちAlpha-2の２文字のアルファベットをコピーして送信してください。日本はJPです。",
                    "https://wikipedia.org/wiki/ISO_3166-1\nFrom this list, please copy the two letters of the Alpha-2 alphabet from the country you live in and send it to us. Japan is JP."))
                try:
                    iso = await self.bot.wait_for("message", check=message_check, timeout=60)
                except asyncio.TimeoutError:
                    view.stop()
                    return
                try:
                    timezone = pytz.country_timezones(iso.content)[0]
                except (KeyError, IndexError):
                    await ctx.send(user.get_text("国コードが見つかりませんでした。\n再度「autosend」コマンドをお試しください。",
                                                 "The country code was not found. \nPlease try the [autosend] command again."))
                    view.stop()
                    return
                await ctx.send(user.get_text("何時にストアの内容を送信すればよろしいですか？0~23の間で答えてください。",
                                             "What time should I send the contents of your store?\nPlease answer between 0 and 23."))

                def message_check_hour(msg: discord.Message):
                    if msg.channel.id != ctx.channel.id:
                        return False
                    if msg.author.id != ctx.message.author.id:
                        return False
                    try:
                        minute = int(msg.content)
                    except ValueError:
                        return False
                    if 0 <= minute <= 23:
                        return True
                    return False

                try:
                    time = await self.bot.wait_for("message", check=message_check_hour, timeout=60)
                except asyncio.TimeoutError:
                    view.stop()
                    return

                user.auto_notify_at = int(time.content)
                user.auto_notify_timezone = timezone
                user.auto_notify_account = account
                self.bot.database.commit()
                view.stop()
                await ctx.send(user.get_text(
                    f"時刻を{timezone}の{time.content}時に設定しました。\n現在時刻は{datetime.now().astimezone(pytz.timezone(timezone))}です。",
                    f"set the time to {time.content} hour in {timezone}.\nThe current time is {datetime.now().astimezone(pytz.timezone(timezone))}."))

            return select_auto_send_time

        await self.list_account_and_execute(ctx, wrapper)

    @commands.command("gopremium")
    async def make_target_premium(self, ctx: Context, month: str = "1"):
        if ctx.message.author.id not in self.bot.admins:
            return
        mentioned_ids = [user.id for user in ctx.message.mentions]
        for user_id in mentioned_ids:
            user = User.get_promised(self.bot.database, user_id)
            if not month.isdigit():
                month = "1"
            if not user.is_premium:
                user.premium_until = datetime.now() + timedelta(days=31 * int(month))
            else:
                user.premium_until += timedelta(days=31 * int(month))
            user.is_premium = True
        self.bot.database.commit()
        await ctx.send(f"Congratulations! now a premium user: {len(mentioned_ids)}")

    @commands.command("unpremium")
    async def un_premium(self, ctx: Context):
        if ctx.message.author.id not in self.bot.admins:
            return
        mentioned_ids = [user.id for user in ctx.message.mentions]
        for user_id in mentioned_ids:
            user = User.get_promised(self.bot.database, user_id)
            user.is_premium = False
            user.premium_until = None
        self.bot.database.commit()
        await ctx.send(f"now not a premium user: {len(mentioned_ids)}")

    @commands.command("onlyhere", aliases=["コマンド制限"])
    @commands.has_permissions(administrator=True)
    async def response_only_this_channel(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        guild = Guild.get_promised(self.bot.database, ctx.guild.id)
        guild.response_here = ctx.channel.id
        self.bot.database.commit()
        await ctx.send(user.get_text(f"<#{guild.response_here}> のみでBOTがshopコマンドに反応するように設定しました。[everywhere]コマンドで解除できます",
                                     f"<#{guild.response_here}> only set the BOT to respond to the shop command.\nThis can be deactivated with the [everywhere] command"))

    @commands.command("everywhere", aliases=["コマンド解放"])
    @commands.has_permissions(administrator=True)
    async def response_only_this_channel(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        guild = Guild.get_promised(self.bot.database, ctx.guild.id)
        guild.response_here = None
        self.bot.database.commit()
        await ctx.send(user.get_text(f"すべての場所でBOTがshopコマンドに反応するように設定しました。",
                                     "All locations have been set up so that the BOT responds to shop commands."))

    @commands.command("rank", aliases=["ランク"])
    async def get_account_rank(self, ctx: Context):

        def wrapper(view: discord.ui.View):
            async def select_account_region(interaction: Interaction):
                await interaction.response.send_message(content="processing your request....wait a moment...")
                account: RiotAccount = self.bot.database.query(RiotAccount).filter(
                    RiotAccount._game_name == interaction.data["values"][0]).first()
                user = User.get_promised(self.bot.database, ctx.message.author.id)
                cl = await self.bot.login_valorant(user, account)
                if not cl:
                    view.stop()
                    return
                tier = await self.bot.run_blocking_func(self.bot.get_valorant_rank_tier, cl)
                await ctx.send(tier)

            return select_account_region

        await self.list_account_and_execute(ctx, wrapper)

    @commands.command("list", aliases=["リスト"])
    async def list_accounts(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        if len(user.riot_accounts) == 0:
            await ctx.send(user.get_text("アカウント情報が登録されていません\n[登録]コマンドを利用して登録してください",
                                         "Your account information has not been registered yet \nAdd your account information using the [register] command."))
            return
        await ctx.send("\n".join([account.game_name for account in user.riot_accounts]))

    @commands.command("update", aliases=["登録更新"])
    async def update_account(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        if not isinstance(ctx.message.channel, discord.channel.DMChannel) or ctx.message.author == self.bot.user:
            await ctx.send(user.get_text("この動作は個人チャットでする必要があります。", "This action needs to be done in private chat"))
            return
        if len(user.riot_accounts) == 0:
            await ctx.send(user.get_text("アカウント情報が登録されていません\n[登録]コマンドを利用して登録してください",
                                         "Your account information has not been registered yet \nAdd your account information using the [register] command."))
            return
        await self.unregister_riot_account(ctx)
        await self.register_riot_user_internal(ctx.message.author)

    async def _execute_shop_command_on_allowed_channel(self, ctx: Context, wrapper: Callable):
        if isinstance(ctx.message.channel, discord.channel.DMChannel) and ctx.message.author != self.bot.user:
            await self.list_account_and_execute(ctx, wrapper)
            return

        guild = Guild.get_promised(self.bot.database, ctx.guild.id)
        if guild.response_here and ctx.channel.id != guild.response_here:
            return
        await self.list_account_and_execute(ctx, wrapper)

    @commands.command("nightmarket", aliases=["ナイトストア"])
    async def fetch_night_market(self, ctx: Context):
        def wrapper(view: discord.ui.View):
            async def select_account_region(interaction: Interaction):
                await interaction.response.send_message(content="processing your request....wait a moment...")
                account: RiotAccount = self.bot.database.query(RiotAccount).filter(
                    RiotAccount._game_name == interaction.data["values"][0]).first()
                user = User.get_promised(self.bot.database, interaction.user.id)
                get_span = 20 if user.is_premium else 360
                if account.last_get_night_shops_at and account.last_get_night_shops_at + timedelta(
                        minutes=get_span) >= datetime.now():
                    await ctx.send(user.get_text(
                        f"最後に取得してから{get_span}分経過していません。{get_span}分に一度のみこのコマンドを実行可能です。",
                        f"It has not been {get_span} minutes since the last acquisition. this command can only be executed once every {get_span} minutes."))
                    return
                account.last_get_night_shops_at = datetime.now()
                self.bot.database.commit()
                cl = await self.bot.login_valorant(user, account)
                if not cl:
                    view.stop()
                    return
                offers = await self.bot.run_blocking_func(cl.store_fetch_storefront)
                if len(offers.get("BonusStore", {}).get("BonusStoreOffers", [])) == 0:
                    await ctx.send(user.get_text(
                        "ショップの内容が見つかりませんでした。Valorantがメンテナンス中もしくは何かの障害の可能性があります。\nそのどちらでもない場合は開発者までご連絡ください。\nhttp://valorant.sakura.rip",
                        "The contents of the store could not be found, Valorant may be under maintenance or there may be some kind of fault. \nIf it is neither of those, please contact the developer.: \nhttp://valorant.sakura.rip"))
                await self._send_night_store_content(offers, user, ctx)
                view.stop()

            return select_account_region

        await self._execute_shop_command_on_allowed_channel(ctx, wrapper)

    async def _send_night_store_content(self, offers: Dict, user: User, ctx: Context):
        for offer in offers.get("BonusStore", {}).get("BonusStoreOffers", []):
            skin = Weapon.get_promised(self.bot.database, offer["Offer"]["Rewards"][0]["ItemID"], user)
            embed = discord.Embed(title=skin.display_name, color=0xff0000,
                                  url=skin.streamed_video if skin.streamed_video else EmptyEmbed,
                                  description=user.get_text(
                                      f'{list(offer["Offer"]["Cost"].values())[0]}→{list(offer["DiscountCosts"].values())[0]}({offer["DiscountPercent"]}%off) ',
                                      f'{list(offer["Offer"]["Cost"].values())[0]}→{list(offer["DiscountCosts"].values())[0]}({offer["DiscountPercent"]}%off) ') if skin.streamed_video else EmptyEmbed)
            embed.set_author(name="valorant shop",
                             icon_url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")
            embed.set_image(url=skin.display_icon)
            await ctx.send(embed=embed)

    @commands.command("shop", aliases=["store", "ショップ", "ストア"])
    async def fetch_today_shop(self, ctx: Context):
        def wrapper(view: discord.ui.View):
            async def select_account_region(interaction: Interaction):
                await interaction.response.send_message(content="processing your request....wait a moment...")
                account: RiotAccount = self.bot.database.query(RiotAccount).filter(
                    RiotAccount._game_name == interaction.data["values"][0]).first()
                user = User.get_promised(self.bot.database, interaction.user.id)
                get_span = 10 if user.is_premium else 180
                if account.last_get_shops_at and account.last_get_shops_at + timedelta(
                        minutes=get_span) >= datetime.now():
                    await ctx.send(user.get_text(
                        f"最後に取得してから{get_span}分経過していません。{get_span}分に一度のみこのコマンドを実行可能です。",
                        f"It has not been {get_span} minutes since the last acquisition. this command can only be executed once every {get_span} minutes."))
                    return

                account.last_get_shops_at = datetime.now()
                self.bot.database.commit()
                cl = await self.bot.login_valorant(user, account)
                if not cl:
                    account.last_get_shops_at = None
                    self.bot.database.commit()
                    view.stop()
                    return
                offers = await self.bot.run_blocking_func(cl.store_fetch_storefront)
                user = User.get_promised(self.bot.database, ctx.message.author.id)
                skins_uuids = offers.get("SkinsPanelLayout", {}).get("SingleItemOffers", [])
                if len(skins_uuids) == 0:
                    await ctx.send(user.get_text(
                        "ショップの内容が見つかりませんでした。Valorantがメンテナンス中もしくは何かの障害の可能性があります。\nそのどちらでもない場合は開発者までご連絡ください。\nhttp://valorant.sakura.rip",
                        "The contents of the store could not be found, Valorant may be under maintenance or there may be some kind of fault. \nIf it is neither of those, please contact the developer.: \nhttp://valorant.sakura.rip"))

                if offers.get("BonusStore") is not None:
                    await ctx.send(user.get_text("ナイトマーケットが開かれています！\n`nightmarket`, `ナイトストア`コマンドで確認しましょう！",
                                                 "The night market is open.！\nLet's check it with the command `nightmarket`, `ナイトストア`"))
                await self._send_store_content(skins_uuids, user, ctx)

                if self.bot.database.query(SkinLog).filter(
                        sqlalchemy_func.DATE(SkinLog.date) == datetime.today().date(),
                        SkinLog.account_puuid == account.puuid).count() == 0:
                    logs = [SkinLog(account_puuid=account.puuid,
                                    date=datetime.today().date(), skin_uuid=uuid) for uuid in skins_uuids]
                    self.bot.database.add_all(logs)
                    self.bot.database.commit()

                view.stop()

            return select_account_region

        await self._execute_shop_command_on_allowed_channel(ctx, wrapper)

    async def _send_store_content(self, offers: List[str], user: User, ctx: Context):
        for offer_uuid in offers:
            skin = Weapon.get_promised(self.bot.database, offer_uuid, user)

            embed = discord.Embed(title=skin.display_name, color=0xff0000,
                                  url=skin.streamed_video if skin.streamed_video else EmptyEmbed,
                                  description=user.get_text("↑から動画が見れます",
                                                            "You can watch the video at↑") if skin.streamed_video else EmptyEmbed)
            embed.set_author(name="valorant shop",
                             icon_url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")
            embed.set_image(url=skin.display_icon)
            await ctx.send(embed=embed)

    @commands.command("randommap", aliases=["ランダムマップ"])
    async def random_map(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        if user.language == "ja-JP":
            maps = ["アセント", "スプリット", "バインド", "ブリーズ", "アイスボックス", "ヘイブン", "フラクチャー"]
        else:
            maps = ["Icebox", "Breeze", "Ascent", "Haven", "Split", "Bind", "Fracture"]
        await ctx.send(random.choice(maps))

    @commands.command("language", aliases=["lang", "言語"])
    async def change_language(self, ctx: Context):
        view = discord.ui.View(timeout=60)

        def button_pushed_lang(lang: str):
            async def button_pushed(interaction: Interaction):
                db_user = User.get_promised(self.bot.database, interaction.user.id)
                db_user.language = lang
                self.bot.database.commit()
                await interaction.channel.send(db_user.get_text("更新しました", "updated"))

            return button_pushed

        en_button = discord.ui.Button(label="English")
        en_button.callback = button_pushed_lang("en-US")

        ja_button = discord.ui.Button(label="日本語")
        ja_button.callback = button_pushed_lang("ja-JP")

        view.add_item(en_button)
        view.add_item(ja_button)
        await ctx.send(content="JA) ご自身の使用している言語を選択してください\nEN) Select the language you are using", view=view)

    @commands.command("premium", aliases=["プレミアム"])
    async def get_premium_details(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        embed = discord.Embed(title=user.get_text("プレミアムユーザーの詳細", "Premium User Details"),
                              description=user.get_text(
                                  "Valorant store botの利用者は、プレミアムユーザーになることで以下の特典を得ることができます(月額500円. paypay/linepay/paypal/btc/ltc)",
                                  "Users of the Valorant store bot can get the following benefits by becoming a premium user(5USD/month, paypal/btc/ltc)"),
                              color=0x800000)
        embed.set_author(name="valorant store bot", url="http://valorant.sakura.rip",
                         icon_url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")
        embed.add_field(name=user.get_text("〇 登録アカウント上限の解放", "〇 Release the maximum number of registered accounts"),
                        value=user.get_text("１アカウントの登録上限が10アカウントまで登録できるようになります",
                                            "The registration limit for 1 account will be increased to 10 accounts."),
                        inline=False)
        embed.add_field(name=user.get_text("〇 取得制限時間の短縮", "〇 Reduction of acquisition time limit"),
                        value=user.get_text("通常では3時間の制限が10分になります", "The normal three-hour limit will be 10 minutes."),
                        inline=False)
        embed.add_field(name=user.get_text("〇 ユーザー体験の向上", "〇 Improving the user experience"),
                        value=user.get_text(
                            "これまで、登録情報の更新が必要などのエラーメッセージが表示されることがありましたが、それぞれのアカウントに個別のプロキシを利用することでそれの出る確率が下がります。(このエラーはプロキシの数に対してユーザー数が多すぎたことが原因でした",
                            "It used to show error messages such as registration information needs to be updated, but by using a separate proxy for each account, the probability of that appearing is reduced. (This error was caused by the number of users being too large for the number of proxies."),
                        inline=False)
        embed.add_field(
            name=user.get_text("〇 指定した時間にストア内容を自動送信", "〇 Automatically send the store contents at the specified time."),
            value=user.get_text("毎朝8時等、指定した時間に今日のストアの内容が自動で送られます",
                                "The contents of today's store will be automatically sent to you at the time you specify, such as 8:00 a.m. every morning."),
            inline=False)
        embed.add_field(name=user.get_text("〇 その他機能への早期アクセス", "〇 Early access to other functions"),
                        value=user.get_text("開発中の機能などへの早期アクセスが可能です",
                                            "Early access to features under development, etc."), inline=False)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=user.get_text("プレミアムになる", "Become Premium"),
                                        url="https://twitter.com/messages/compose?recipient_id=1247325126896447488&text=" + user.get_text(
                                            "%E3%83%97%E3%83%AC%E3%83%9F%E3%82%A2%E3%83%A0%E3%83%A6%E3%83%BC%E3%82%B6%E3%83%BC%E3%81%AB%E3%81%AA%E3%82%8A%E3%81%9F%E3%81%84%E3%81%A7%E3%81%99%E3%80%82%0D%0A%E6%94%AF%E6%89%95%E6%96%B9%E6%B3%95%28paypay%2Clinepay%2C%E5%8F%A3%E5%BA%A7%E6%8C%AF%E8%BE%BC%2Cpaypal%2Cbtc%2Cltc%29%3A+%0D%0A%E4%BD%95%E3%81%8B%E6%9C%88%E5%88%86%281%EF%BD%9E12%29%3A+",
                                            "I+wanna+be+premium+user%0D%0Apayment+via%28paypal%2Cbtc%2Cltc%2C+bank+transfer%29%3A+%0D%0Amonth%281%EF%BD%9E12%29%3A+")))
        view.add_item(discord.ui.Button(label=user.get_text("質問", "Ask question"), url="http://valorant.sakura.rip"))
        await ctx.send(embed=embed, view=view)
        if user.is_premium:
            await ctx.send(
                user.get_text(f"おめでとうございます！。あなたはプレミアムユーザーです。\n{user.premium_until.strftime('%Y/%m/%d %H:%M:%S')}まで",
                              f"Congratulations! You are a premium user!\n until {user.premium_until.strftime('%Y/%m/%d %H:%M:%S')}"))

    @commands.command("register", aliases=["登録"])
    async def register_riot_account(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)
        if not isinstance(ctx.message.channel, discord.channel.DMChannel) or ctx.message.author == self.bot.user:
            await ctx.send(user.get_text("ログイン情報の登録が必要です。\n個人チャットで登録を進めてください",
                                         "You need to register your login information. Please proceed to register in \n personal chat"))
        if user.is_premium:
            if len(user.riot_accounts) > 10:
                await ctx.send(user.get_text("登録可能なアカウント数上限は１０です。",
                                             "The maximum number of accounts that can be registered is 10."))
                return
        else:
            if len(user.riot_accounts) >= 1:
                await ctx.send(user.get_text("""すでに1アカウントの情報が登録されています。
複数アカウントの登録はプレミアムユーザーのみ可能です。
既に登録済みのアカウント情報を更新したい場合は「登録更新」コマンドを利用してください
プレミアムユーザーの詳細は`premium`, `プレミアム`コマンドを利用してください""", """One account has already been registered.
Multiple accounts can be registered only by premium users.
If you want to update the information of an already registered account, please use the `update` command
Use the `premium` or `プレミアム` commands to get the details of premium users
"""))
                return

        await self.register_riot_user_internal(ctx.message.author)

    async def register_riot_user_internal(self, to: Union[discord.Member, discord.User]):
        user = User.get_promised(self.bot.database, to.id)

        if user.try_activate_count >= 3:
            if user.activation_locked_at + timedelta(minutes=10) < datetime.now():
                user.try_activate_count = 0
                user.activation_locked_at = None
            else:
                await to.send(user.get_text(f"ログインの試行回数上限に達しました。({user.try_activate_count}回)\n10分後に再度お試しください。",
                                            f"The maximum number of login attempts has been reached. ({user.try_activate_count} times)\nplease try again 10 minutes later,."))
                return

        embed = discord.Embed(title="VALORANT AUTHENTICATION",
                              description=user.get_text("ショップのスキン情報を入手するためには、以下のValorantのアカウント情報が必要です。",
                                                        "The following Valorant account information is required in order to fetch the store skin information."),
                              color=0xff0000)
        embed.set_author(name="play valorant",
                         icon_url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")
        embed.set_thumbnail(url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")
        embed.add_field(
            name=user.get_text("ユーザー名", "user id"),
            value=user.get_text("ゲームにログインするときに使用するIDです。", "The ID you use to log in to the game")
        )
        embed.add_field(
            name=user.get_text("パスワード", "password"),
            value=user.get_text("ゲームにログインするときに使用するパスワードです。", "The password you use to log in to the game.")
        )
        embed.set_footer(text=user.get_text(
            "ログイン情報はショップの内容を確認する目的のみに使用されます。",
            "Your login information will be used only for the purpose of checking the contents of the store."
        ))
        await to.send(embed=embed)
        await to.send(
            file=discord.File(user.get_text("assets/valorant_login_form_ja.png", "assets/valorant_login_form_en.png"))
        )

        def check_is_private_message(msg: discord.Message) -> bool:
            if msg.author.id != to.id:
                return False
            if msg.channel.id != to.dm_channel.id:
                return False
            return True

        riot_account = RiotAccount()
        view = discord.ui.View(timeout=60)
        menu = discord.ui.Select(options=[
            discord.SelectOption(
                label=region,
                description=description
            ) for region, description in {
                "ap": user.get_text("アジア太平洋地域(日本を含みます)", "Asia Pacific"),
                "na": user.get_text("北アメリカ", "North America"),
                "eu": user.get_text("ヨーロッパ", "Europe"),
                "latam": user.get_text("ラテンアメリカ", "Latin America"),
                "br": user.get_text("ブラジル", "Brazil"),
                "kr": user.get_text("韓国", "Korea"),
                "pbe": user.get_text("パブリックベータ環境", "Public Beta Environment")
            }.items()
        ])

        async def select_account_region(interaction: Interaction):
            riot_account.region = interaction.data["values"][0]
            view.stop()

        menu.callback = select_account_region
        view.add_item(menu)
        await to.send(content=user.get_text("まずはアカウントの地域を選択してください。\n正しいものを選択しないとログインできません。",
                                            "Select the region of your account\nIf you do not select the correct one, you will not be able to log in."),
                      view=view)

        view_stat = await view.wait()
        if view_stat:
            return
        await to.send(user.get_text("ユーザー名を送信してください。", "Submit your user id"))

        try:
            username = await self.bot.wait_for("message", check=check_is_private_message, timeout=60)
        except asyncio.TimeoutError:
            return
        riot_account.username = username.content
        for account in user.riot_accounts:
            if account.username == riot_account.username:
                await to.send(
                    user.get_text("このユーザーIDはすでにあなたのアカウントに登録されています。\n削除/再登録する場合は[登録解除]コマンドを利用してください",
                                  "This user ID has already been registered in your account.\nTo delete/reregister, use the [unregister] command.")
                )
                return

        await to.send(user.get_text("次に、パスワードを送信してください。", "Submit your password"))
        try:
            password = await self.bot.wait_for("message", check=check_is_private_message, timeout=60)
        except asyncio.TimeoutError:
            return
        riot_account.password = password.content
        await to.send(user.get_text("確認中です...", "checking...."))
        user.try_activate_count += 1
        cl = self.bot.new_valorant_client_api(user.is_premium, riot_account)
        try:
            await self.bot.run_blocking_func(cl.activate)
        except InvalidCredentialError:
            if user.try_activate_count >= 3:
                user.activation_locked_at = datetime.now()
                await to.send(user.get_text(f"ログインの試行回数上限に達しました。({user.try_activate_count}回)\n10分後に再度お試しください。",
                                            f"The maximum number of login attempts has been reached. ({user.try_activate_count} times)\nplease try again 10 minutes later,."))
                self.bot.database.commit()
                return
            await to.send(user.get_text(
                "ログインの情報に誤りがあります。\n再度「登録」コマンドを利用してログイン情報を登録してください。",
                "Invalid credentials, Please use the [register] command again to register your login information."))
            return
        except RateLimitedError:
            await to.send(user.get_text("現在サーバーが込み合っており、取得ができませんでした。後程お試しください",
                                        "The server is currently busy and could not retrieve the data. Please try again later."))
            return None
        except Exception as e:
            self.bot.logger.error(f"failed to login valorant client", exc_info=e)
            await to.send(user.get_text("不明なエラーが発生しました。管理者までお問い合わせください。",
                                        "An unknown error has occurred. Please contact the administrator."))
            return None
        user.try_activate_count = 0
        user.activation_locked_at = None
        name = await self.bot.run_blocking_func(cl.fetch_player_name)
        riot_account.game_name = f"{name[0]['GameName']}#{name[0]['TagLine']}"
        riot_account.puuid = cl.puuid
        user.riot_accounts.append(riot_account)
        self.bot.database.commit()
        tier = await self.bot.run_blocking_func(self.bot.get_valorant_rank_tier, cl)
        await to.send(user.get_text(
            f"ログイン情報の入力が完了しました。\n{riot_account.game_name}\nRANK: {tier}",
            f"Your login information has been entered.\n{riot_account.game_name}\nRANK: {tier}"
        ))

    @commands.command("unregister", aliases=["登録解除"])
    async def unregister_riot_account(self, ctx: Context):
        user = User.get_promised(self.bot.database, ctx.message.author.id)

        if not isinstance(ctx.message.channel, discord.channel.DMChannel) or ctx.message.author == self.bot.user:
            await ctx.send(user.get_text("この動作は個人チャットでする必要があります。", "This action needs to be done in private chat"))
            return

        get_span = 5 if user.is_premium else 86400
        if user.last_account_deleted_at and user.last_account_deleted_at + timedelta(
                minutes=get_span) >= datetime.now():
            await ctx.send(user.get_text(
                f"最後に削除してから{get_span}分経過していません。{get_span}分に一度のみこのコマンドを実行可能です。",
                f"It has not been {get_span} minutes since the last deletion. this command can only be executed once every {get_span} minutes."))
            return

        user.last_account_deleted_at = datetime.now()
        self.bot.database.commit()

        def wrapper(view: discord.ui.View):
            async def select_account_region(interaction: Interaction):
                await interaction.response.send_message(content="processing your request....wait a moment...")
                account = self.bot.database.query(RiotAccount).filter(
                    RiotAccount._game_name == interaction.data["values"][0]).first()
                self.bot.database.delete(account)
                self.bot.database.commit()
                view.stop()
                await ctx.send(user.get_text(f"{account.username}: 完了しました", f"{account.username}: Done"))

            return select_account_region

        await self.list_account_and_execute(ctx, wrapper)


def setup(bot: ValorantStoreBot):
    bot.add_cog(CommandsHandler(bot))
