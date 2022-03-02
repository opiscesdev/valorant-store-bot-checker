from typing import List

from database import User as UserNew
from database_old import User as UserOld
from database import session as session_new
from database_old import session as session_old
from database import RiotAccount

olds: List[UserOld] = session_old.query(UserOld).all()
new_users = []
for old in olds:
    if not old.riot_userid:
        continue
    new_users.append(UserNew(
        id=old.uuid,
        riot_accounts=[
            RiotAccount(
                username=old.riot_userid,
                password=old.riot_password,
                region="ap",
            )
        ]
    ))
print(len(new_users))
session_new.add_all(new_users)
session_new.commit()
