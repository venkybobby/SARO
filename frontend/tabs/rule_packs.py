"""CF-02: Rule Packs viewer tab."""
from __future__ import annotations

import streamlit as st


def render(token: str) -> None:
    st.header("📦 Rule Packs")
    st.caption("Versioned compliance rule packs powering Gate 4 — CF-02.")

    api_base = st.session_state.get("api_base", "http://localhost:8000")

    import requests
    try:
        resp = requests.get(
            f"{api_base}/api/v1/rule-packs",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            packs = resp.json()
            for pack in packs:
                with st.expander(f"{pack.get('name')} @ {pack.get('version')}"):
                    rules = pack.get("rules", [])
                    st.write(f"**Rules:** {len(rules)}")
                    for rule in rules:
                        st.markdown(
                            f"- **{rule.get('rule_id')}** — {rule.get('title')} "
                            f"*(triggers on: {rule.get('domain_trigger')})*"
                        )
        elif resp.status_code == 404:
            st.info("Rule packs endpoint not yet registered. Available locally via the engine.")
        else:
            st.warning(f"Could not load rule packs ({resp.status_code})")
    except Exception:
        # Graceful fallback: show local pack info from file system
        from pathlib import Path
        import sys
        ROOT = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(ROOT))
        try:
            from rule_packs.loader import load_all_packs
            packs = load_all_packs(ROOT / "rule_packs")
            st.success(f"Loaded {len(packs)} rule packs from local filesystem.")
            for pack in packs:
                with st.expander(f"{pack.name} @ {pack.version}"):
                    st.write(f"**Rules:** {len(pack.rules)}")
                    for rule in pack.rules:
                        st.markdown(
                            f"- **{rule.rule_id}** — {rule.title} "
                            f"*(triggers on: {rule.domain_trigger})*"
                        )
        except Exception as e:
            st.error(f"Could not load rule packs: {e}")
