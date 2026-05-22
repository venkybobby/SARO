"""CF-04: AIMS Document Lifecycle tab."""
from __future__ import annotations

import requests
import streamlit as st


def render(token: str) -> None:
    api_base = st.session_state.get("api_base", "http://localhost:8000")
    st.header("📋 AIMS Document Lifecycle")
    st.caption("ISO 42001 evidence — create and link audit documents.")

    with st.expander("Create new AIMS document", expanded=False):
        with st.form("aims_create_form"):
            title = st.text_input("Document title *", placeholder="Data Processing Policy v1")
            version = st.text_input("Version *", placeholder="1.0.0")
            owner_email = st.text_input("Owner email *", placeholder="compliance@acme.com")
            eff_date = st.date_input("Effective date (optional)", value=None)
            submitted = st.form_submit_button("Create Document", type="primary")

        if submitted:
            if not title or not version or not owner_email:
                st.warning("Title, version, and owner email are required.")
            else:
                payload = {"title": title, "version": version, "owner_email": owner_email}
                if eff_date:
                    payload["effective_date"] = eff_date.isoformat()
                try:
                    resp = requests.post(
                        f"{api_base}/api/v1/aims/documents",
                        json=payload,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=20,
                    )
                    if resp.status_code == 201:
                        st.success(f"Document created: {resp.json().get('title')}")
                        st.rerun()
                    else:
                        st.error(f"Failed ({resp.status_code}): {resp.json().get('detail', resp.text)}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.subheader("Your AIMS documents")
    try:
        resp = requests.get(
            f"{api_base}/api/v1/aims/documents",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 200:
            docs = resp.json()
            if not docs:
                st.info("No documents yet. Create one above.")
            else:
                for doc in docs:
                    with st.expander(f"{doc['title']} v{doc['version']}"):
                        st.write(f"**Owner:** {doc.get('owner_email', 'N/A')}")
                        st.write(f"**ID:** `{doc['id']}`")
                        linked = doc.get("linked_audit_ids", [])
                        st.write(f"**Linked audits:** {len(linked)}")
                        if st.button("Download evidence pack", key=f"aims_pack_{doc['id']}"):
                            try:
                                pack_resp = requests.get(
                                    f"{api_base}/api/v1/aims/documents/{doc['id']}/evidence-pack",
                                    headers={"Authorization": f"Bearer {token}"},
                                    timeout=20,
                                )
                                if pack_resp.status_code == 200:
                                    st.json(pack_resp.json())
                                else:
                                    st.error(f"Error: {pack_resp.text}")
                            except Exception as e:
                                st.error(str(e))
        else:
            st.warning(f"Could not load documents ({resp.status_code})")
    except Exception as e:
        st.error(f"Error loading documents: {e}")
