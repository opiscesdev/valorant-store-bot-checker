from __future__ import annotations

import datetime

import sqlalchemy.orm
from sqlalchemy import Column, Integer, String, DATETIME

from .setting import Base


# TODO: allow multiple accounts
# class RiotAccount(Base):
#     __tablename__ = "riot_accounts"
#
#     username: str = Column("username", String)
#     password: str = Column("password", String)
#     riot_id: str = Column("riot_id", String)
#     usable: bool = Column("usable", Boolean)
#
#     user_id: int = Column(Integer, ForeignKey("users.uuid"))
#     user = sqlalchemy.orm.relationship("User", backref="RiotAccount")


class User(Base):
    __tablename__ = "users"

    uuid: int = Column("uuid", Integer, primary_key=True)

    riot_userid: str = Column("riot_userid", String)
    riot_password: str = Column("riot_password", String)
    try_activate_count: int = Column("tac", Integer, default=0)
    activation_locked_at: datetime.datetime = Column("acloat", DATETIME)

    last_get_shops_at: datetime.datetime = Column("lgsat", DATETIME)
    last_get_night_shops_at: datetime.datetime = Column("lgnsat", DATETIME)

    # riot_accounts: List[RiotAccount] = sqlalchemy.orm.relationship("RiotAccount")

    @staticmethod
    def get_promised(session: sqlalchemy.orm.Session, uuid: str) -> User:
        user = session.query(User).filter(User.uuid == uuid).first()
        if user is None:
            session.add(User(uuid=uuid))
            session.commit()
            user = session.query(User).filter(User.uuid == uuid).first()
        return user
