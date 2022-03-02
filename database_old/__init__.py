from .server import Server
from .user import User
from .setting import Base, ENGINE, session

Base.metadata.create_all(bind=ENGINE)
