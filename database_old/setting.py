# DBの設定
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base

DATABASE = "sqlite:///valorant.sqlite3"
ENGINE = create_engine(
    DATABASE, connect_args={"check_same_thread": False}
)

# Sessionの作成
session = scoped_session(
    sessionmaker(autoflush=False, bind=ENGINE)
)

# modelで使用する
Base = declarative_base()
Base.query = session.query_property()
