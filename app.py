import streamlit as st
import pandas as pd
import time
from xrpl_utils import XRPLCredentialManager

# Initialize the manager
xrpl_manager = XRPLCredentialManager()
st.set_page_config(page_title="Institutional Registrar", layout="wide")

# Session state
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
        with st.spinner("Creating 2 Students..."):
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
        ipfs = st.text_input("IPFS CID", value="QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco")
        taxon = st.number_input("Taxon", value=100)

    if st.button("🔥 Run Automatic Batch", type="primary"):
        if st.session_state.issuer_seed and batch_input:
            students = []
            for line in batch_input.split('\n'):
                if ',' in line:
                    addr, seed = line.split(',')
                    students.append({"addr": addr.strip(), "seed": seed.strip()})
            
            with st.spinner("Transacting on XRPL..."):
                results = xrpl_manager.issue_bulk_credentials(
                    st.session_state.issuer_seed, students, int(taxon), {"n": course, "i": f"ipfs://{ipfs}"}
                )
                st.dataframe(pd.DataFrame(results), use_container_width=True)
                st.success("Batch Complete!")
        else:
            st.warning("Please setup Issuer and Student data in the sidebar.")

with tab2:
    st.header("🎓 Student Portfolio")
    search = st.text_input("Search Wallet Address (r...)").strip()
    if search:
        nfts = xrpl_manager.get_student_portfolio(search)
        if nfts:
            st.info(f"Found {len(nfts)} NFT(s)")
            for nft in nfts:
                with st.container(border=True):
                    c_img, c_txt = st.columns([1, 3])
                    
                    # Updated to use direct URL to ensure it displays correctly
                    cert_image_url = "https://raw.githubusercontent.com/fomomodigital/image-host/main/importance_of_certifications.png"
                    c_img.image(cert_image_url, use_container_width=True)
                    
                    nft_id = nft.get('NFTokenID')
                    c_txt.write(f"**NFTokenID:** `{nft_id}`")
                    c_txt.write(f"**Issuer:** `{nft.get('Issuer')}`")
                    
                    if c_txt.button("📋 Copy to Revoke Tab", key=nft_id):
                        st.session_state.revoke_id = nft_id
                        st.session_state.revoke_owner = search
                        st.success("Copied to Tab 3!")
        else:
            st.info("No credentials found for this wallet.")

with tab3:
    st.header("🔍 Verification & Revocation")
    v_id = st.text_input("Enter NFTokenID to Verify", value=st.session_state.get("revoke_id", ""))
    v_owner = st.text_input("Current Owner (Student Address)", value=st.session_state.get("revoke_owner", ""))
    
    if v_id and st.button("Verify Authenticity"):
        st.json(xrpl_manager.verify_credential(v_id))
    
    st.divider()
    st.subheader("🔥 Revoke Credential")
    st.warning("Issuer Revocation requires the 'Current Owner' address if the student has accepted the NFT.")
    
    if v_id and st.button("Permanently Burn NFT", type="primary"):
        try:
            # Passing v_owner to fix the tecNO_ENTRY error
            res = xrpl_manager.burn_credential(st.session_state.issuer_seed, v_id, owner_address=v_owner)
            
            # Check for success in the response metadata
            result_code = res.get("meta", {}).get("TransactionResult", "Unknown")
            if result_code == "tesSUCCESS":
                st.success("🔥 Credential successfully revoked from the ledger!")
            else:
                st.error(f"Transaction Result: {result_code}")
            st.json(res)
        except Exception as e:
            st.error(f"Failed: {e}")