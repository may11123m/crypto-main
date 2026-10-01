import aiohttp
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class IndicatorService:
    def __init__(self):
        self.binance_klines_url = "https://api.binance.com/api/v3/klines"

    async def analyze_symbol(self, symbol: str = "BTC", interval: str = "1h") -> dict:
        """
        Fetches OHLCV candlestick data and calculates RSI, MACD, and EMA 20/50/200.
        Returns a structured Technical Analysis summary with a overall score (1-10).
        """
        clean_symbol = symbol.upper().replace("USDT", "").replace("/", "").strip()
        pair = f"{clean_symbol}USDT"

        df = await self._fetch_klines(pair, interval)
        if df is None or len(df) < 200:
            return {"error": f"Insufficient technical data for '{clean_symbol}'."}

        # 1. EMA Calculations
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

        # 2. RSI Calculation (14 periods)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 3. MACD Calculation (12, 26, 9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # Latest values
        last = df.iloc[-1]
        close = last['close']
        rsi = last['rsi']
        ema200 = last['ema200']
        macd = last['macd']
        macd_sig = last['signal']

        # Score & Sentiment logic (Base score = 5)
        score = 5.0

        # RSI Evaluation
        if rsi < 30:
            score += 2.0
            rsi_status = "Oversold 🟢 (Potential Reversal)"
        elif rsi > 70:
            score -= 2.0
            rsi_status = "Overbought 🔴 (Correction Risk)"
        else:
            rsi_status = "Neutral ⚪"

        # EMA Trend Evaluation
        if close > ema200:
            score += 1.5
            trend_status = "Bullish Trend 🟢 (Above EMA 200)"
        else:
            score -= 1.5
            trend_status = "Bearish Trend 🔴 (Below EMA 200)"

        # MACD Evaluation
        if macd > macd_sig:
            score += 1.5
            macd_status = "Bullish Crossover 🟢"
        else:
            score -= 1.5
            macd_status = "Bearish Crossover 🔴"

        final_score = max(1.0, min(10.0, round(score, 1)))

        if final_score >= 7.0:
            sentiment = "Strongly Bullish 🚀"
        elif final_score >= 5.5:
            sentiment = "Slightly Bullish 📈"
        elif final_score <= 3.5:
            sentiment = "Strongly Bearish 📉"
        else:
            sentiment = "Neutral / Ranging ⚖️"

        return {
            "symbol": pair,
            "interval": interval,
            "price": close,
            "rsi": round(rsi, 2),
            "rsi_status": rsi_status,
            "ema20": round(last['ema20'], 4),
            "ema50": round(last['ema50'], 4),
            "ema200": round(ema200, 4),
            "macd_status": macd_status,
            "trend_status": trend_status,
            "score": final_score,
            "sentiment": sentiment
        }

    async def _fetch_klines(self, pair: str, interval: str):
        try:
            url = f"{self.binance_klines_url}?symbol={pair}&interval={interval}&limit=250"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        df = pd.DataFrame(data, columns=[
                            'open_time', 'open', 'high', 'low', 'close', 'volume',
                            'close_time', 'quote_volume', 'trades', 'tb_base', 'tb_quote', 'ignore'
                        ])
                        df['close'] = df['close'].astype(float)
                        return df
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
        return None

indicator_service = IndicatorService()