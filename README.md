# 🎰 LEPS CASINO — Telegram Bot

Полноценное крипто-казино в Telegram. Рулетка, Мины, Башня. Пополнение через TON, Stars, @send, xRocket.

---

## 🚀 Деплой на Render.com (5 минут)

### Шаг 1 — Загрузи код на GitHub
1. Создай новый репозиторий на github.com
2. Загрузи все файлы этой папки

### Шаг 2 — Создай сервис на Render
1. Зайди на render.com → New → **Background Worker**
2. Подключи репозиторий GitHub
3. Настройки:
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`

### Шаг 3 — Переменные окружения
В разделе **Environment** добавь:

| Переменная | Описание | Обязательная |
|-----------|----------|:---:|
| `BOT_TOKEN` | Токен от @BotFather | ✅ |
| `ADMIN_IDS` | ID админов через запятую: `123456,654321` | ✅ |
| `TON_API_KEY` | Ключ от tonapi.io | для TON депозитов |
| `COLLECTION_WALLET` | TON адрес для сбора | для TON депозитов |
| `ROCKET_API_KEY` | Ключ xRocket | для xRocket |
| `DATABASE_URL` | PostgreSQL URL (опционально) | — |
| `WITHDRAWAL_FEE` | Комиссия вывода (0.05 = 5%) | — |

### Шаг 4 — Запуск
Нажми **Deploy**. Бот запустится автоматически.

---

## 💰 Способы пополнения

- **@send** — перевод с комментарием = ваш Telegram ID
- **xRocket** — Rocket кошелёк
- **⭐ Stars** — Telegram Stars (встроенная оплата)
- **💎 TON** — прямой перевод на кошелёк казино (автодетект через TonAPI)

---

## 🎮 Игры

### 🎰 Рулетка
- Европейская (0-36)
- Ставки: цвет (×2), чёт/нечет (×2), 1-18/19-36 (×2), дюжины (×3), колонки (×3), число (×36)

### 💣 Мины
- Поле 5×5 (25 клеток)
- От 2 до 15 мин
- Динамический коэффициент
- Забрать выигрыш в любой момент

### 🗼 Башня
- 10 этажей, 3 позиции
- 1-2 мины на этаж
- Множитель растёт с каждым этажом
- Забрать после любого этажа

---

## 👥 Реферальная система
- Уникальная ссылка для каждого пользователя
- 10% от чистых проигрышей рефералов
- Автоначисление в момент проигрыша

---

## 🔐 Команды администратора

```
/admin           — Панель администратора
/setminbet 0.1   — Минимальная ставка
/setmaxbet 100   — Максимальная ставка
/setwithfee 0.05 — Комиссия вывода (5%)
/setwallet EQ... — Кошелёк для сбора TON
/addbalance [id] [сумма] — Начислить TON
/subbalance [id] [сумма] — Списать TON
/ban [id]        — Заблокировать
/unban [id]      — Разблокировать
/userinfo [id]   — Инфо о пользователе
```

---

## 🗄 База данных

- **SQLite** (по умолчанию, файл casino.db) — для тестов
- **PostgreSQL** (через DATABASE_URL) — для продакшена

Render.com предоставляет бесплатный PostgreSQL:
**New → PostgreSQL** → скопируй Internal Database URL в `DATABASE_URL`

---

## 🛠 Локальный запуск

```bash
# Установи зависимости
pip install -r requirements.txt

# Скопируй и заполни .env
cp .env.example .env
# Отредактируй .env — добавь BOT_TOKEN и ADMIN_IDS

# Запусти
python bot.py
```

---

## 📁 Структура

```
leps_casino/
├── bot.py              # Точка входа
├── requirements.txt
├── Dockerfile
├── render.yaml
├── Procfile
├── database/
│   └── models.py       # SQLAlchemy модели
├── games/
│   ├── roulette.py     # Логика рулетки
│   ├── mines.py        # Логика мин
│   └── tower.py        # Логика башни
├── handlers/
│   ├── main.py         # Стартовое меню, баланс
│   ├── roulette.py     # Хендлер рулетки
│   ├── mines.py        # Хендлер мин
│   ├── tower.py        # Хендлер башни
│   ├── payments.py     # Stars платежи
│   └── admin.py        # Панель админа
├── payments/
│   └── ton_watcher.py  # Фоновый мониторинг TON
└── utils/
    └── keyboards.py    # Все клавиатуры
```
