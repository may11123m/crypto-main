import aiohttp
import logging

logger = logging.getLogger(__name__)

class FuturesService:
    def __init__(self):
        self.base_url = "https://fapi.binance.com"

    async def get_futures_data(self, symbol: str) -> dict:
        """
        Fetches Funding Rate, Open Interest, and Long/Short Ratio for a symbol from Binance Futures.
        """
        clean_symbol = symbol.strip().upper().replace("USDT", "")
        pair = f"{clean_symbol}USDT"

        premium_url = f"{self.base_url}/fapi/v1/premiumIndex?symbol={pair}"
        oi_url = f"{self.base_url}/fapi/v1/openInterest?symbol={pair}"
        ls_url = f"{self.base_url}/futures/data/globalLongShortAccountRatio?symbol={pair}&period=5m&limit=1"

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Fetch Premium Index & Funding Rate
                async with session.get(premium_url, timeout=5) as p_resp:
                    if p_resp.status != 200:
                        return {"error": f"Symbol '{pair}' not found on Futures market."}
                    p_data = await p_resp.json()

                # 2. Fetch Open Interest
                async with session.get(oi_url, timeout=5) as oi_resp:
                    oi_data = await oi_resp.json() if oi_resp.status == 200 else {}

                # 3. Fetch Long/Short Ratio
                async with session.get(ls_url, timeout=5) as ls_resp:
                    ls_data = await ls_resp.json() if ls_resp.status == 200 else []

                # Extracting metrics
                mark_price = float(p_data.get("markPrice", 0))
                funding_rate = float(p_data.get("lastFundingRate", 0)) * 100  # Percentage
                open_interest_amount = float(oi_data.get("openInterest", 0))
                open_interest_usd = open_interest_amount * mark_price

                ls_item = ls_data[0] if isinstance(ls_data, list) and len(ls_data) > 0 else {}
                ls_ratio = float(ls_item.get("longShortRatio", 1.0))
                long_account = float(ls_item.get("longAccount", 0.5)) * 100
                short_account = float(ls_item.get("shortAccount", 0.5)) * 100

                # Sentiment & Signal Analysis
                if funding_rate > 0.05:
                    funding_signal = "🔥 High Long Bias (Overheated)"
                elif funding_rate < -0.01:
                    funding_signal = "🧊 Short Squeeze Potential"
                else:
                    funding_signal = "⚖️ Balanced Rate"

                return {
                    "symbol": pair,
                    "mark_price": mark_price,
                    "funding_rate": funding_rate,
                    "funding_signal": funding_signal,
                    "open_interest_usd": open_interest_usd,
                    "long_short_ratio": ls_ratio,
                    "long_pct": long_account,
                    "short_pct": short_account
                }

        except Exception as e:
            logger.error(f"Error fetching futures data for {pair}: {e}")
            return {"error": "Failed to connect to Futures API server."}

futures_service = FuturesService()