import asyncio
import functools
import logging
import random
from datetime import datetime
from typing import Optional, List, Callable

import discord
import pytz
import sqlalchemy.orm
from discord.embeds import EmptyEmbed
from discord.ext import commands

import valclient
from database import session, Weapon
from database.user import RiotAccount, User
from setting import INITIAL_EXTENSIONS
from valclient.auth import InvalidCredentialError, RateLimitedError


def build_logger() -> logging.Logger:
    sth = logging.StreamHandler()
    flh = logging.FileHandler('sample.log')

    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO,
                        handlers=[sth, flh])
    return logging.getLogger(__name__)


with open("proxies.txt", "r", encoding="utf-8") as f:
    proxies = f.read().splitlines()

premium_proxies = proxies[:(int(len(proxies) / 4))]
normal_proxies = proxies[(int(len(proxies) / 4) * 3):]


def get_link(link: str) -> str:
    splited = link.split(":")
    return f"http://{splited[2]}:{splited[3]}@{splited[0]}:{splited[1]}"


def get_proxy_url(is_premium: bool):
    if is_premium:
        link = get_link(random.choice(premium_proxies))
    else:
        link = get_link(random.choice(normal_proxies))
    return {
        "http": link,
        "https": link
    }


class ValorantStoreBot(commands.AutoShardedBot):
    def __init__(self, prefix: str, intents: Optional[discord.Intents] = None):
        super().__init__(prefix, intents=intents, max_messages=None, help_command=None)
        for c in INITIAL_EXTENSIONS:
            self.load_extension(c)

        self.database: sqlalchemy.orm.Session = session
        self.logger: logging.Logger = build_logger()
        self.admins: List[int] = [753630696295235605]

    async def update_account_profile(self, user: User, account: RiotAccount):
        cl = await self.login_valorant(user, account)
        if not cl:
            return
        name = await self.run_blocking_func(cl.fetch_player_name)
        account.puuid = cl.puuid
        account.game_name = f"{name[0]['GameName']}#{name[0]['TagLine']}"
        self.database.commit()

    async def get_user_promised(self, uid: int) -> discord.User:
        u = self.get_user(uid)
        if not u:
            u = await self.fetch_user(uid)
        return u

    async def login_valorant(self, user: User, account: RiotAccount) -> Optional[valclient.Client]:
        cl = self.new_valorant_client_api(user.is_premium, account)
        user_d = await self.get_user_promised(account.user_id)
        try:
            await self.run_blocking_func(cl.activate)
        except RateLimitedError:
            await user_d.send(user.get_text("現在サーバーが込み合っており、取得ができませんでした。後程お試しください",
                                            "The server is currently busy and could not retrieve the data. Please try again later."))
            return None
        except InvalidCredentialError:
            await user_d.send(user.get_text("ログインの情報に誤りがあります。\n再度「登録」コマンドを利用してログイン情報を登録してください",
                                            "Invalid credentials, Please use the [register] command again to register your login information."))
        except Exception as e:
            self.logger.error(f"failed to login valorant client", exc_info=e)
            await user_d.send(user.get_text("不明なエラーが発生しました。管理者までお問い合わせください。",
                                            "An unknown error has occurred. Please contact the administrator."))
            return None
        account.puuid = cl.puuid
        return cl

    async def store_content_notify(self):
        while True:
            await asyncio.sleep(60)
            users = self.database.query(User).filter(User.auto_notify_timezone != "").all()
            for user in users:
                try:
                    now_hour = datetime.now().astimezone(pytz.timezone(user.auto_notify_timezone)).hour
                    if now_hour == user.auto_notify_at:
                        if user.auto_notify_flag is True:
                            continue
                        user.auto_notify_flag = True
                        cl = await self.login_valorant(user, user.auto_notify_account)
                        if not cl:
                            self.database.commit()
                            return
                        u = await self.get_user_promised(user.id)
                        await u.send(
                            content=user.get_text("本日のストアの内容をお送りします。", "Here's what's in your valorant store today"))
                        offers = await self.run_blocking_func(cl.store_fetch_storefront)
                        for offer_uuid in offers.get("SkinsPanelLayout", {}).get("SingleItemOffers", []):
                            skin = Weapon.get_promised(self.database, offer_uuid, user)
                            embed = discord.Embed(title=skin.display_name, color=0xff0000,
                                                  url=skin.streamed_video if skin.streamed_video else EmptyEmbed,
                                                  description=user.get_text("↑から動画が見れます",
                                                                            "You can watch the video at↑") if skin.streamed_video else EmptyEmbed)
                            embed.set_author(name="valorant shop",
                                             icon_url="https://pbs.twimg.com/profile_images/1403218724681777152/rcOjWkLv_400x400.jpg")
                            embed.set_image(url=skin.display_icon)
                            await u.send(embed=embed)
                    else:
                        user.auto_notify_flag = False
                except Exception as e:
                    self.logger.error("failed to notify store content", exc_info=e)
            self.database.commit()

    async def run_blocking_func(self, blocking_func: Callable, *args, **kwargs):
        loop = asyncio.get_event_loop()
        function = functools.partial(blocking_func, *args, **kwargs)
        return await loop.run_in_executor(None, function)

    def new_valorant_client_api(self, is_premium: bool,
                                account: RiotAccount) -> valclient.Client:
        if account.is_not_valid:
            return valclient.Client()
        proxy = get_proxy_url(is_premium)
        return valclient.Client(region=account.region, auth={
            "username": account.username,
            "password": account.password
        }, proxy=proxy)

    def get_valorant_rank_tier(self, cl: valclient.Client) -> str:
        tier_to_name = ["UNRANKED", "Unused1", "Unused2", "IRON 1", "IRON 2", "IRON 3", "BRONZE 1",
                        "BRONZE 2", "BRONZE 3", "SILVER 1", "SILVER 2", "SILVER 3", "GOLD 1", "GOLD 2",
                        "GOLD 3", "PLATINUM 1", "PLATINUM 2", "PLATINUM 3", "DIAMOND 1", "DIAMOND 2",
                        "DIAMOND 3", "IMMORTAL 1", "IMMORTAL 2", "IMMORTAL 3", "RADIANT"]
        result = cl.fetch_competitive_updates()
        try:
            tier = result["Matches"][0]["TierAfterUpdate"]
        except IndexError:
            return "Failed to get rank tier"
        return tier_to_name[tier]

    async def on_ready(self):
        print(f"bot started: {self.user}")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Valorant store"))

        asyncio.ensure_future(self.store_content_notify())
