import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

from services.price_service import price_service
from services.search_service import search_service
from services.indicator_service import indicator_service
from services.security_service import security_service
from services.futures_service import futures_service
from services.alert_service import alert_service

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Health Check for Render
async def handle_health_check(request):
    return web.Response(text="Bot is online and running!")

# Background Alert Monitor
async def check_alerts_loop():
    while True:
        try:
            alerts = await alert_service.get_all_alerts()
            for alert in alerts:
                data = await price_service.get_crypto_price(alert['symbol'])
                if "error" in data:
                    continue

                current_price = data['price']
                triggered = False

                if alert['condition'] == "ABOVE" and current_price >= alert['target_price']:
                    triggered = True
                elif alert['condition'] == "BELOW" and current_price <= alert['target_price']:
                    triggered = True

                if triggered:
                    msg_text = (
                        f"🚨 **PRICE ALERT TRIGGERED!** 🚨\n\n"
                        f"💎 **Token:** `{alert['symbol']}`\n"
                        f"🎯 **Target Price:** `${alert['target_price']:,.4f}`\n"
                        f"💵 **Current Price:** `${current_price:,.4f}`\n"
                    )
                    try:
                        await bot.send_message(chat_id=alert['user_id'], text=msg_text, parse_mode="Markdown")
                        await alert_service.remove_triggered_alert(alert['id'])
                    except Exception as err:
                        logger.error(f"Failed to send alert: {err}")
        except Exception as e:
            logger.error(f"Alert loop error: {e}")

        await asyncio.sleep(30)


# Main Menu Keyboard
def get_main_keyboard():
    kb = [
        [
            InlineKeyboardButton(text="📊 Spot Price", callback_data="menu_spot"),
            InlineKeyboardButton(text="📈 Technical Analysis", callback_data="menu_ta")
        ],
        [
            InlineKeyboardButton(text="⚡ Futures Data", callback_data="menu_futures"),
            InlineKeyboardButton(text="🚨 Set Price Alert", callback_data="guide_alert")
        ],
        [
            InlineKeyboardButton(text="🛡️ Security Audit", callback_data="guide_security"),
            InlineKeyboardButton(text="📋 My Active Alerts", callback_data="cmd_myalerts")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# Coin Selection Keyboards (Eliminates typing)
def get_coin_keyboard(action_prefix):
    kb = [
        [
            InlineKeyboardButton(text="⚡ BTC", callback_data=f"{action_prefix}_BTC"),
            InlineKeyboardButton(text="💎 ETH", callback_data=f"{action_prefix}_ETH"),
            InlineKeyboardButton(text="🟣 SOL", callback_data=f"{action_prefix}_SOL")
        ],
        [
            InlineKeyboardButton(text="🟡 BNB", callback_data=f"{action_prefix}_BNB"),
            InlineKeyboardButton(text="🐸 PEPE", callback_data=f"{action_prefix}_PEPE"),
            InlineKeyboardButton(text="🐕 DOGE", callback_data=f"{action_prefix}_DOGE")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="menu_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(Command("start"))
async def start_handler(message: Message):
    welcome_text = "🌐 **Welcome to CryptoPulse Pro!**\n\nSelect an option from the menu below:"
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")


# Navigation & Menus
@dp.callback_query(F.data == "menu_main")
async def handle_main_menu(callback: CallbackQuery):
    await callback.message.edit_text("🌐 **Welcome to CryptoPulse Pro!**\n\nSelect an option from the menu below:", reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "menu_spot")
async def handle_spot_menu(callback: CallbackQuery):
    await callback.message.edit_text("📊 **Select a Token for Spot Price:**", reply_markup=get_coin_keyboard("spot"), parse_mode="Markdown")

@dp.callback_query(F.data == "menu_ta")
async def handle_ta_menu(callback: CallbackQuery):
    await callback.message.edit_text("📈 **Select a Token for Technical Analysis (1H):**", reply_markup=get_coin_keyboard("ta"), parse_mode="Markdown")

@dp.callback_query(F.data == "menu_futures")
async def handle_futures_menu(callback: CallbackQuery):
    await callback.message.edit_text("⚡ **Select a Token for Futures Metrics (Funding & OI):**", reply_markup=get_coin_keyboard("ft"), parse_mode="Markdown")


# Handlers for Quick Coin Buttons
@dp.callback_query(F.data.startswith("spot_"))
async def handle_spot_calc(callback: CallbackQuery):
    symbol = callback.data.replace("spot_", "")
    await callback.answer(f"Fetching {symbol} price...")
    
    cex_data = await price_service.get_crypto_price(symbol)
    if "error" not in cex_data:
        change_emoji = "🟢" if cex_data['change_24h'] >= 0 else "🔴"
        response = (
            f"📊 **Market Overview: {cex_data['symbol']}**\n\n"
            f"💵 **Price:** `${cex_data['price']:,.4f}`\n"
            f"{change_emoji} **24h Change:** `{cex_data['change_24h']:+.2f}%`\n"
            f"📈 **24h High:** `${cex_data['high_24h']:,.4f}`\n"
            f"📉 **24h Low:** `${cex_data['low_24h']:,.4f}`\n"
            f"💰 **24h Volume:** `${cex_data['volume']:,.2f}`\n"
        )
        await callback.message.answer(response, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("ta_"))
async def handle_ta_calc(callback: CallbackQuery):
    symbol = callback.data.replace("ta_", "")
    await callback.answer(f"Analyzing {symbol}...")
    
    analysis = await indicator_service.analyze_symbol(symbol, interval="1h")
    if "error" not in analysis:
        response = (
            f"⚡ **Technical Signals: {analysis['symbol']} (1H Timeframe)**\n\n"
            f"📊 **Market Sentiment:** `{analysis['sentiment']}`\n"
            f"🎯 **Technical Score:** `{analysis['score']} / 10`\n\n"
            f"🔹 **RSI (14):** `{analysis['rsi']}` ➔ {analysis['rsi_status']}\n"
            f"🔹 **MACD Signal:** {analysis['macd_status']}\n"
            f"🔹 **EMA 200 Trend:** {analysis['trend_status']}\n\n"
            f"⚠️ *Not financial advice*"
        )
        await callback.message.answer(response, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("ft_"))
async def handle_ft_calc(callback: CallbackQuery):
    symbol = callback.data.replace("ft_", "")
    await callback.answer(f"Fetching {symbol} futures data...")
    
    ft_data = await futures_service.get_futures_data(symbol)
    if "error" not in ft_data:
        funding_emoji = "🔴" if ft_data['funding_rate'] > 0.03 else ("🟢" if ft_data['funding_rate'] < 0 else "⚪")
        response = (
            f"📊 **Futures Metrics: {ft_data['symbol']}**\n\n"
            f"💵 **Mark Price:** `${ft_data['mark_price']:,.2f}`\n\n"
            f"{funding_emoji} **Funding Rate (8h):** `{ft_data['funding_rate']:+.4f}%`\n"
            f"📌 **Market Sentiment:** `{ft_data['funding_signal']}`\n\n"
            f"💧 **Open Interest (USD):** `${ft_data['open_interest_usd']:,.0f}`\n"
            f"⚖️ **Long / Short Ratio:** `{ft_data['long_short_ratio']:.2f}`\n"
            f"• **Long Accounts:** `{ft_data['long_pct']:.1f}%` 🟢\n"
            f"• **Short Accounts:** `{ft_data['short_pct']:.1f}%` 🔴\n\n"
            f"⚠️ *Not financial advice*"
        )
        await callback.message.answer(response, parse_mode="Markdown")


# Guides for Alert and Security
@dp.callback_query(F.data == "guide_alert")
async def handle_alert_guide(callback: CallbackQuery):
    text = "🚨 **Set Price Alert:**\nSend a command in this format:\n`alert btc 65000`"
    await callback.answer()
    await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data == "guide_security")
async def handle_security_guide(callback: CallbackQuery):
    text = "🛡️ **Smart Contract Audit:**\nType `check` followed by the contract address:\nExample:\n`check 0x6b175474e89094c44da98b954eedeac495271d0f`"
    await callback.answer()
    await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data == "cmd_myalerts")
async def handle_my_alerts_callback(callback: CallbackQuery):
    await callback.answer()
    await handle_my_alerts(callback.message, user_id=callback.from_user.id)


# Direct Custom Symbol / Search Handler
@dp.message(F.text)
async def handle_custom_search(message: Message):
    query = message.text.strip()
    if query.startswith("/"):
        return

    msg = await message.answer(f"🔍 Searching data for **'{query}'**...")

    # First try Spot CEX
    cex_data = await price_service.get_crypto_price(query)
    if "error" not in cex_data:
        change_emoji = "🟢" if cex_data['change_24h'] >= 0 else "🔴"
        response = (
            f"📊 **Market Overview: {cex_data['symbol']}**\n\n"
            f"💵 **Price:** `${cex_data['price']:,.4f}`\n"
            f"{change_emoji} **24h Change:** `{cex_data['change_24h']:+.2f}%`\n"
            f"📈 **24h High:** `${cex_data['high_24h']:,.4f}`\n"
            f"📉 **24h Low:** `${cex_data['low_24h']:,.4f}`\n"
            f"💰 **24h Volume:** `${cex_data['volume']:,.2f}`\n"
        )
        await msg.edit_text(response, parse_mode="Markdown")
        return

    # Fallback to DEX Search
    dex_results = await search_service.search_token(query)
    if dex_results:
        first = dex_results[0]
        change_emoji = "🟢" if first['change_24h'] >= 0 else "🔴"
        response = (
            f"🌐 **{first['name']} ({first['symbol']})**\n"
            f"🔗 **Chain:** `{first['chain']}` | **DEX:** `{first['dex']}`\n\n"
            f"💵 **Price:** `${first['price_usd']:,.6f}`\n"
            f"{change_emoji} **24h Change:** `{first['change_24h']:+.2f}%`\n"
            f"💧 **Liquidity:** `${first['liquidity']:,.2f}`\n"
            f"📝 **Contract:**\n`{first['contract']}`"
        )
        await msg.edit_text(response, parse_mode="Markdown")
        return

    await msg.edit_text(f"❌ Symbol or token **'{query}'** not found.")


# Alert logic handlers
@dp.message(F.text.lower().startswith("alert "))
async def handle_set_alert(message: Message):
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer("❌ **Usage:** `alert <symbol> <target_price>`", parse_mode="Markdown")
        return

    symbol = parts[1].upper()
    try:
        target_price = float(parts[2])
    except ValueError:
        await message.answer("❌ Invalid target price.")
        return

    data = await price_service.get_crypto_price(symbol)
    if "error" in data:
        await message.answer(f"❌ Symbol **'{symbol}'** not found.")
        return

    current_price = data['price']
    condition = "ABOVE" if target_price > current_price else "BELOW"

    alert_id = await alert_service.add_alert(
        user_id=message.from_user.id,
        symbol=symbol,
        target_price=target_price,
        condition=condition
    )

    await message.answer(f"✅ Alert set for `{symbol}` at `${target_price:,.4f}` [ID: `{alert_id}`]", parse_mode="Markdown")


@dp.message(Command("myalerts"))
async def handle_my_alerts(message: Message, user_id: int = None):
    uid = user_id if user_id else message.from_user.id
    user_alerts = await alert_service.get_user_alerts(uid)

    if not user_alerts:
        await message.answer("ℹ️ You have no active alerts.")
        return

    text = "📋 **Your Active Price Alerts:**\n\n"
    for a in user_alerts:
        cond_icon = "📈" if a['condition'] == "ABOVE" else "📉"
        text += f"• **ID `{a['id']}`** | `{a['symbol']}` {cond_icon} `${a['target_price']:,.4f}`\n"

    await message.answer(text, parse_mode="Markdown")


async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing!")
        return

    await alert_service.init_db()
    asyncio.create_task(check_alerts_loop())

    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("🚀 Bot is running...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
