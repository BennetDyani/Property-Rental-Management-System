import streamlit as st
import requests
from pathlib import Path

# --- Configuration ---
API_BASE_URL = "http://localhost:8000"
st.set_page_config(page_title="RentalAI Manager", page_icon="🏠", layout="wide")

# --- Custom Styling ---
st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "user_default_123"

# --- Sidebar: Configuration ---
with st.sidebar:
    st.title("⚙️ Settings")
    st.session_state.thread_id = st.text_input("Session ID (Thread)", value=st.session_state.thread_id)
    tenant_id = st.number_input("Tenant ID (Optional)", value=0, step=1)
    if tenant_id == 0: tenant_id = None

    st.divider()
    st.subheader("Quick Actions")
    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# --- Navigation ---
tabs = st.tabs(["💬 AI Assistant", "📂 Document Portal", "📊 Management Dashboard"])

# --- TAB 1: AI ASSISTANT ---
with tabs[0]:
    st.header("AI Property Assistant")
    st.caption("Ask about leases, payments, or report maintenance issues.")

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("How can I help you today?"):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call Backend API
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    payload = {
                        "message": prompt,
                        "thread_id": st.session_state.thread_id,
                        "tenant_id": tenant_id
                    }
                    response = requests.post(f"{API_BASE_URL}/chat", json=payload)
                    response.raise_for_status()
                    answer = response.json()["response"]
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# --- TAB 2: DOCUMENT PORTAL ---
with tabs[1]:
    st.header("Document Ingestion")
    st.caption("Upload leases, invoices, or inspection photos to the AI memory.")

    col1, col2 = st.columns(2)
    with col1:
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt", "png", "jpg", "jpeg"])
        doc_type = st.selectbox("Document Type",
                                ["lease", "invoice", "maintenance_report", "inspection_photo", "general"])

    with col2:
        prop_id = st.number_input("Property ID (Optional)", value=0, step=1)
        if prop_id == 0: prop_id = None

        if st.button("🚀 Ingest Document", use_container_width=True):
            if uploaded_file:
                with st.spinner("Extracting and indexing..."):
                    try:
                        # Prepare multipart form data for FastAPI
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {
                            "tenant_id": tenant_id or "",
                            "property_id": prop_id or "",
                            "doc_type": doc_type
                        }
                        res = requests.post(f"{API_BASE_URL}/ingest", files=files, data=data)
                        res.raise_for_status()
                        st.success(f"Success! {res.json()['message']}")
                    except Exception as e:
                        st.error(f"Upload failed: {e}")
            else:
                st.warning("Please select a file first.")

# --- TAB 3: MANAGEMENT DASHBOARD ---
with tabs[2]:
    st.header("Landlord Insights")
    st.caption("Trigger high-level reports using the AI agents.")

    col1, col2, col3 = st.columns(3)


    # We use the /chat endpoint to generate these reports via the Agents
    def get_report(query):
        try:
            payload = {"message": query, "thread_id": "admin_report", "tenant_id": None}
            res = requests.post(f"{API_BASE_URL}/chat", json=payload)
            return res.json()["response"]
        except:
            return "Error generating report."


    with col1:
        if st.button("💰 Income Forecast", use_container_width=True):
            with st.spinner("Analyzing..."):
                st.info(get_report("Give me a detailed rental income forecast for the next 3 months."))

    with col2:
        if st.button("🛠 Maintenance Summary", use_container_width=True):
            with st.spinner("Analyzing..."):
                st.info(get_report("What is the current maintenance status? Which requests are urgent?"))

    with col3:
        if st.button("⚠️ Overdue Payments", use_container_width=True):
            with st.spinner("Analyzing..."):
                st.info(get_report("Who is currently overdue on rent and how much is owed?"))