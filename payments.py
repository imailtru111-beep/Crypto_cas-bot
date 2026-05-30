from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice,
    PreCheckoutQuery, SuccessfulPayment
)
from database.models import get_user, update_balance, log_transaction
from utils.keyboards import stars_amounts_kb, back_kb

router = Router()

# 1 Star = 0.013 TON (approximate)
STAR_TO_TON = 0.013


@router.callback_query(F.data == "dep_stars")
async def cb_dep_stars(call: CallbackQuery):
    text = (
        f"⭐ ПОПОЛНЕНИЕ STARS\n"
        f"════════════════════\n\n"
        f"Курс: 1 ⭐ = {STAR_TO_TON} TON\n\n"
        f"Выбери сумму:\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=stars_amounts_kb())
    await call.answer()


@router.callback_query(F.data.startswith("stars_buy_"))
async def cb_stars_buy(call: CallbackQuery):
    stars = int(call.data.split("_")[2])
    ton_amount = round(stars * STAR_TO_TON, 4)

    prices = [LabeledPrice(label=f"Пополнение {ton_amount} TON", amount=stars)]

    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"💎 LEPS CASINO — {ton_amount} TON",
        description=f"Пополнение баланса на {ton_amount} TON ({stars} Stars)",
        payload=f"deposit_{call.from_user.id}_{stars}",
        currency="XTR",
        prices=prices,
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload

    if payload.startswith("deposit_"):
        parts = payload.split("_")
        tg_id = int(parts[1])
        stars = int(parts[2])
        ton_amount = round(stars * STAR_TO_TON, 4)

        await update_balance(tg_id, ton_amount)

        from database.models import async_session, User
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalar_one_or_none()
            if user:
                user.total_deposited += ton_amount
                await session.commit()

        await log_transaction(
            tg_id, "deposit", ton_amount, "completed",
            provider="stars",
            external_id=payment.telegram_payment_charge_id,
            comment=f"{stars} Stars"
        )

        user = await get_user(tg_id)
        await message.answer(
            f"✅ Пополнение успешно!\n\n"
            f"⭐ Stars: {stars}\n"
            f"💎 TON: +{ton_amount}\n"
            f"💰 Баланс: {user.balance:.4f} TON"
        )
