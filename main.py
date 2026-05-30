import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import get_or_create_user, get_user, async_session
from sqlalchemy import select, desc
from database.models import BetHistory, Transaction
from utils.keyboards import main_menu_kb, deposit_kb, back_kb

router = Router()

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


class WithdrawStates(StatesGroup):
    waiting_wallet = State()
    waiting_amount = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_ref_link(bot_username: str, tg_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{tg_id}"


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    referrer_id = None

    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except ValueError:
            pass

    user = await get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referrer_id=referrer_id,
    )

    if user.is_banned:
        await message.answer("🚫 Ваш аккаунт заблокирован.")
        return

    text = (
        f"🎰 ═══════════════════\n"
        f"  Добро пожаловать в\n"
        f"  💎 LEPS CASINO 💎\n"
        f"════════════════════\n\n"
        f"👤 {message.from_user.full_name}\n"
        f"💰 Баланс: {user.balance:.4f} TON\n\n"
        f"🎮 Выбери игру и испытай удачу!\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(call.from_user.id)
    if not user:
        await call.answer()
        return

    text = (
        f"🎰 ═══════════════════\n"
        f"    💎 LEPS CASINO 💎\n"
        f"════════════════════\n\n"
        f"💰 Баланс: {user.balance:.4f} TON\n\n"
        f"🎮 Выбери игру:\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await call.message.edit_text(text, reply_markup=main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "balance")
async def cb_balance(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    if not user:
        await call.answer("Пользователь не найден", show_alert=True)
        return

    text = (
        f"💰 ═══════════════════\n"
        f"       БАЛАНС\n"
        f"════════════════════\n\n"
        f"💎 Основной: {user.balance:.4f} TON\n"
        f"👥 Реферальный: {user.ref_balance:.4f} TON\n\n"
        f"📊 Статистика:\n"
        f"  ➕ Внесено: {user.total_deposited:.4f} TON\n"
        f"  ➖ Выведено: {user.total_withdrawn:.4f} TON\n"
        f"  🎯 Поставлено: {user.total_wagered:.4f} TON\n"
        f"  🏆 Выиграно: {user.total_won:.4f} TON\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=back_kb("main_menu"))
    await call.answer()


@router.callback_query(F.data == "deposit")
async def cb_deposit(call: CallbackQuery):
    text = (
        f"💳 ═══════════════════\n"
        f"     ПОПОЛНЕНИЕ\n"
        f"════════════════════\n\n"
        f"Выбери способ пополнения:\n\n"
        f"🤖 @send — перевод с комментарием\n"
        f"🚀 xRocket — Rocket кошелёк\n"
        f"⭐ Stars — Telegram Stars\n"
        f"💎 TON — прямой перевод\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=deposit_kb())
    await call.answer()


@router.callback_query(F.data == "dep_send")
async def cb_dep_send(call: CallbackQuery):
    tg_id = call.from_user.id
    text = (
        f"🤖 ПОПОЛНЕНИЕ ЧЕРЕЗ @send\n"
        f"════════════════════\n\n"
        f"1️⃣ Открой бота @send\n"
        f"2️⃣ Переведи нужную сумму TON\n"
        f"3️⃣ В комментарии укажи:\n\n"
        f"<code>{tg_id}</code>\n\n"
        f"⚠️ Без комментария пополнение не зачислится!\n"
        f"✅ Средства поступят автоматически\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=back_kb("deposit"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "dep_xrocket")
async def cb_dep_xrocket(call: CallbackQuery):
    tg_id = call.from_user.id
    text = (
        f"🚀 ПОПОЛНЕНИЕ ЧЕРЕЗ xRocket\n"
        f"════════════════════\n\n"
        f"1️⃣ Открой @xrocket\n"
        f"2️⃣ Переведи TON на адрес кошелька\n"
        f"3️⃣ Укажи комментарий:\n\n"
        f"<code>{tg_id}</code>\n\n"
        f"✅ Средства поступят автоматически\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=back_kb("deposit"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "dep_ton")
async def cb_dep_ton(call: CallbackQuery):
    from database.models import get_setting
    wallet = await get_setting("collection_wallet", "не настроен")
    tg_id = call.from_user.id
    text = (
        f"💎 ПОПОЛНЕНИЕ TON\n"
        f"════════════════════\n\n"
        f"Адрес кошелька:\n"
        f"<code>{wallet}</code>\n\n"
        f"Обязательный комментарий:\n"
        f"<code>{tg_id}</code>\n\n"
        f"⚠️ Без комментария с вашим ID\n"
        f"пополнение не зачислится!\n\n"
        f"⏱ Обработка до 5 минут\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=back_kb("deposit"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "referral")
async def cb_referral(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    bot = call.bot
    bot_info = await bot.get_me()

    ref_link = get_ref_link(bot_info.username, call.from_user.id)

    # Count referrals
    async with async_session() as session:
        from database.models import User
        from sqlalchemy import func
        result = await session.execute(
            select(func.count()).where(User.referrer_id == call.from_user.id)
        )
        ref_count = result.scalar() or 0

    text = (
        f"👥 ═══════════════════\n"
        f"   РЕФЕРАЛЬНАЯ СИСТЕМА\n"
        f"════════════════════\n\n"
        f"💰 Получай 10% от проигрышей\n"
        f"   приглашённых игроков!\n\n"
        f"🔗 Твоя ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 Рефералов: {ref_count}\n"
        f"💎 Заработано: {user.ref_balance:.4f} TON\n\n"
        f"ℹ️ Бонус начисляется автоматически\n"
        f"   в момент проигрыша реферала\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=back_kb("main_menu"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "bet_history")
async def cb_bet_history(call: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(BetHistory)
            .where(BetHistory.tg_id == call.from_user.id)
            .order_by(desc(BetHistory.created_at))
            .limit(10)
        )
        bets = result.scalars().all()

    if not bets:
        text = "📊 История ставок пуста"
    else:
        lines = ["📊 ═══ ИСТОРИЯ СТАВОК ═══\n"]
        for b in bets:
            icon = "✅" if b.profit >= 0 else "❌"
            lines.append(
                f"{icon} {b.game.upper()} | "
                f"Ставка: {b.bet_amount:.3f} | "
                f"{'+'if b.profit>=0 else ''}{b.profit:.3f} TON"
            )
        text = "\n".join(lines)

    await call.message.edit_text(text, reply_markup=back_kb("main_menu"))
    await call.answer()


@router.callback_query(F.data == "withdraw")
async def cb_withdraw_start(call: CallbackQuery, state: FSMContext):
    user = await get_user(call.from_user.id)
    from database.models import get_setting
    fee = float(await get_setting("withdrawal_fee", "0.05"))
    min_wd = float(await get_setting("min_withdraw", "1.0"))

    text = (
        f"📤 ═══════════════════\n"
        f"       ВЫВОД\n"
        f"════════════════════\n\n"
        f"💰 Доступно: {user.balance:.4f} TON\n"
        f"📉 Комиссия: {fee*100:.0f}%\n"
        f"💎 Минимум: {min_wd} TON\n\n"
        f"Введи TON-адрес для вывода:\n"
        f"════════════════════"
    )
    await state.set_state(WithdrawStates.waiting_wallet)
    await call.message.edit_text(text, reply_markup=back_kb("main_menu"))
    await call.answer()


@router.message(WithdrawStates.waiting_wallet)
async def process_withdraw_wallet(message: Message, state: FSMContext):
    wallet = message.text.strip()
    if len(wallet) < 48:
        await message.answer("❌ Неверный TON-адрес. Попробуй снова:")
        return

    await state.update_data(wallet=wallet)
    await state.set_state(WithdrawStates.waiting_amount)
    await message.answer(f"✅ Адрес принят.\n\nВведи сумму вывода в TON:")


@router.message(WithdrawStates.waiting_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число. Например: 1.5")
        return

    from database.models import get_setting, log_transaction
    from sqlalchemy import select
    from database.models import WithdrawRequest, User, async_session
    import datetime

    user = await get_user(message.from_user.id)
    fee_pct = float(await get_setting("withdrawal_fee", "0.05"))
    min_wd = float(await get_setting("min_withdraw", "1.0"))

    if amount < min_wd:
        await message.answer(f"❌ Минимальная сумма вывода: {min_wd} TON")
        return
    if amount > user.balance:
        await message.answer(f"❌ Недостаточно средств. Баланс: {user.balance:.4f} TON")
        return

    fee = round(amount * fee_pct, 6)
    net = round(amount - fee, 6)
    data = await state.get_data()
    wallet = data["wallet"]

    # Deduct balance and create request
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
        u = result.scalar_one_or_none()
        u.balance -= amount
        u.total_withdrawn += net

        wr = WithdrawRequest(
            tg_id=message.from_user.id,
            amount=amount,
            fee=fee,
            net_amount=net,
            wallet=wallet,
        )
        session.add(wr)
        await session.commit()
        wr_id = wr.id

    await log_transaction(message.from_user.id, "withdraw", amount, "pending", comment=f"wallet:{wallet}")

    await state.clear()
    await message.answer(
        f"📤 Заявка #{wr_id} принята!\n\n"
        f"💰 Сумма: {amount:.4f} TON\n"
        f"📉 Комиссия: {fee:.4f} TON\n"
        f"💎 К выплате: {net:.4f} TON\n"
        f"📬 Адрес: {wallet[:20]}...\n\n"
        f"⏱ Обработка: до 24 часов",
        reply_markup=main_menu_kb()
    )

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"💸 НОВАЯ ЗАЯВКА НА ВЫВОД #{wr_id}\n\n"
                f"👤 Пользователь: {message.from_user.id}\n"
                f"💰 Сумма: {amount:.4f} TON\n"
                f"💎 К выплате: {net:.4f} TON\n"
                f"📬 Адрес: {wallet}"
            )
        except Exception:
            pass
