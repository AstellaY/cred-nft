import xrpl
import json
import binascii
from typing import List, Dict, Optional
from xrpl.clients import JsonRpcClient
from xrpl.wallet import generate_faucet_wallet, Wallet
from xrpl.models.requests import AccountNFTs, AccountInfo
from xrpl.models.transactions import NFTokenMint, NFTokenCreateOffer, NFTokenBurn, NFTokenAcceptOffer
from xrpl.utils import str_to_hex
from xrpl.core import addresscodec 

XRPL_TESTNET_URL = "https://s.altnet.rippletest.net:51234"

class XRPLCredentialManager:
    def __init__(self, endpoint: str = XRPL_TESTNET_URL):
        self.client = JsonRpcClient(endpoint)

    def validate_address(self, address: str) -> Optional[str]:
        if not address: return None
        try:
            clean_addr = "".join(c for c in str(address) if c.isalnum())
            addresscodec.decode_classic_address(clean_addr)
            return clean_addr
        except: return None

    def generate_faucet_wallet(self):
        return generate_faucet_wallet(self.client, debug=True)

    def get_balance(self, address: str) -> str:
        try:
            request = AccountInfo(account=address, ledger_index="validated")
            response = self.client.request(request)
            return str(int(response.result["account_data"]["Balance"]) / 1_000_000)
        except: return "0"

    def issue_bulk_credentials(self, seed: str, students_data: List[Dict], taxon: int, metadata: Dict):
        issuer_wallet = Wallet.from_seed(seed.strip())
        uri_hex = str_to_hex(json.dumps(metadata))
        results = []

        for student in students_data:
            addr = self.validate_address(student.get('addr'))
            s_seed = str(student.get('seed', '')).strip()
            if not addr:
                results.append({"student": "Invalid", "status": "Failed: Checksum Error"})
                continue

            try:
                mint_tx = NFTokenMint(
                    account=issuer_wallet.classic_address, 
                    uri=uri_hex, 
                    flags=9, 
                    nftoken_taxon=int(taxon)
                )
                mint_res = xrpl.transaction.submit_and_wait(mint_tx, self.client, issuer_wallet)
                nft_id = self._extract_nft_id(mint_res.result["meta"])
                
                if nft_id:
                    offer_tx = NFTokenCreateOffer(
                        account=issuer_wallet.classic_address, 
                        nftoken_id=nft_id, 
                        amount="0", 
                        destination=addr, 
                        flags=1 
                    )
                    offer_res = xrpl.transaction.submit_and_wait(offer_tx, self.client, issuer_wallet)
                    offer_idx = self._extract_offer_index(offer_res.result["meta"])
                    
                    if s_seed and offer_idx:
                        student_wallet = Wallet.from_seed(s_seed)
                        accept_tx = NFTokenAcceptOffer(account=student_wallet.classic_address, nftoken_sell_offer=offer_idx)
                        xrpl.transaction.submit_and_wait(accept_tx, self.client, student_wallet)
                        results.append({"student": addr, "nft_id": nft_id, "status": "Success: Claimed"})
                    else:
                        results.append({"student": addr, "nft_id": nft_id, "status": "Offer Created"})
            except Exception as e:
                results.append({"student": addr, "status": f"Error: {str(e)}"})
        return results

    def get_student_portfolio(self, account_address: str):
        clean = self.validate_address(account_address)
        if not clean: return []
        request = AccountNFTs(account=clean, ledger_index="validated")
        try:
            response = self.client.request(request)
            return response.result.get("account_nfts", [])
        except: return []

    def verify_credential(self, nft_id: str) -> Dict:
        try:
            issuer_hex = nft_id[8:48]
            issuer_addr = addresscodec.encode_classic_address(binascii.unhexlify(issuer_hex))
            return {"issuer": issuer_addr, "status": "Verified Authentic"}
        except: return {"status": "Invalid ID"}

    def burn_credential(self, seed: str, nftoken_id: str, owner_address: Optional[str] = None):
        wallet = Wallet.from_seed(seed.strip())
        burn_tx = NFTokenBurn(
            account=wallet.classic_address, 
            nftoken_id=nftoken_id.strip(),
            owner=owner_address.strip() if owner_address else None
        )
        return xrpl.transaction.submit_and_wait(burn_tx, self.client, wallet).result

    def _extract_nft_id(self, meta: Dict) -> Optional[str]:
        for node in meta.get("AffectedNodes", []):
            for key in ["CreatedNode", "ModifiedNode"]:
                if key in node and node[key]["LedgerEntryType"] == "NFTokenPage":
                    fields = node[key].get("NewFields") or node[key].get("FinalFields")
                    if fields and "NFTokens" in fields:
                        return fields["NFTokens"][-1]["NFToken"]["NFTokenID"]
        return None

    def _extract_offer_index(self, meta: Dict) -> Optional[str]:
        for node in meta.get("AffectedNodes", []):
            if "CreatedNode" in node and node["CreatedNode"]["LedgerEntryType"] == "NFTokenOffer":
                return node["CreatedNode"].get("LedgerIndex")
        return None