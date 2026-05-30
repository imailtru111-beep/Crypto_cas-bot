import asyncio
import aiohttp
import os
from database.models import async_session, User, Transaction, get_setting, update_balance, log_transaction
from sqlalchemy import select

TON_API_KEY = os.getenv("TON_API_KEY", "")
PROCESSED_TX = set()  # In-memory cache of processed tx hashes


async def check_ton_deposits(bot):
    """Background task to check TON wallet for incoming deposits"""
    if not TON_API_KEY:
        return

    collection_wallet = await get_setting("collection_wallet", "")
    if not collection_wallet:
        return

    try:
        headers = {"Authorization": f"Bearer {TON_API_KEY}"}
        url = f"https://tonapi.io/v2/accounts/{collection_wallet}/transactions?limit=20"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()

        transactions = data.get("transactions", [])

        for tx in transactions:
            tx_hash = tx.get("hash", "")
            if tx_hash in PROCESSED_TX:
                continue

            # Only incoming
            in_msg = tx.get("in_msg", {})
            if not in_msg:
                continue

            value_nano = int(in_msg.get("value", 0))
            if value_nano <= 0:
                continue

            # Value in TON
            value_ton = value_nano / 1_000_000_000

            # Get comment
            comment_body = in_msg.get("decoded_body", {})
            comment = comment_body.get("text", "") if comment_body else ""

            # Try to find user by comment (should be their tg_id)
            try:
                tg_id = int(comment.strip())
            except (ValueError, AttributeError):
                PROCESSED_TX.add(tx_hash)
                continue

            # Check if user exists
            async with async_session() as db_session:
                result = await db_session.execute(select(User).where(User.tg_id == tg_id))
                user = result.scalar_one_or_none()
                if not user:
                    PROCESSED_TX.add(tx_hash)
                    continue

                # Check not already processed
                existing = await db_session.execute(
                    select(Transaction).where(Transaction.external_id == tx_hash)
                )
                if existing.scalar_one_or_none():
                    PROCESSED_TX.add(tx_hash)
                    continue

                # Credit balance
                user.balance += value_ton
                user.total_deposited += value_ton

                tx_record = Transaction(
                    tg_id=tg_id,
                    type="deposit",
                    amount=value_ton,
                    status="completed",
                    provider="ton",
                    external_id=tx_hash,
                    comment=f"TON direct deposit",
                )
                db_session.add(tx_record)
                await db_session.commit()

            PROCESSED_TX.add(tx_hash)

            # Notify user
            try:
                await bot.send_message(
                    tg_id,
                    f"✅ Пополнение получено!\n\n"
                    f"💎 +{value_ton:.4f} TON\n"
                    f"💰 Баланс обновлён"
                )
            except Exception:
                pass

    except Exception as e:
        pass  # Silent fail - will retry next cycle


async def ton_watcher_loop(bot):
    """Run TON deposit checker every 30 seconds"""
    while True:
        try:
            await check_ton_deposits(bot)
        except Exception:
            pass
        await asyncio.sleep(30)


async def check_send_deposits(bot):
    """Check @send bot deposits via webhook/polling"""
    # @send integration - users send with comment = tg_id
    # This is handled via webhook from @send or manual verification
    # Basic implementation: check transactions table for pending
    pass


async def payment_watcher(bot):
    """Main payment watcher coroutine"""
    await asyncio.gather(
        ton_watcher_loop(bot),
    )
