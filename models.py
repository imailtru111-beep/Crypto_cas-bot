import os
from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean,
    DateTime, Text, ForeignKey, select, update
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///casino.db")
# Fix postgres URL for SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(64), nullable=True)
    full_name = Column(String(128), nullable=True)
    balance = Column(Float, default=0.0)
    ref_balance = Column(Float, default=0.0)
    referrer_id = Column(BigInteger, nullable=True)
    total_deposited = Column(Float, default=0.0)
    total_withdrawn = Column(Float, default=0.0)
    total_wagered = Column(Float, default=0.0)
    total_won = Column(Float, default=0.0)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, nullable=False)
    type = Column(String(32), nullable=False)  # deposit, withdraw, bet_win, bet_loss, ref_bonus
    amount = Column(Float, nullable=False)
    currency = Column(String(16), default="TON")
    status = Column(String(16), default="pending")  # pending, completed, failed
    provider = Column(String(32), nullable=True)  # send, xrocket, stars, ton
    external_id = Column(String(256), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BetHistory(Base):
    __tablename__ = "bet_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, nullable=False)
    game = Column(String(32), nullable=False)  # roulette, mines, tower
    bet_amount = Column(Float, nullable=False)
    win_amount = Column(Float, default=0.0)
    profit = Column(Float, default=0.0)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WithdrawRequest(Base):
    __tablename__ = "withdraw_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    net_amount = Column(Float, nullable=False)
    wallet = Column(String(128), nullable=False)
    status = Column(String(16), default="pending")  # pending, approved, rejected
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class GameSession(Base):
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, nullable=False)
    game = Column(String(32), nullable=False)
    state = Column(Text, nullable=True)  # JSON state
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BotSettings(Base):
    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Insert default settings
    async with async_session() as session:
        defaults = {
            "min_bet": "0.1",
            "max_bet": "100.0",
            "house_edge": "0.03",
            "withdrawal_fee": os.getenv("WITHDRAWAL_FEE", "0.05"),
            "collection_wallet": os.getenv("COLLECTION_WALLET", ""),
            "min_withdraw": "1.0",
        }
        for key, value in defaults.items():
            existing = await session.execute(
                select(BotSettings).where(BotSettings.key == key)
            )
            if not existing.scalar_one_or_none():
                session.add(BotSettings(key=key, value=value))
        await session.commit()


async def get_setting(key: str, default=None):
    async with async_session() as session:
        result = await session.execute(
            select(BotSettings).where(BotSettings.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else default


async def set_setting(key: str, value: str):
    async with async_session() as session:
        result = await session.execute(
            select(BotSettings).where(BotSettings.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            session.add(BotSettings(key=key, value=value))
        await session.commit()


async def get_or_create_user(tg_id: int, username: str = None, full_name: str = None, referrer_id: int = None):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                tg_id=tg_id,
                username=username,
                full_name=full_name,
                referrer_id=referrer_id,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # Update username/name
            if username:
                user.username = username
            if full_name:
                user.full_name = full_name
            user.last_seen = datetime.utcnow()
            await session.commit()
        return user


async def get_user(tg_id: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        return result.scalar_one_or_none()


async def update_balance(tg_id: int, delta: float):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if user:
            user.balance = max(0.0, user.balance + delta)
            await session.commit()
            return user.balance
        return None


async def log_transaction(tg_id: int, type_: str, amount: float, status: str = "completed",
                           provider: str = None, external_id: str = None, comment: str = None):
    async with async_session() as session:
        tx = Transaction(
            tg_id=tg_id,
            type=type_,
            amount=amount,
            status=status,
            provider=provider,
            external_id=external_id,
            comment=comment,
        )
        session.add(tx)
        await session.commit()
        return tx.id


async def log_bet(tg_id: int, game: str, bet: float, win: float, details: str = None):
    profit = win - bet
    async with async_session() as session:
        history = BetHistory(
            tg_id=tg_id,
            game=game,
            bet_amount=bet,
            win_amount=win,
            profit=profit,
            details=details,
        )
        session.add(history)

        # Update user stats
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if user:
            user.total_wagered += bet
            user.total_won += win

        await session.commit()

    # Handle referral bonus on loss
    if profit < 0:
        await handle_ref_bonus(tg_id, abs(profit))


async def handle_ref_bonus(loser_tg_id: int, loss_amount: float):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == loser_tg_id))
        user = result.scalar_one_or_none()
        if not user or not user.referrer_id:
            return

        ref_result = await session.execute(select(User).where(User.tg_id == user.referrer_id))
        referrer = ref_result.scalar_one_or_none()
        if not referrer:
            return

        bonus = round(loss_amount * 0.10, 6)
        referrer.ref_balance += bonus
        referrer.balance += bonus

        session.add(Transaction(
            tg_id=referrer.tg_id,
            type="ref_bonus",
            amount=bonus,
            status="completed",
            comment=f"10% от проигрыша реферала {loser_tg_id}",
        ))
        await session.commit()
