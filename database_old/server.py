from __future__ import annotations

from sqlalchemy import Column, Integer

from .setting import Base


class Server(Base):
    __tablename__ = "servers"

    id: int = Column("id", Integer, primary_key=True)
    welcome_channel_id: int = Column("wcid", Integer)
    agent_select_msg_id: int = Column("agid", Integer)
    rank_select_msg_id: int = Column("raid", Integer)

    # recruitment_create_msg_id: int = Column("recr_aid", Integer)
    # recruitment_category_id: int = Column("recr_cid", Integer)

    @staticmethod
    def get_promised(session, uid: int) -> Server:
        server = session.query(Server).filter(Server.id == uid).first()
        if server is None:
            session.add(Server(id=uid))
            session.commit()
            server = session.query(Server).filter(Server.id == uid).first()
        return server

#
# class QueueType(IntEnum):
#     unrate = auto()
#     competitive = auto()
#     custom = auto()
#
#
# class Recruitment(Base):
#     __tablename__ = "recruitments"
#     id: int = Column("id", Integer, autoincrement=True, primary_key=True)
#     server_id: int = Column("id", Integer)
#
#     _agent_ids: str = Column("a_ids", String)
#     _rank_ids: str = Column("r_ids", String)
#
#     queue_type: QueueType = Column("qtype", Integer)
#     member_count: int = Column("mc", Integer)
#
#     description: str = Column("desc", String)
#     title: str = Column("title", String)
#
#     @property
#     def agent_ids(self) -> List[str]:
#         return self.__remove_empty_string(self._agent_ids.split("%%"))
#
#     def set_agent_ids(self, id: str):
#         ids = self.agent_ids
#         ids.append(id)
#         self._agent_ids = "%%".join(ids)
#
#     def delete_agent_ids(self, id: str):
#         if id not in self._agent_ids:
#             return
#         ids = self.agent_ids
#         ids.remove(id)
#         self._agent_ids = "%%".join(ids)
#
#     @property
#     def rank_ids(self) -> List[str]:
#         return self.__remove_empty_string(self._rank_ids.split("%%"))
#
#     def set_rank_ids(self, id: str):
#         ids = self.rank_ids
#         ids.append(id)
#         self._rank_ids = "%%".join(ids)
#
#     def delete_rank_ids(self, id: str):
#         if id not in self._rank_ids:
#             return
#         ids = self.rank_ids
#         ids.remove(id)
#         self._rank_ids = "%%".join(ids)
#
#     def __remove_empty_string(self, array: List[str]) -> list[Sized]:
#         return list(filter(len, array))
