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

# Web server health check for Render free tier
async def handle_health_check(request):
    return web.Response(text="Bot is online and running!")

# Background Task to monitor price alerts
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
                        f"📊 **Condition:** Price reached target `{alert['condition']}`!"
                    )
                    try:
                        await bot.send_message(chat_id=alert['user_id'], text=msg_text, parse_mode="Markdown")
                        await alert_service.remove_triggered_alert(alert['id'])
                    except Exception as err:
                        logger.error(f"Failed to send alert to {alert['user_id']}: {err}")

        except Exception as e:
            logger.error(f"Error in alert monitoring loop: {e}")

        await asyncio.sleep(30)


# Main English Inline Keyboard
def get_main_keyboard():
    kb = [
        [
            InlineKeyboardButton(text="📊 Spot Price", callback_data="guide_price"),
            InlineKeyboardButton(text="📈 Technical Analysis (TA)", callback_data="guide_ta")
        ],
        [
            InlineKeyboardButton(text="⚡ Futures Data (FT)", callback_data="guide_futures"),
            InlineKeyboardButton(text="🚨 Set Price Alert", callback_data="guide_alert")
        ],
        [
            InlineKeyboardButton(text="🛡️ Security Audit", callback_data="guide_security"),
            InlineKeyboardButton(text="📋 My Active Alerts", callback_data="cmd_myalerts")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(Command("start"))
async def start_handler(message: Message):
    welcome_text = (
        "🌐 **Welcome to CryptoPulse Pro!**\n\n"
        "Click any button below or type your command directly:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")


# Handle inline keyboard clicks
@dp.callback_query(F.data.startswith("guide_"))
async def handle_guides(callback: CallbackQuery):
    action = callback.data.replace("guide_", "")
    
    if action == "price":
        text = "🔍 **Spot Price Check:**\nJust send the symbol or token name.\nExample: `btc`, `eth`, or `pepe`"
    elif action == "ta":
        text = "📈 **Technical Analysis:**\nType `ta` before the symbol.\nExample: `ta btc` or `ta eth`"
    elif action == "futures":
        text = "⚡ **Futures Metrics (Funding Rate & OI):**\nType `ft` before the symbol.\nExample: `ft btc` or `ft sol`"
    elif action == "alert":
        text = "🚨 **Set Price Alert:**\nSend command in this format:\n`alert btc 65000`"
    elif action == "security":
        text = "🛡️ **Smart Contract Audit:**\nType `check` before the token address:\nExample: `check 0x6b1754...`"
    else:
        text = "Unknown selection."

    await callback.answer()
    await callback.message.answer(text, parse_mode="Markdown")


@dp.callback_query(F.data == "cmd_myalerts")
async def handle_my_alerts_callback(callback: CallbackQuery):
    await callback.answer()
    await handle_my_alerts(callback.message, user_id=callback.from_user.id)


# Set Price Alert
@dp.message(F.text.lower().startswith("alert "))
async def handle_set_alert(message: Message):
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer("❌ **Usage:** `alert <symbol> <target_price>`\nExample: `alert btc 65000`", parse_mode="Markdown")
        return

    symbol = parts[1].upper()
    try:
        target_price = float(parts[2])
    except ValueError:
        await message.answer("❌ Invalid target price. Please enter numbers only.")
        return

    data = await price_service.get_crypto_price(symbol)
    if "error" in data:
        await message.answer(f"❌ Symbol **'{symbol}'** was not found on exchanges.")
        return

    current_price = data['price']
    condition = "ABOVE" if target_price > current_price else "BELOW"

    alert_id = await alert_service.add_alert(
        user_id=message.from_user.id,
        symbol=symbol,
        target_price=target_price,
        condition=condition
    )

    cond_emoji = "📈" if condition == "ABOVE" else "📉"
    response = (
        f"✅ **Price Alert Saved!** [ID: `{alert_id}`]\n\n"
        f"🪙 **Token:** `{symbol}`\n"
        f"💵 **Current Price:** `${current_price:,.4f}`\n"
        f"🎯 **Target Price:** `${target_price:,.4f}`\n"
        f"{cond_emoji} **Trigger:** When price goes `{condition}` target."
    )
    await message.answer(response, parse_mode="Markdown")


# View Active Alerts
@dp.message(Command("myalerts"))
async def handle_my_alerts(message: Message, user_id: int = None):
    uid = user_id if user_id else message.from_user.id
    user_alerts = await alert_service.get_user_alerts(uid)

    if not user_alerts:
        await message.answer("ℹ️ You have no active price alerts.")
        return

    text = "📋 **Your Active Price Alerts:**\n\n"
    for a in user_alerts:
        cond_icon = "📈" if a['condition'] == "ABOVE" else "📉"
        text += f"• **ID `{a['id']}`** | `{a['symbol']}` {cond_icon} `${a['target_price']:,.4f}`\n"

    text += "\n💡 *To delete an alert, send:* `/delalert <ID>`"
    await message.answer(text, parse_mode="Markdown")


# Delete Alert
@dp.message(Command("delalert"))
async def handle_del_alert(message: Message):
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("❌ **Usage:** `/delalert <ID>`", parse_mode="Markdown")
        return

    alert_id = int(parts[1])
    success = await alert_service.delete_alert(alert_id, message.from_user.id)

    if success:
        await message.answer(f"🗑️ Alert ID `{alert_id}` deleted successfully.", parse_mode="Markdown")
    else:
        await message.answer(f"❌ Alert ID `{alert_id}` not found or not owned by you.", parse_mode="Markdown")


# Futures Data (Supports ft btc and /ft btc)
@dp.message(F.text.func(lambda text: text.lower().startswith("ft ") or text.lower().startswith("/ft ")))
async def handle_futures(message: Message):
    clean_text = message.text.lower().replace("/ft ", "").replace("ft ", "").strip()
    msg = await message.answer(f"📈 Fetching Futures data for **{clean_text.upper()}**...")

    try:
        ft_data = await futures_service.get_futures_data(clean_text)
        if "error" in ft_data:
            await msg.edit_text(f"❌ {ft_data['error']}")
            return

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
        await msg.edit_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Futures error: {e}")
        await msg.edit_text("❌ Error fetching futures metrics.")


# Token Security Audit
@dp.message(F.text.func(lambda text: text.lower().startswith("check ") or text.lower().startswith("/check ")))
async def handle_security_check(message: Message):
    address = message.text.lower().replace("/check ", "").replace("check ", "").strip()
    msg = await message.answer(f"🛡️ Auditing smart contract address...")

    try:
        audit = await security_service.check_token_security(address, chain_id="1")
        if "error" in audit:
            await msg.edit_text(f"❌ {audit['error']}")
            return

        flags_text = "\n".join(audit['risk_flags']) if audit['risk_flags'] else "No severe risk flags detected ✅"

        response = (
            f"🛡️ **Security Audit: {audit['token_name']} ({audit['token_symbol']})**\n\n"
            f"🚦 **Risk Level:** `{audit['risk_level']}`\n"
            f"🍯 **Honeypot Test:** `{audit['is_honeypot']}`\n\n"
            f"📊 **Contract Rules:**\n"
            f"• Buy Tax: `{audit['buy_tax']}` | Sell Tax: `{audit['sell_tax']}`\n"
            f"• Open Source: `{audit['is_open_source']}`\n"
            f"• Mintable: `{audit['is_mintable']}`\n\n"
            f"⚠️ **Warnings:**\n{flags_text}"
        )
        await msg.edit_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Security check error: {e}")
        await msg.edit_text("❌ Error auditing smart contract.")


# Technical Analysis (Supports ta btc and /ta btc)
@dp.message(F.text.func(lambda text: text.lower().startswith("ta ") or text.lower().startswith("/ta ")))
async def handle_ta(message: Message):
    symbol = message.text.lower().replace("/ta ", "").replace("ta ", "").strip()
    msg = await message.answer(f"⚙️ Calculating technical indicators for **{symbol.upper()}**...")

    try:
        analysis = await indicator_service.analyze_symbol(symbol, interval="1h")
        if "error" in analysis:
            await msg.edit_text(f"❌ {analysis['error']}")
            return

        response = (
            f"⚡ **Technical Signals: {analysis['symbol']} (1H Timeframe)**\n\n"
            f"📊 **Market Sentiment:** `{analysis['sentiment']}`\n"
            f"🎯 **Technical Score:** `{analysis['score']} / 10`\n\n"
            f"🔹 **RSI (14):** `{analysis['rsi']}` ➔ {analysis['rsi_status']}\n"
            f"🔹 **MACD Signal:** {analysis['macd_status']}\n"
            f"🔹 **EMA 200 Trend:** {analysis['trend_status']}\n\n"
            f"⚠️ *Not financial advice*"
        )
        await msg.edit_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"TA error: {e}")
        await msg.edit_text("❌ Error calculating technical analysis.")


# Spot / DEX Price Search
@dp.message(F.text)
async def handle_search(message: Message):
    query = message.text.strip()
    if query.startswith("/"):
        return

    msg = await message.answer(f"🔍 Fetching price data for **'{query}'**...")

    try:
        cex_data = await price_service.get_crypto_price(query)
        if "error" not in cex_data:
            change_emoji = "🟢" if cex_data['change_24h'] >= 0 else "🔴"
            response = (
                f"📊 **Market Overview: {cex_data['symbol']}**\n\n"
                f"💵 **Price:** `${cex_data['price']:,.4f}`\n"
                f"{change_emoji} **24h Change:** `{cex_data['change_24h']:+.2f}%`\n"
                f"📈 **24h High:** `${cex_data['high_24h']:,.4f}`\n"
                f"📉 **24h Low:** `${cex_data['low_24h']:,.4f}`\n"
                f"💰 **24h Volume:** `${cex_data['volume']:,.2f}`\n\n"
                f"💡 *Tip: Type 'ta {cex_data['symbol']}' for Technical Analysis.*"
            )
            await msg.edit_text(response, parse_mode="Markdown")
            return

        dex_results = await search_service.search_token(query)
        if not dex_results:
            await msg.edit_text(f"❌ No token found matching **'{query}'**.")
            return

        first = dex_results[0]
        change_emoji = "🟢" if first['change_24h'] >= 0 else "🔴"
        response = (
            f"🌐 **{first['name']} ({first['symbol']})**\n"
            f"🔗 **Chain:** `{first['chain']}` | **DEX:** `{first['dex']}`\n\n"
            f"💵 **Price:** `${first['price_usd']:,.6f}`\n"
            f"{change_emoji} **24h Change:** `{first['change_24h']:+.2f}%`\n"
            f"💧 **Liquidity:** `${first['liquidity']:,.2f}`\n"
            f"📝 **Contract Address:**\n`{first['contract']}`"
        )
        await msg.edit_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await msg.edit_text("❌ Error searching price data.")


async def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing in .env file!")
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

    logger.info(f"🌐 Health server started on port {port}")
    logger.info("🚀 CryptoPulse Pro v2 Bot Running...")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
