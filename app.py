import streamlit as st
import requests
import json
import pandas as pd
import time

# --- Logo ---
st.image("https://a9group.net/a9logo.png", width=96)

# --- App Title and Instructions ---
st.title("🚀 Atlassian Admin & Jira API Playground")

st.info("""
🔑 **Instructions**  
1️⃣ Enter your **API Key** and **Organization ID**.  
2️⃣ Browse all endpoints in the sidebar, edit the URL as needed, and test live!  
3️⃣ View results as JSON or table, and download as CSV!  
4️⃣ The app remembers your responses for dynamic dropdowns (like `directoryId`, `userId`, etc.).  
""")

def paginate(url, headers, params, debug):
    all_results = []
    while url:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            if debug:
                st.error(f"Request failed: {resp.status_code} {resp.text}")
            break
        resp_json = resp.json()
        data = resp_json.get("data", [])
        if isinstance(data, list):
            all_results.extend(data)
        if debug:
            st.write(f"➡️ Pagination URL: {resp.url}")
            st.json(resp_json)
        next_link = resp_json.get("links", {}).get("next")
        if next_link:
            if next_link.startswith("http"):
                url = next_link
                params = None
            else:
                base = url.split("?")[0]
                if next_link.startswith("?"):
                    url = base + next_link
                else:
                    url = f"{base}?cursor={next_link}"
            time.sleep(delay)
        else:
            url = None
    return {"data": all_results}

st.sidebar.header("🔧 API Setup")
api_key = st.sidebar.text_input("API Key (Bearer Token)", type="password")
org_id = st.sidebar.text_input("Organization ID")
paginate_results = st.sidebar.checkbox("📃 Paginate results", value=True)
delay = st.sidebar.number_input(
    "⏳ Delay between requests (seconds)", min_value=0.0, max_value=5.0, value=0.5, step=0.5
)
debug = st.sidebar.checkbox("🐞 Show Debug Output", value=False)

# --- Auto-discover directories and groups for quick reference ---
headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json",
}

if api_key and org_id and "directoryId_dict" not in st.session_state:
    dir_url = f"https://api.atlassian.com/admin/v2/orgs/{org_id}/directories"
    resp = requests.get(dir_url, headers=headers)
    if resp.status_code == 200:
        directories = resp.json().get("data", [])
        mapping = {d.get("directoryId"): d.get("name", d.get("directoryId")) for d in directories}
        if mapping:
            st.session_state["directoryId_dict"] = mapping
            st.session_state.setdefault("param_directoryId", list(mapping.keys())[0])

selected_dir = st.session_state.get("param_directoryId")
if api_key and org_id and selected_dir and "groupId_dict" not in st.session_state:
    grp_url = f"https://api.atlassian.com/admin/v2/orgs/{org_id}/directories/{selected_dir}/groups"
    resp = requests.get(grp_url, headers=headers)
    if resp.status_code == 200:
        groups = resp.json().get("data", [])
        mapping = {g.get("id"): g.get("name", g.get("id")) for g in groups}
        if mapping:
            st.session_state["groupId_dict"] = mapping

st.markdown("## 📑 Known Variables")
st.write(f"**Organization ID:** {org_id}")

dir_dict = st.session_state.get("directoryId_dict")
if dir_dict:
    st.write("**Directories**")
    st.dataframe(pd.DataFrame(list(dir_dict.items()), columns=["ID", "Name"]))

grp_dict = st.session_state.get("groupId_dict")
if grp_dict:
    st.write(f"**Groups for Directory {selected_dir}**")
    st.dataframe(pd.DataFrame(list(grp_dict.items()), columns=["ID", "Name"]))

@st.cache_data
def load_openapi_specs():
    urls = [
        "https://dac-static.atlassian.com/cloud/admin/organization/swagger.v3.json",
        "https://dac-static.atlassian.com/cloud/jira/platform/swagger-v3.v3.json",
    ]
    specs = []
    for url in urls:
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                specs.append(resp.json())
        except Exception as e:
            st.warning(f"Failed to load {url}: {e}")
    return specs

specs = load_openapi_specs()

tags = {}
for spec in specs:
    server_url = spec.get("servers", [{}])[0].get("url", "https://api.atlassian.com")
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            for tag in details.get("tags", []):
                if tag not in tags:
                    tags[tag] = []
                tags[tag].append({
                    "path": path,
                    "method": method.upper(),
                    "details": details,
                    "server_url": server_url,
                })

tag = st.sidebar.selectbox("📂 Select API Tag", list(tags.keys()))
endpoints = tags[tag]
endpoint_options = [f"{ep['method']} {ep['path']}" for ep in endpoints]
selected_endpoint = st.sidebar.selectbox("🔗 Select Endpoint", endpoint_options)
selected = next(ep for ep in endpoints if f"{ep['method']} {ep['path']}" == selected_endpoint)

st.subheader(f"🔗 {selected_endpoint}")
st.write(selected["details"].get("summary", "No summary available."))

# --- Path & query parameters ---
path_params = {}
query_params = {}

if "parameters" in selected["details"]:
    for param in selected["details"]["parameters"]:
        pname = param.get("name", "unnamed_param")
        pdesc = param.get("description", "")
        ptype = param.get("in", "")
        # Use known dict if available
        known_dict = st.session_state.get(f"{pname}_dict", {})
        param_key = f"param_{pname}"
        if ptype == "path":
            if known_dict:
                value = st.selectbox(
                    f"🔧 Path param: {pname} ({pdesc})",
                    list(known_dict.keys()),
                    format_func=lambda k: known_dict[k],
                    key=param_key,
                )
            else:
                value = st.text_input(
                    f"🔧 Path param: {pname} ({pdesc})",
                    st.session_state.get(param_key, ""),
                    key=param_key,
                )
            path_params[pname] = value
            st.session_state[param_key] = value
        elif ptype == "query":
            value = st.text_input(f"🔎 Query param: {pname} ({pdesc})", "")
            if value:
                query_params[pname] = value

# --- Request body if applicable ---
request_body = None
if "requestBody" in selected["details"]:
    st.subheader("📝 Request Body (JSON)")
    body_input = st.text_area("Edit the request body here:", "{}")
    try:
        request_body = json.loads(body_input)
    except json.JSONDecodeError:
        st.warning("⚠️ Invalid JSON. Using empty object.")
        request_body = {}

# --- Build default URL ---
default_url = selected.get("server_url", "https://api.atlassian.com") + selected["path"]
if "{orgId}" in default_url and org_id:
    default_url = default_url.replace("{orgId}", org_id)

st.subheader("🔗 Dynamic URL Editor (Honoring Spec Base URL)")
editable_url = st.text_input("Edit the final request URL", value=default_url)

# --- Send request helper ---
def send_request(method, url, api_key, body=None, params=None):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if method == "GET":
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if paginate_results and resp.status_code == 200:
            data = paginate(url, headers, params, debug)
        return resp, data
    else:
        resp = requests.request(method, url, headers=headers, json=body, params=params)
        return resp, resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else None

if st.button("🚀 Send Request"):
    method = selected["method"]
    for param, value in path_params.items():
        editable_url = editable_url.replace(f"{{{param}}}", value)
    
    st.write(f"🔗 **Final URL:** {editable_url}")
    
    resp, json_data = send_request(method, editable_url, api_key, body=request_body, params=query_params)
    st.write(f"Status Code: {resp.status_code}")

    try:
        st.subheader("📦 JSON Response")
        st.json(json_data)
        
        # --- Build known dictionaries for path parameters ---
        known_keys = ["directoryId", "userId", "groupId", "accountId"]
        if isinstance(json_data, dict) and "data" in json_data and isinstance(json_data["data"], list):
            for key in known_keys:
                mapping = {str(item[key]): item.get("name", item.get("displayName", item[key])) for item in json_data["data"] if key in item}
                if mapping:
                    st.session_state[f"{key}_dict"] = mapping
                    param_key = f"param_{key}"
                    if key == "directoryId" and param_key not in st.session_state:
                        st.session_state[param_key] = list(mapping.keys())[0]

        # --- Try to build tabular data ---
        df = None
        if isinstance(json_data, list):
            df = pd.DataFrame(json_data)
        elif isinstance(json_data, dict) and "data" in json_data and isinstance(json_data["data"], list):
            df = pd.DataFrame(json_data["data"])
        
        if df is not None and not df.empty:
            st.subheader("📊 Tabular View")
            st.dataframe(df)

            # --- Download CSV ---
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
st.caption("✅ Final release: fully dynamic, builds dictionaries for known path params, and CSV export ready!")

