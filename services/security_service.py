import aiohttp
import logging

logger = logging.getLogger(__name__)

class SecurityService:
    def __init__(self):
        # GoPlus Security API for EVM chains
        self.goplus_url = "https://api.gopluslabs.io/api/v1/token_security"

    async def check_token_security(self, contract_address: str, chain_id: str = "1") -> dict:
        """
        Audits token contract address via GoPlus Security API.
        Checks for Honeypot, buy/sell taxes, mintable function, and proxy risk.
        """
        clean_address = contract_address.strip().lower()
        url = f"{self.goplus_url}/{chain_id}?contract_addresses={clean_address}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=7) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get("result", {}).get(clean_address, {})

                        if not result:
                            return {"error": f"Contract address not found on Chain ID {chain_id}."}

                        is_honeypot = result.get("is_honeypot", "0") == "1"
                        buy_tax = float(result.get("buy_tax", 0) or 0) * 100
                        sell_tax = float(result.get("sell_tax", 0) or 0) * 100
                        is_open_source = result.get("is_open_source", "0") == "1"
                        is_proxy = result.get("is_proxy", "0") == "1"
                        is_mintable = result.get("is_mintable", "0") == "1"
                        owner_address = result.get("owner_address", "Renounced / None")

                        # Risk Level Assessment
                        risk_score = 0
                        risk_flags = []

                        if is_honeypot:
                            risk_score += 100
                            risk_flags.append("🚨 HONEYPOT DETECTED (Cannot Sell!)")

                        if buy_tax > 10:
                            risk_score += 25
                            risk_flags.append(f"⚠️ High Buy Tax ({buy_tax:.1f}%)")

                        if sell_tax > 10:
                            risk_score += 25
                            risk_flags.append(f"⚠️ High Sell Tax ({sell_tax:.1f}%)")

                        if is_mintable:
                            risk_score += 20
                            risk_flags.append("⚠️ Token is Mintable (Unlimited Supply Risk)")

                        if is_proxy:
                            risk_score += 15
                            risk_flags.append("⚠️ Proxy Contract (Code can be modified)")

                        if not is_open_source:
                            risk_score += 30
                            risk_flags.append("🔴 Unverified Source Code")

                        if risk_score >= 70:
                            risk_level = "HIGH RISK 🔴"
                        elif risk_score >= 30:
                            risk_level = "MEDIUM RISK 🟡"
                        else:
                            risk_level = "LOW RISK / SAFE 🟢"

                        return {
                            "contract": clean_address,
                            "token_name": result.get("token_name", "Unknown"),
                            "token_symbol": result.get("token_symbol", "N/A").upper(),
                            "is_honeypot": "YES 🚨" if is_honeypot else "NO ✅",
                            "buy_tax": f"{buy_tax:.1f}%",
                            "sell_tax": f"{sell_tax:.1f}%",
                            "is_open_source": "Verified ✅" if is_open_source else "Unverified ❌",
                            "is_mintable": "YES ⚠️" if is_mintable else "NO ✅",
                            "owner": owner_address if owner_address else "Renounced / None",
                            "risk_level": risk_level,
                            "risk_flags": risk_flags
                        }
        except Exception as e:
            logger.error(f"Error checking token security: {e}")

        return {"error": "Failed to connect to security audit server."}

security_service = SecurityService()