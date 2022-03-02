from __future__ import annotations

from sqlalchemy import Column, Integer
from sqlalchemy.orm import Session

from .setting import Base


class Guild(Base):
    __tablename__ = "guilds"

    id: int = Column("id", Integer, primary_key=True)
    response_here: int = Column("response_here", Integer)

    @staticmethod
    def get_promised(session: Session, uid: int) -> Guild:
        guild = session.query(Guild).filter(Guild.id == uid).first()
        if guild is not None:
            return guild
        new_guild = Guild(id=uid)
        session.add(new_guild)
        session.commit()
        return new_guild
