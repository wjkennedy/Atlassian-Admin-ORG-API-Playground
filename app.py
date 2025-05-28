import streamlit as st
import requests
import json
import pandas as pd

# --- Logo ---
st.image("https://a9group.net/a9logo.png", width=96)

# --- App Title and Instructions ---
st.title("🚀 Atlassian Admin API Playground (Full Dynamic Spec + CSV Export)")

st.info("""
🔑 **Instructions**  
1️⃣ Enter your **API Key** and **Organization ID**.  
2️⃣ Browse all endpoints in the sidebar, edit the URL as needed, and test live!  
3️⃣ View results as JSON or table, and download as CSV!  
""")

st.sidebar.header("🔧 API Setup")
api_key = st.sidebar.text_input("API Key (Bearer Token)", type="password")
org_id = st.sidebar.text_input("Organization ID")

@st.cache_data
def load_openapi_spec():
    url = "https://dac-static.atlassian.com/cloud/admin/organization/swagger.v3.json"
    resp = requests.get(url)
    return resp.json() if resp.status_code == 200 else {}

spec = load_openapi_spec()

# --- Use servers[0].url from the spec to get the base URL
servers = spec.get("servers", [])
base_url = servers[0]["url"] if servers else "https://api.atlassian.com"

paths = spec.get("paths", {})
tags = {}
for path, methods in paths.items():
    for method, details in methods.items():
        for tag in details.get("tags", []):
            if tag not in tags:
                tags[tag] = []
            tags[tag].append({
                "path": path,
                "method": method.upper(),
                "details": details
            })

tag = st.sidebar.selectbox("📂 Select API Tag", list(tags.keys()))
endpoints = tags[tag]
endpoint_options = [f"{ep['method']} {ep['path']}" for ep in endpoints]
selected_endpoint = st.sidebar.selectbox("🔗 Select Endpoint", endpoint_options)
selected = next(ep for ep in endpoints if f"{ep['method']} {ep['path']}" == selected_endpoint)

st.subheader(f"🔗 {selected_endpoint}")
st.write(selected["details"].get("summary", "No summary available."))

path_params = {}
query_params = {}

if "parameters" in selected["details"]:
    for param in selected["details"]["parameters"]:
        pname = param.get("name", "unnamed_param")
        pdesc = param.get("description", "")
        ptype = param.get("in", "")
        if ptype == "path":
            value = st.text_input(f"🔧 Path param: {pname} ({pdesc})", "")
            path_params[pname] = value
        elif ptype == "query":
            value = st.text_input(f"🔎 Query param: {pname} ({pdesc})", "")
            if value:
                query_params[pname] = value

request_body = None
if "requestBody" in selected["details"]:
    st.subheader("📝 Request Body (JSON)")
    body_input = st.text_area("Edit the request body here:", "{}")
    try:
        request_body = json.loads(body_input)
    except json.JSONDecodeError:
        st.warning("⚠️ Invalid JSON. Using empty object.")
        request_body = {}

# --- Build final URL based on spec's server URL
default_url = base_url + selected["path"]
if "{orgId}" in default_url and org_id:
    default_url = default_url.replace("{orgId}", org_id)

st.subheader("🔗 Dynamic URL Editor (Honoring Spec Base URL)")
editable_url = st.text_input("Edit the final request URL", value=default_url)

def send_request(method, url, api_key, body=None, params=None):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if method == "GET":
        resp = requests.get(url, headers=headers, params=params)
    else:
        resp = requests.request(method, url, headers=headers, json=body, params=params)
    return resp

if st.button("🚀 Send Request"):
    method = selected["method"]
    for param, value in path_params.items():
        editable_url = editable_url.replace(f"{{{param}}}", value)
    
    st.write(f"🔗 **Final URL:** {editable_url}")
    
    resp = send_request(method, editable_url, api_key, body=request_body, params=query_params)
    st.write(f"Status Code: {resp.status_code}")
    
    try:
        json_data = resp.json()
        st.subheader("📦 JSON Response")
        st.json(json_data)
        
        # Try to convert to tabular data
        df = None
        if isinstance(json_data, list):
            df = pd.DataFrame(json_data)
        elif isinstance(json_data, dict) and "data" in json_data and isinstance(json_data["data"], list):
            df = pd.DataFrame(json_data["data"])
        
        if df is not None and not df.empty:
            st.subheader("📊 Tabular View")
            st.dataframe(df)

            # Download CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download data as CSV",
                data=csv,
                file_name='api_data.csv',
                mime='text/csv',
            )
        else:
            st.info("ℹ️ No tabular data to display.")
    except Exception as e:
        st.text(resp.text)
        st.error(f"Error parsing JSON: {e}")

st.markdown("---")
st.caption("✅ This playground uses the live /admin/v2 API – dynamic exploration, tabular data view, and CSV export ready!")

