import streamlit as st
import pandas as pd
import json
import binascii
from datetime import date
from xrpl_utils import XRPLCredentialManager

xrpl_manager = XRPLCredentialManager()
st.set_page_config(page_title="Institutional Registrar", layout="wide")

if "issuer_seed" not in st.session_state: st.session_state.issuer_seed = ""
if "students" not in st.session_state: st.session_state.students = ""

# --- SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Testnet Faucet")
    if st.button("🚀 Step 1: Create Issuer"):
        with st.spinner("Funding Issuer..."):
            w = xrpl_manager.generate_faucet_wallet()
            st.session_state.issuer_seed = w.seed
            st.rerun()
    st.session_state.issuer_seed = st.text_input("Issuer Seed", value=st.session_state.issuer_seed, type="password")
    if st.button("👥 Step 2: Create Test Students"):
        s_list = []
        for _ in range(2):
            s_w = xrpl_manager.generate_faucet_wallet()
            s_list.append(f"{s_w.classic_address}, {s_w.seed}")
        st.session_state.students = "\n".join(s_list)
        st.success("Students Created!")

# --- MAIN DASHBOARD ---
st.title("🏛️ XRPL Academic Registrar")
tab1, tab2, tab3 = st.tabs(["🚀 Issue Credentials", "🎓 Portfolio", "🔍 Verify & Revoke"])

with tab1:
    st.header("Batch Issuance")
    col1, col2 = st.columns(2)
    with col1:
        batch_input = st.text_area("Student List (rAddress, sSeed)", value=st.session_state.students, height=200)
    with col2:
        course = st.text_input("Course Name", value="Applied Cryptography")
        expiry = st.date_input("Certificate Expiry Date", value=date(2027, 12, 31))
        taxon = st.number_input("Taxon", value=100)

    if st.button("🔥 Run Automatic Batch", type="primary"):
        if st.session_state.issuer_seed and batch_input:
            students = [{"addr": l.split(',')[0].strip(), "seed": l.split(',')[1].strip()} for l in batch_input.split('\n') if ',' in l]
            with st.spinner("Transacting on XRPL..."):
                # Metadata now includes expiry
                meta = {
                    "n": course, 
                    "exp": str(expiry),
                    "i": "https://raw.githubusercontent.com/fomomodigital/image-host/main/importance_of_certifications.png"
                }
                results = xrpl_manager.issue_bulk_credentials(st.session_state.issuer_seed, students, int(taxon), meta)
                st.dataframe(pd.DataFrame(results), use_container_width=True)
                st.success("Batch Complete!")

with tab2:
    st.header("🎓 Student Portfolio")
    search = st.text_input("Search Wallet Address (r...)").strip()
    if search:
        nfts = xrpl_manager.get_student_portfolio(search)
        if nfts:
            for nft in nfts:
                with st.container(border=True):
                    c_img, c_txt = st.columns([1, 3])
                    c_img.image("https://raw.githubusercontent.com/fomomodigital/image-host/main/importance_of_certifications.png", use_container_width=True)
                    
                    # Logic to check expiry from metadata
                    status_msg = "✅ Active"
                    try:
                        memo = json.loads(binascii.unhexlify(nft.get("URI")).decode())
                        exp_date = date.fromisoformat(memo.get("exp"))
                        if date.today() > exp_date:
                            status_msg = "❌ EXPIRED"
                    except: pass

                    nft_id = nft.get('NFTokenID')
                    c_txt.write(f"**Status:** {status_msg}")
                    c_txt.write(f"**NFTokenID:** `{nft_id}`")
                    c_txt.write(f"**Issuer:** `{nft.get('Issuer')}`")
                    
                    if c_txt.button("📋 Copy to Revoke Tab", key=nft_id):
                        st.session_state.revoke_id = nft_id
                        st.session_state.revoke_owner = search
                        st.success("Copied to Tab 3!")
        else: st.info("No credentials found.")

with tab3:
    st.header("🔍 Verification & Revocation")
    v_id = st.text_input("Enter NFTokenID to Verify", value=st.session_state.get("revoke_id", ""))
    v_owner = st.text_input("Current Owner (Student Address)", value=st.session_state.get("revoke_owner", ""))
    
    if v_id and st.button("Verify Authenticity"):
        st.json(xrpl_manager.verify_credential(v_id))
    
    st.divider()
    if v_id and st.button("Permanently Burn NFT", type="primary"):
        res = xrpl_manager.burn_credential(st.session_state.issuer_seed, v_id, owner_address=v_owner)
        if res.get("meta", {}).get("TransactionResult") == "tesSUCCESS":
            st.success("🔥 Credential successfully revoked!")
        else: st.error(f"Error: {res.get('meta', {}).get('TransactionResult')}")
        st.json(res)