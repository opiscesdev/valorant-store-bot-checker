import datetime

from sqlalchemy import Column, Integer, String, DATE

from .setting import Base


class SkinLog(Base):
    __tablename__ = "skin_logs"

    id: int = Column("id", Integer, autoincrement=True, primary_key=True)

    account_puuid: str = Column("account_puuid", String)
    date: datetime.date = Column("date", DATE)
    skin_uuid: str = Column("skin_uuid", String)
