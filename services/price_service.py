import aiohttp
import logging

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self):
        # Binance & MEXC Public APIs
        self.binance_url = "https://api.binance.com/api/v3/ticker/24hr"
        self.mexc_url = "https://api.mexc.com/api/v3/ticker/24hr"

    async def get_crypto_price(self, symbol: str = "BTC") -> dict:
        """
        Fetches 24h ticker price from Binance with automatic fallback to MEXC.
        Returns a formatted dictionary with market metrics.
        """
        clean_symbol = symbol.upper().replace("USDT", "").replace("/", "").strip()
        pair = f"{clean_symbol}USDT"

        # Try Source 1: Binance
        data = await self._fetch_binance(pair)
        if data:
            data["source"] = "Binance"
            return data

        # Try Source 2: MEXC (Fallback)
        logger.warning(f"⚠️ Binance unavailable for {pair}. Trying MEXC fallback...")
        data = await self._fetch_mexc(pair)
        if data:
            data["source"] = "MEXC"
            return data

        return {"error": f"Symbol '{clean_symbol}' not found on active exchanges."}

    async def _fetch_binance(self, pair: str):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.binance_url}?symbol={pair}", timeout=5) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        return {
                            "symbol": pair,
                            "price": float(res["lastPrice"]),
                            "change_24h": float(res["priceChangePercent"]),
                            "high_24h": float(res["highPrice"]),
                            "low_24h": float(res["lowPrice"]),
                            "volume": float(res["quoteVolume"])
                        }
        except Exception as e:
            logger.error(f"Error fetching from Binance: {e}")
        return None

    async def _fetch_mexc(self, pair: str):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mexc_url}?symbol={pair}", timeout=5) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        return {
                            "symbol": pair,
                            "price": float(res["lastPrice"]),
                            "change_24h": float(res["priceChangePercent"]) * 100 if abs(float(res["priceChangePercent"])) < 1 else float(res["priceChangePercent"]),
                            "high_24h": float(res["highPrice"]),
                            "low_24h": float(res["lowPrice"]),
                            "volume": float(res["quoteVolume"])
                        }
        except Exception as e:
            logger.error(f"Error fetching from MEXC: {e}")
        return None

# Singleton instance
price_service = PriceService()