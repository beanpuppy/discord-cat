from apocryphes.pool import PooledSQLiteDatabase
from estoult import Field

db = PooledSQLiteDatabase(database="data/bot.db")


class SessionHistory(db.Schema):
    __tablename__ = "session_history"

    player = Field(str)
    start = Field(str)
    end = Field(str)


class DowntimeHistory(db.Schema):
    __tablename__ = "downtime_history"

    id = Field(int)
    start = Field(str)
    end = Field(str)


def create_db():
    db.connect()

    db.sql(
        """
        create table if not exists session_history (
            player text not null,
            start text not null,
            end text not null
        );
    """,
        (),
    )

    db.sql(
        """
        create table if not exists downtime_history (
            id integer primary key autoincrement not null,
            start text not null,
            end text not null
        );
    """,
        (),
    )

    db.close()
