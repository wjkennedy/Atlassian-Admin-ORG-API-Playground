
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
debug = st.checkbox("🐞 Show Debug Output", value=True)

if st.button("🚀 Start Crawl"):
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.atlassian.com/admin/v2/orgs"

    hierarchy_data = []
    roles_mapping = []

    if os.path.exists("hierarchy_data.json"):
        with open("hierarchy_data.json", "r") as f:
            hierarchy_data = json.load(f)
        st.info("Loaded existing hierarchy snapshot (continuing from last state).")

    dir_url = f"{base_url}/{org_id}/directories"
    dirs_resp = requests.get(dir_url, headers=headers).json()
    directories = dirs_resp.get("data", [])

    if debug:
        st.write("📦 Directories fetched:")
        st.json(dirs_resp)

    if not directories:
        st.warning("No directories found or unable to fetch directories.")
    else:
        for d in directories:
            dir_id = extract_guid(d.get("directoryId"))
            dir_name = d.get("name", "Unknown Directory")
            if not dir_id:
                continue

            if debug:
                st.write(f"➡️ Crawling directory: {dir_name} ({dir_id})")

            grp_url = f"{base_url}/{org_id}/directories/{dir_id}/groups"
            grp_resp = requests.get(grp_url, headers=headers).json()
            groups = grp_resp.get("data", [])
            time.sleep(delay)

            if debug:
                st.write("📦 Groups fetched:")
                st.json(grp_resp)

            usr_url = f"{base_url}/{org_id}/directories/{dir_id}/users"
            usr_resp = requests.get(usr_url, headers=headers).json()
            users = usr_resp.get("data", [])
            time.sleep(delay)

            if debug:
                st.write("👥 Users fetched:")
                st.json(usr_resp)

            for g in groups:
                grp_id = extract_guid(g.get("id"))
                grp_name = g.get("name", "Unknown Group")
                if not grp_id:
                    continue

                if debug:
                    st.write(f"➡️ Crawling group: {grp_name} ({grp_id})")

                role_url = f"{base_url}/{org_id}/directories/{dir_id}/groups/{grp_id}/role-assignments"
                role_resp = requests.get(role_url, headers=headers).json()
                roles = role_resp.get("data", [])
                time.sleep(delay)

                if debug:
                    st.write("🔑 Role assignments fetched:")
                    st.json(role_resp)

                role_names = [r.get("roleKey", "unknown-role") for r in roles if r]

                for u in users:
                    user_id = extract_guid(u.get("accountId"))
                    if not user_id:
                        continue

                    user_email = u.get("email") or user_id
                    user_name = (
                        user_email or
                        u.get("name") or
                        u.get("nickname") or
                        user_id
                    )
                    platform_roles = ", ".join(u.get("platformRoles", []))

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

                    for r in role_names:
                        roles_mapping.append({
                            "userId": user_id,
                            "userName": user_name,
                            "userEmail": user_email,
                            "groupId": grp_id,
                            "groupName": grp_name,
                            "roleKey": r
                        })

                    for p_role in u.get("platformRoles", []):
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

    if debug:
        st.write("✅ Final hierarchy data:")
        st.dataframe(df)
        st.write("✅ Final roles mapping:")
        st.dataframe(roles_df)

    if df.empty:
        st.warning("No hierarchy data retrieved!")
    else:
        st.write("✅ Hierarchy Data")
        st.dataframe(df)

        st.write("### User-Role Mapping Table")
        st.dataframe(roles_df)

        st.write("### Sankey Diagram: Directory ➜ Group ➜ User (Email)")
        sankey_df = pd.DataFrame([
            (row["directoryName"], 1, row["groupName"], 1, row["userEmail"], 1)
            for _, row in df.iterrows()
        ], columns=["Source", "Source_Weight", "Intermediate", "Intermediate_Weight", "Target", "Target_Weight"])
        fig1, ax1 = plt.subplots(figsize=(14, 10))
        ask.sankey(sankey_df, fontsize=8, titles=["Directory", "Group", "User (Email)"], label_values=True, label_loc=["left", "center", "right"])
        st.pyplot(fig1)

        if not roles_df.empty:
            st.write("### Sankey Diagram: Directory ➜ Group ➜ User (Email) ➜ Role")
            sankey_roles_df = pd.DataFrame([
                (df.loc[df["userId"] == row["userId"], "directoryName"].values[0], 1,
                 df.loc[df["userId"] == row["userId"], "groupName"].values[0], 1,
                 row["userEmail"], 1, row["roleKey"], 1)
                for _, row in roles_df.iterrows()
            ], columns=["Source", "Source_Weight", "Intermediate", "Intermediate_Weight", "Target", "Target_Weight", "Role", "Role_Weight"])
            fig2, ax2 = plt.subplots(figsize=(16, 10))
            ask.sankey(sankey_roles_df, fontsize=8, titles=["Directory", "Group", "User (Email)", "Role"], label_values=True, label_loc=["left", "left", "center", "right"])
            st.pyplot(fig2)
        else:
            st.warning("No role data found for Sankey diagram!")
