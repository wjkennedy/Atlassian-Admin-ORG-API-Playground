import streamlit as st
import requests
import json

st.title("Atlassian Org Admin API Playground (Full Dynamic Spec)")

st.info("""
🔑 **Instructions**  
1️⃣ Enter your **API Key** and **Organization ID**.  
2️⃣ Browse all endpoints in the sidebar, edit the URL as needed, and test live!  
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

# --- Corrected base URL to include /admin/v2 ---
base_url = "https://api.atlassian.com/admin/v2"
default_url = base_url + selected["path"]
if "{orgId}" in default_url and org_id:
    default_url = default_url.replace("{orgId}", org_id)

st.subheader("🔗 Dynamic URL Editor")
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
    resp = send_request(method, editable_url, api_key, body=request_body, params=query_params)
    st.write(f"Status Code: {resp.status_code}")
    try:
        st.json(resp.json())
    except:
        st.text(resp.text)

st.markdown("---")
st.caption("✅ Finalized with admin/v2 prefix handling and safe parameter replacements.")

