import aiohttp
import logging
import re

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        self.dexscreener_url = "https://api.dexscreener.com/latest/dex/search"

    def is_contract_address(self, query: str) -> bool:
        """Checks if input string resembles an EVM or Solana contract address."""
        query = query.strip()
        # EVM Address check (0x followed by 40 hex chars)
        if re.match(r"^0x[a-fA-F0-9]{40}$", query):
            return True
        # Solana Address check (Base58 string between 32 and 44 characters)
        if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", query) and not query.isalnum() is False and len(query) > 30:
            return True
        return False

    async def search_token(self, query: str) -> list:
        """
        Smart search across CEX & DEX pools by Name, Symbol, or Contract Address.
        Returns a formatted list of top matching pairs.
        """
        clean_query = query.strip()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.dexscreener_url}?q={clean_query}", timeout=7) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        pairs = res.get("pairs", [])
                        
                        if not pairs:
                            return []

                        # Format & limit top 5 results sorted by liquidity/volume
                        results = []
                        for pair in pairs[:5]:
                            base_token = pair.get("baseToken", {})
                            results.append({
                                "name": base_token.get("name", "Unknown"),
                                "symbol": base_token.get("symbol", "N/A").upper(),
                                "contract": base_token.get("address", "N/A"),
                                "price_usd": float(pair.get("priceUsd", 0) or 0),
                                "change_24h": float(pair.get("priceChange", {}).get("h24", 0) or 0),
                                "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                                "liquidity": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                                "chain": pair.get("chainId", "unknown").capitalize(),
                                "dex": pair.get("dexId", "DEX").capitalize(),
                                "url": pair.get("url", "")
                            })
                        return results
        except Exception as e:
            logger.error(f"Error in SearchService: {e}")
            return []

search_service = SearchService()