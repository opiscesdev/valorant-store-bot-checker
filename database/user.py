from __future__ import annotations

import datetime
from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey, DATETIME, Boolean
from sqlalchemy.orm import Session, relationship

from .setting import Base


class User(Base):
    __tablename__ = "users"

    id: int = Column("id", Integer, primary_key=True)
    language: str = Column("language", String, default="ja-JP")

    try_activate_count: int = Column("try_activate_count", Integer, default=0)
    activation_locked_at: datetime.datetime = Column("activation_locked_at", DATETIME)

    _is_premium: bool = Column("is_premium", Boolean, default=False)
    premium_until: datetime.datetime = Column("premium_until", DATETIME)

    riot_accounts: List[RiotAccount] = relationship("RiotAccount", backref="users")

    auto_notify_timezone: str = Column("auto_notify_timezone", String)
    auto_notify_at: int = Column("auto_notify_at", Integer)
    auto_notify_flag: bool = Column("auto_notify_flag", Boolean)
    auto_notify_account: RiotAccount = relationship("RiotAccount", uselist=False, overlaps="riot_accounts,users")

    last_account_deleted_at: datetime.datetime = Column("last_account_deleted_at", DATETIME)

    @property
    def is_premium(self):
        return self._is_premium and self.premium_until >= datetime.datetime.now()

    @is_premium.setter
    def is_premium(self, value: bool):
        self._is_premium = value

    @staticmethod
    def get_promised(session: Session, uid: int) -> User:
        user = session.query(User).filter(User.id == uid).first()
        if user is not None:
            return user
        new_user = User(id=uid)
        session.add(new_user)
        session.commit()
        return new_user

    def get_text(self, ja: str, en: str):
        if self.language == "ja-JP":
            return ja
        return en


class UpdateProfileRequired(Exception):
    def __init__(self, account: RiotAccount):
        self.account = account


class RiotAccount(Base):
    __tablename__ = "riot_accounts"

    uuid: int = Column("uuid", Integer, autoincrement=True, primary_key=True)
    is_not_valid: bool = Column("is_not_valid", Boolean, default=False)

    username: str = Column("username", String)
    password: str = Column("password", String)
    region: str = Column("region", String)

    _game_name: str = Column("game_name", String)
    _puuid: str = Column("puuid", String)

    user_id: int = Column("user_id", Integer, ForeignKey("users.id"))

    last_get_shops_at: datetime.datetime = Column("last_get_shops_at", DATETIME)
    last_get_night_shops_at: datetime.datetime = Column("last_get_night_shops_at", DATETIME)

    auto_notify_account_user_id = relationship("User", overlaps="auto_notify_account,riot_accounts,users")

    @property
    def puuid(self):
        if not self._puuid:
            raise UpdateProfileRequired(self)
        return self._puuid

    @puuid.setter
    def puuid(self, value):
        self._puuid = value

    @property
    def game_name(self):
        if not self._game_name:
            raise UpdateProfileRequired(self)
        return self._game_name

    @game_name.setter
    def game_name(self, value):
        self._game_name = value
