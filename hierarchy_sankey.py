
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import ausankey as ask
import requests
import time
import json
import os

st.set_page_config(page_title="A9 Hierarchy Crawler", layout="wide")
st.image("https://a9group.net/a9logo.png", width=200)

st.title("🔍 A9 Hierarchy Crawler & Sankey View")

st.markdown("""
**Setup:**  
- This app requires an Atlassian API Token and your Organization ID (provided in `.streamlit/secrets.toml` or entered in the sidebar).  
- It creates a snapshot file `hierarchy_data.json` to save crawl progress.  
- You can delete this file to start fresh:  
```bash
rm hierarchy_data.json
```
""")

st.markdown("""
**Problem Statement:** Audit failures carry steep penalties—fines, lost contracts, reputational damage—and recurring failures without documented Root Cause Analysis (RCA) and Remediation Plans erode stakeholder trust.

**Reality Check:** Most organizations treat audits as episodic checkboxes, not a continuous, automated control loop. This reactive posture leads to mounting technical debt and compliance drift.

**A9’s Edge:** We act as your risk mitigation partner—embedding continuous audit readiness into your Atlassian workflows. Think of us as cost-effective insurance and daily discipline, not a one-off expense.

---
""")

def extract_guid(urn_id: str) -> str:
    if urn_id and ":" in urn_id:
        return urn_id.split(":")[-1]
    return urn_id

def save_hierarchy_to_json(data, filename="hierarchy_data.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

if "api" in st.secrets:
    api_key = st.secrets["api"]["api_key"]
    org_id = st.secrets["api"]["org_id"]
else:
    st.sidebar.warning("⚠️ Secrets file not found. Please enter API token and Org ID.")
    api_key = st.sidebar.text_input("🔑 API Token (Bearer)", type="password")
    org_id = st.sidebar.text_input("🏢 Organization ID")

delay = st.number_input("⏳ Delay between requests (seconds)", min_value=0.5, max_value=5.0, value=1.0, step=0.5)
debug = st.checkbox("🐞 Show Debug Output", value=False)


def paginate(url, headers, debug):
    results = []
    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            if debug:
                st.error(f"Request failed: {resp.status_code} {resp.text}")
            break
        resp_json = resp.json()
        data = resp_json.get("data", [])
        results.extend(data)
        if debug:
            st.write(f"➡️ Pagination URL: {resp.url}")
            st.json(resp_json)
        next_link = resp_json.get("links", {}).get("next")
        if next_link:
            if next_link.startswith("http"):
                url = next_link
            else:
                base = url.split("?")[0]
                if next_link.startswith("?"):
                    url = base + next_link
                else:
                    url = f"{base}?cursor={next_link}"
            time.sleep(delay)
        else:
            url = None
    return results

if st.button("🚀 Start Crawl"):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    base_url = "https://api.atlassian.com/admin/v2/orgs"

    hierarchy_data = []
    roles_mapping = []

    if os.path.exists("hierarchy_data.json"):
        with open("hierarchy_data.json", "r") as f:
            hierarchy_data = json.load(f)
        st.info("Loaded existing hierarchy snapshot (continuing from last state).")


    dir_url = f"{base_url}/{org_id}/directories"
    directories = paginate(dir_url, headers, debug)

    if not directories:
        st.warning("No directories found or unable to fetch directories.")
    else:
        for d in directories:
            dir_id = extract_guid(d.get("directoryId"))
            dir_name = d.get("name", "Unknown Directory")
            if not dir_id:
                continue

            grp_url = f"{base_url}/{org_id}/directories/{dir_id}/groups"
            groups = paginate(grp_url, headers, debug)

            usr_url = f"{base_url}/{org_id}/directories/{dir_id}/users"
            users = paginate(usr_url, headers, debug)
            user_map = {extract_guid(u.get("accountId")): u for u in users}

            for g in groups:
                grp_id = extract_guid(g.get("id"))
                grp_name = g.get("name", "Unknown Group")
                if not grp_id:
                    continue

                role_url = f"{base_url}/{org_id}/directories/{dir_id}/groups/{grp_id}/role-assignments"
                roles = paginate(role_url, headers, debug)
                role_names = [r.get("roleKey", "unknown-role") for r in roles if r]

                grp_users_url = f"{base_url}/{org_id}/directories/{dir_id}/groups/{grp_id}/users"
                group_users = paginate(grp_users_url, headers, debug)

                for u in group_users:
                    user_id = extract_guid(u.get("accountId"))
                    if not user_id:
                        continue

                    u_full = user_map.get(user_id, u)

                    user_email = u_full.get("email") or user_id
                    user_name = (
                        user_email or
                        u_full.get("name") or
                        u_full.get("nickname") or
                        user_id
                    )
                    platform_roles = ", ".join(u_full.get("platformRoles", []))

                    entry = {
                        "directoryId": dir_id,
                        "directoryName": dir_name,
                        "groupId": grp_id,
                        "groupName": grp_name,
                        "userId": user_id,
                        "userName": user_name,
                        "userEmail": user_email,
                        "notes": ", ".join(role_names),
                        "platformRoles": platform_roles
                    }
                    hierarchy_data.append(entry)
                    save_hierarchy_to_json(hierarchy_data)

                    # Group roles
                    for r in role_names:
                        roles_mapping.append({
                            "userId": user_id,
                            "userName": user_name,
                            "userEmail": user_email,
                            "groupId": grp_id,
                            "groupName": grp_name,
                            "roleKey": r
                        })
                    
                    # Platform (org-level) roles
                    for p_role in u_full.get("platformRoles", []):
                        roles_mapping.append({
                            "userId": user_id,
                            "userName": user_name,
                            "userEmail": user_email,
                            "groupId": "ORG-LEVEL",
                            "groupName": "Organization-wide",
                            "roleKey": p_role
                        })

    df = pd.DataFrame(hierarchy_data)
    roles_df = pd.DataFrame(roles_mapping)

    if df.empty:
        st.warning("No hierarchy data retrieved!")
    else:
        st.write("✅ **Hierarchy Data**")
        st.dataframe(df)

        st.download_button("💾 Download CSV", data=df.to_csv(index=False), file_name="hierarchy_data.csv", mime="text/csv")
        st.download_button("💾 Download JSON", data=json.dumps(hierarchy_data, indent=2), file_name="hierarchy_data.json", mime="application/json")


        st.write("### 🗂️ User-Role Mapping Table")
        st.dataframe(roles_df)
        st.download_button("💾 Download Roles Mapping CSV", data=roles_df.to_csv(index=False), file_name="roles_mapping.csv", mime="text/csv")


        st.write("### 🔗 Sankey Diagram: **Directory ➜ Group ➜ User (Email)**")
        sankey_df = pd.DataFrame([
            (row["directoryName"], 1, row["groupName"], 1, row["userEmail"], 1)
            for _, row in df.iterrows()
        ], columns=["Source", "Source_Weight", "Intermediate", "Intermediate_Weight", "Target", "Target_Weight"])
        fig1, ax1 = plt.subplots(figsize=(14, 10))
        ask.sankey(
            sankey_df,
            fontsize=8,
            titles=["Directory", "Group", "User (Email)"],
            label_values=True,
            label_loc=["left", "center", "right"]
        )
        plt.title("Directory ➜ Group ➜ User (Email) Map", fontsize=12)
        st.pyplot(fig1)

        if not roles_df.empty:
            st.write("### 🔗 Sankey Diagram: **Directory ➜ Group ➜ User (Email) ➜ Role**")
            sankey_roles_df = pd.DataFrame([
                (df.loc[df["userId"] == row["userId"], "directoryName"].values[0], 1,
                 df.loc[df["userId"] == row["userId"], "groupName"].values[0], 1,
                 row["userEmail"], 1, row["roleKey"], 1)
                for _, row in roles_df.iterrows()
            ], columns=["Source", "Source_Weight", "Intermediate", "Intermediate_Weight", "Target", "Target_Weight", "Role", "Role_Weight"])

            fig2, ax2 = plt.subplots(figsize=(16, 10))
            ask.sankey(
                sankey_roles_df,
                fontsize=8,
                titles=["Directory", "Group", "User (Email)", "Role"],
                label_values=True,
                label_loc=["left", "left", "center", "right"]
            )
            plt.title("Directory ➜ Group ➜ User (Email) ➜ Role Map", fontsize=12)
            st.pyplot(fig2)
        else:
            st.warning("No role data found for Sankey diagram!")
