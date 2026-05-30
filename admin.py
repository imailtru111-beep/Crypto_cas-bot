import os
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import (
    async_session, get_setting, set_setting, update_balance,
    log_transaction, User, Transaction, BetHistory, WithdrawRequest
)
from sqlalchemy import select, func, desc
from utils.keyboards import admin_main_kb, admin_withdraw_kb, back_kb

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


def admin_only(func):
    async def wrapper(message_or_call, *args, **kwargs):
        uid = message_or_call.from_user.id
        if uid not in ADMIN_IDS:
            if hasattr(message_or_call, 'answer'):
                await message_or_call.answer("🚫 Доступ запрещён")
            else:
                await message_or_call.answer("🚫 Доступ запрещён", show_alert=True)
            return
        return await func(message_or_call, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


class AdminStates(StatesGroup):
    broadcast_text = State()
    adjust_balance_id = State()
    adjust_balance_amount = State()
    set_setting_key = State()
    set_setting_value = State()
    set_wallet = State()


@router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    async with async_session() as session:
        user_count = (await session.execute(select(func.count()).select_from(User))).scalar()
        total_dep = (await session.execute(select(func.sum(User.total_deposited)))).scalar() or 0
        total_wd = (await session.execute(select(func.sum(User.total_withdrawn)))).scalar() or 0
        pending_wd = (await session.execute(
            select(func.count()).select_from(WithdrawRequest)
            .where(WithdrawRequest.status == "pending")
        )).scalar()

    text = (
        f"🔐 ═══════════════════\n"
        f"    ADMIN PANEL\n"
        f"════════════════════\n\n"
        f"👥 Пользователей: {user_count}\n"
        f"💰 Пополнено всего: {total_dep:.2f} TON\n"
        f"📤 Выведено всего: {total_wd:.2f} TON\n"
        f"⏳ Заявок на вывод: {pending_wd}\n"
        f"════════════════════"
    )
    await message.answer(text, reply_markup=admin_main_kb())


@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return

    async with async_session() as session:
        user_count = (await session.execute(select(func.count()).select_from(User))).scalar()
        total_wagered = (await session.execute(select(func.sum(User.total_wagered)))).scalar() or 0
        total_won = (await session.execute(select(func.sum(User.total_won)))).scalar() or 0
        total_dep = (await session.execute(select(func.sum(User.total_deposited)))).scalar() or 0
        total_wd = (await session.execute(select(func.sum(User.total_withdrawn)))).scalar() or 0
        total_balance = (await session.execute(select(func.sum(User.balance)))).scalar() or 0
        banned = (await session.execute(
            select(func.count()).select_from(User).where(User.is_banned == True)
        )).scalar()

    house_profit = total_wagered - total_won
    text = (
        f"📊 ═══════════════════\n"
        f"     СТАТИСТИКА\n"
        f"════════════════════\n\n"
        f"👥 Пользователей: {user_count}\n"
        f"🚫 Заблокировано: {banned}\n\n"
        f"💰 Пополнено: {total_dep:.4f} TON\n"
        f"📤 Выведено: {total_wd:.4f} TON\n"
        f"💳 Балансы: {total_balance:.4f} TON\n\n"
        f"🎯 Поставлено: {total_wagered:.4f} TON\n"
        f"🏆 Выиграно: {total_won:.4f} TON\n"
        f"🏦 Доход казино: {house_profit:.4f} TON\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=back_kb("adm_main"))
    await call.answer()


@router.callback_query(F.data == "adm_users")
async def cb_adm_users(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(desc(User.created_at)).limit(20)
        )
        users = result.scalars().all()

    lines = ["👥 ═══ ПОЛЬЗОВАТЕЛИ (20) ═══\n"]
    for u in users:
        ban = "🚫" if u.is_banned else "✅"
        lines.append(f"{ban} {u.tg_id} | @{u.username or '—'} | {u.balance:.3f} TON")

    await call.message.edit_text("\n".join(lines), reply_markup=back_kb("adm_main"))
    await call.answer()


@router.callback_query(F.data == "adm_withdrawals")
async def cb_adm_withdrawals(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(WithdrawRequest)
            .where(WithdrawRequest.status == "pending")
            .order_by(WithdrawRequest.created_at)
            .limit(10)
        )
        requests = result.scalars().all()

    if not requests:
        await call.message.edit_text("✅ Нет заявок на вывод", reply_markup=back_kb("adm_main"))
        await call.answer()
        return

    wr = requests[0]
    text = (
        f"💸 ЗАЯВКА #{wr.id}\n"
        f"════════════════════\n\n"
        f"👤 ID: {wr.tg_id}\n"
        f"💰 Сумма: {wr.amount:.4f} TON\n"
        f"📉 Комиссия: {wr.fee:.4f} TON\n"
        f"💎 К выплате: {wr.net_amount:.4f} TON\n"
        f"📬 Адрес:\n{wr.wallet}\n\n"
        f"📅 {wr.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"⏳ Ещё заявок: {len(requests)-1}\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=admin_withdraw_kb(wr.id))
    await call.answer()


@router.callback_query(F.data.startswith("adm_wd_approve_"))
async def cb_adm_wd_approve(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return

    wr_id = int(call.data.split("_")[3])
    async with async_session() as session:
        result = await session.execute(
            select(WithdrawRequest).where(WithdrawRequest.id == wr_id)
        )
        wr = result.scalar_one_or_none()
        if not wr or wr.status != "pending":
            await call.answer("Заявка уже обработана", show_alert=True)
            return
        wr.status = "approved"
        wr.processed_at = datetime.utcnow()
        await session.commit()
        tg_id = wr.tg_id
        net = wr.net_amount

    await log_transaction(tg_id, "withdraw_approved", net, "completed", comment=f"request_id:{wr_id}")

    try:
        await call.bot.send_message(
            tg_id,
            f"✅ Заявка #{wr_id} одобрена!\n"
            f"💎 Отправлено: {net:.4f} TON"
        )
    except Exception:
        pass

    await call.message.edit_text(f"✅ Заявка #{wr_id} одобрена", reply_markup=back_kb("adm_main"))
    await call.answer("✅ Одобрено!")


@router.callback_query(F.data.startswith("adm_wd_reject_"))
async def cb_adm_wd_reject(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return

    wr_id = int(call.data.split("_")[3])
    async with async_session() as session:
        result = await session.execute(
            select(WithdrawRequest).where(WithdrawRequest.id == wr_id)
        )
        wr = result.scalar_one_or_none()
        if not wr or wr.status != "pending":
            await call.answer("Заявка уже обработана", show_alert=True)
            return
        wr.status = "rejected"
        wr.processed_at = datetime.utcnow()
        tg_id = wr.tg_id
        amount = wr.amount
        await session.commit()

    # Refund
    await update_balance(tg_id, amount)
    await log_transaction(tg_id, "withdraw_refund", amount, "completed", comment=f"refund_request:{wr_id}")

    try:
        await call.bot.send_message(
            tg_id,
            f"❌ Заявка #{wr_id} отклонена.\n"
            f"💰 Средства возвращены: {amount:.4f} TON"
        )
    except Exception:
        pass

    await call.message.edit_text(f"❌ Заявка #{wr_id} отклонена, средства возвращены", reply_markup=back_kb("adm_main"))
    await call.answer("❌ Отклонено, возврат выполнен")


@router.callback_query(F.data == "adm_settings")
async def cb_adm_settings(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return

    settings = {}
    for key in ["min_bet", "max_bet", "house_edge", "withdrawal_fee", "min_withdraw", "collection_wallet"]:
        settings[key] = await get_setting(key, "—")

    text = (
        f"⚙️ НАСТРОЙКИ\n"
        f"════════════════════\n\n"
        f"💰 Мин ставка: {settings['min_bet']} TON\n"
        f"💰 Макс ставка: {settings['max_bet']} TON\n"
        f"🏦 Комиссия казино: {float(settings['house_edge'])*100:.0f}%\n"
        f"📉 Комиссия вывода: {float(settings['withdrawal_fee'])*100:.0f}%\n"
        f"💎 Мин вывод: {settings['min_withdraw']} TON\n"
        f"📬 Кошелёк: {settings['collection_wallet'][:20] if settings['collection_wallet'] != '—' else '—'}...\n\n"
        f"Чтобы изменить — используй команды:\n"
        f"/setminbet [сумма]\n"
        f"/setmaxbet [сумма]\n"
        f"/setwithfee [0.05]\n"
        f"/setwallet [адрес]\n"
        f"/addbalance [id] [сумма]\n"
        f"/subbalance [id] [сумма]\n"
        f"/ban [id]\n"
        f"/unban [id]\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=back_kb("adm_main"))
    await call.answer()


@router.callback_query(F.data == "adm_main")
async def cb_adm_main(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return
    await call.message.edit_text("🔐 Admin Panel", reply_markup=admin_main_kb())
    await call.answer()


@router.callback_query(F.data == "adm_payments")
async def cb_adm_payments(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.type == "deposit")
            .order_by(desc(Transaction.created_at))
            .limit(15)
        )
        txs = result.scalars().all()

    lines = ["💰 ═══ ПЛАТЕЖИ (15) ═══\n"]
    for t in txs:
        lines.append(
            f"#{t.id} {t.tg_id} | {t.amount:.3f} TON | "
            f"{t.provider or '?'} | {t.status}"
        )

    await call.message.edit_text("\n".join(lines) or "Нет платежей", reply_markup=back_kb("adm_main"))
    await call.answer()


@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🚫", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_text)
    await call.message.edit_text(
        "📢 Введи текст рассылки:\n(или /cancel для отмены)",
        reply_markup=back_kb("adm_main")
    )
    await call.answer()


@router.message(AdminStates.broadcast_text)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    text = message.text
    await state.clear()

    async with async_session() as session:
        result = await session.execute(select(User.tg_id).where(User.is_banned == False))
        user_ids = [row[0] for row in result.fetchall()]

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, f"📢 LEPS CASINO\n\n{text}")
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Не доставлено: {failed}")


# Admin commands
@router.message(Command("setminbet"))
async def cmd_setminbet(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = float(message.text.split()[1])
        await set_setting("min_bet", str(val))
        await message.answer(f"✅ Мин ставка: {val} TON")
    except Exception:
        await message.answer("❌ Использование: /setminbet 0.1")


@router.message(Command("setmaxbet"))
async def cmd_setmaxbet(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = float(message.text.split()[1])
        await set_setting("max_bet", str(val))
        await message.answer(f"✅ Макс ставка: {val} TON")
    except Exception:
        await message.answer("❌ Использование: /setmaxbet 100")


@router.message(Command("setwithfee"))
async def cmd_setwithfee(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = float(message.text.split()[1])
        await set_setting("withdrawal_fee", str(val))
        await message.answer(f"✅ Комиссия вывода: {val*100:.0f}%")
    except Exception:
        await message.answer("❌ Использование: /setwithfee 0.05")


@router.message(Command("setwallet"))
async def cmd_setwallet(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        wallet = message.text.split()[1]
        await set_setting("collection_wallet", wallet)
        await message.answer(f"✅ Кошелёк установлен: {wallet[:20]}...")
    except Exception:
        await message.answer("❌ Использование: /setwallet EQ...")


@router.message(Command("addbalance"))
async def cmd_addbalance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        tg_id = int(parts[1])
        amount = float(parts[2])
        new_bal = await update_balance(tg_id, amount)
        await log_transaction(tg_id, "admin_add", amount, "completed", comment=f"admin:{message.from_user.id}")
        await message.answer(f"✅ Начислено {amount} TON пользователю {tg_id}\nБаланс: {new_bal:.4f}")
    except Exception:
        await message.answer("❌ Использование: /addbalance [id] [сумма]")


@router.message(Command("subbalance"))
async def cmd_subbalance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        tg_id = int(parts[1])
        amount = float(parts[2])
        new_bal = await update_balance(tg_id, -amount)
        await log_transaction(tg_id, "admin_sub", -amount, "completed", comment=f"admin:{message.from_user.id}")
        await message.answer(f"✅ Списано {amount} TON у пользователя {tg_id}\nБаланс: {new_bal:.4f}")
    except Exception:
        await message.answer("❌ Использование: /subbalance [id] [сумма]")


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        tg_id = int(message.text.split()[1])
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_banned = True
                await session.commit()
                await message.answer(f"🚫 Пользователь {tg_id} заблокирован")
            else:
                await message.answer("Пользователь не найден")
    except Exception:
        await message.answer("❌ Использование: /ban [id]")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        tg_id = int(message.text.split()[1])
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_banned = False
                await session.commit()
                await message.answer(f"✅ Пользователь {tg_id} разблокирован")
            else:
                await message.answer("Пользователь не найден")
    except Exception:
        await message.answer("❌ Использование: /unban [id]")


@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        tg_id = int(message.text.split()[1])
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            u = result.scalar_one_or_none()
            if not u:
                await message.answer("Пользователь не найден")
                return

            ref_count = (await session.execute(
                select(func.count()).select_from(User).where(User.referrer_id == tg_id)
            )).scalar()

        text = (
            f"👤 Пользователь {tg_id}\n"
            f"@{u.username or '—'} | {u.full_name or '—'}\n"
            f"💰 Баланс: {u.balance:.4f} TON\n"
            f"👥 Рефералов: {ref_count}\n"
            f"💎 Ref бонус: {u.ref_balance:.4f} TON\n"
            f"➕ Пополнено: {u.total_deposited:.4f}\n"
            f"➖ Выведено: {u.total_withdrawn:.4f}\n"
            f"🎯 Поставлено: {u.total_wagered:.4f}\n"
            f"🏆 Выиграно: {u.total_won:.4f}\n"
            f"🚫 Бан: {'да' if u.is_banned else 'нет'}\n"
            f"📅 Регистрация: {u.created_at.strftime('%Y-%m-%d')}"
        )
        await message.answer(text)
    except Exception:
        await message.answer("❌ Использование: /userinfo [id]")
