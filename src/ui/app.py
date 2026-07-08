import os
from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

# --- Configuration ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
DEFAULT_N8N_CHAT_RESPONSE_FIELD = os.getenv("N8N_CHAT_RESPONSE_FIELD", "response")
DEFAULT_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
st.set_page_config(page_title="RentalAI Manager", page_icon="🏡", layout="wide")


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int = 15) -> tuple[bool, str]:
    try:
        response = requests.post(url, json=payload, timeout=timeout_seconds)
        response.raise_for_status()
        return True, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


def send_to_n8n(webhook_url: str, payload: dict[str, Any]) -> tuple[bool, str]:
    if not webhook_url:
        return False, "N8N webhook URL is not set."
    return _post_json(webhook_url, payload)


def get_nested_value(data: dict[str, Any], dotted_path: str) -> Any:
    value: Any = data
    for part in dotted_path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def call_n8n_chat(
    *,
    webhook_url: str,
    payload: dict[str, Any],
    response_field: str,
    timeout_seconds: int = 20,
) -> tuple[bool, str, str]:
    if not webhook_url:
        return False, "N8N webhook URL is not set.", ""

    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout_seconds)
        response.raise_for_status()

        data = response.json() if response.content else {}
        candidate = get_nested_value(data, response_field)
        if candidate is None:
            if isinstance(data, dict):
                for key in ("response", "answer", "message", "text"):
                    if key in data and data[key] is not None:
                        candidate = data[key]
                        break

        answer = str(candidate).strip() if candidate is not None else ""
        if not answer:
            return False, "n8n response did not include a usable answer field.", ""

        return True, f"HTTP {response.status_code}", answer
    except Exception as exc:
        return False, str(exc), ""


def call_api_chat(api_base_url: str, payload: dict[str, Any], timeout_seconds: int = 20) -> tuple[bool, str, str]:
    try:
        response = requests.post(f"{api_base_url}/chat", json=payload, timeout=timeout_seconds)
        response.raise_for_status()
        answer = response.json().get("response", "")
        if not answer:
            return False, "API response did not include 'response'.", ""
        return True, f"HTTP {response.status_code}", answer
    except Exception as exc:
        return False, str(exc), ""


def send_to_telegram(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Telegram bot token or chat id is missing."

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    return _post_json(telegram_url, payload)


def notify_automation_channels(
    *,
    use_n8n: bool,
    n8n_webhook_url: str,
    use_telegram: bool,
    telegram_bot_token: str,
    telegram_chat_id: str,
    n8n_payload: dict[str, Any],
    telegram_text: str,
) -> list[str]:
    status_messages: list[str] = []

    if use_n8n:
        ok, detail = send_to_n8n(n8n_webhook_url, n8n_payload)
        prefix = "n8n" if ok else "n8n failed"
        status_messages.append(f"{prefix}: {detail}")

    if use_telegram:
        ok, detail = send_to_telegram(telegram_bot_token, telegram_chat_id, telegram_text)
        prefix = "Telegram" if ok else "Telegram failed"
        status_messages.append(f"{prefix}: {detail}")

    return status_messages

# --- Custom Styling ---
st.markdown("""
    <style>
    :root {
        --brand-primary: #2f6ea6;
        --brand-primary-soft: #e8f2fb;
        --brand-accent: #2d9d8f;
        --surface-bg: #f6fbf9;
        --surface-card: #ffffff;
        --text-main: #1f2a37;
        --text-muted: #5b6777;
        --border-soft: #d7e6eb;
        --alert-soft: #fff5dd;
    }

    .stApp {
        background:
            radial-gradient(circle at 8% 8%, #edf8ff 0, rgba(237,248,255,0) 32%),
            radial-gradient(circle at 92% 6%, #eafbf4 0, rgba(234,251,244,0) 28%),
            var(--surface-bg);
        color: var(--text-main);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f1f9ff 0%, #eef7f4 100%);
        border-right: 1px solid var(--border-soft);
    }

    .hero-card {
        background: linear-gradient(135deg, #ffffff 0%, #eef8ff 100%);
        border: 1px solid var(--border-soft);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin: 0.3rem 0 1rem 0;
    }

    .hero-title {
        margin: 0;
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--text-main);
    }

    .hero-subtitle {
        margin: 0.3rem 0 0 0;
        color: var(--text-muted);
        font-size: 0.95rem;
    }

    .section-card {
        background: var(--surface-card);
        border: 1px solid var(--border-soft);
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        margin-bottom: 0.6rem;
    }

    .section-note {
        background: var(--alert-soft);
        border: 1px solid #f3dfac;
        color: #5e4a1e;
        border-radius: 10px;
        padding: 0.55rem 0.7rem;
        font-size: 0.88rem;
        margin-bottom: 0.8rem;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 0.85rem;
        border-radius: 10px;
    }

    .stTabs [aria-selected="true"] {
        background: var(--brand-primary-soft);
    }

    .stChatMessage {
        border-radius: 14px;
        border: 1px solid var(--border-soft);
    }

    .stButton > button {
        border-radius: 10px;
        border: 1px solid #b7d0df;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--brand-primary) 0%, #255a88 100%);
        border: none;
    }

    .stButton > button:hover {
        border-color: #8ab2cb;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "user_default_123"

st.markdown(
    """
    <div class="hero-card">
        <p class="hero-title">RentalAI Manager</p>
        <p class="hero-subtitle">Friendly tools for tenant support, document processing, and property insights.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Sidebar: Configuration ---
with st.sidebar:
    st.title("Settings")
    st.caption("Configure the current session")
    st.session_state.thread_id = st.text_input("Session ID (Thread)", value=st.session_state.thread_id)
    tenant_id = st.number_input("Tenant ID (Optional)", value=0, step=1)
    if tenant_id == 0: tenant_id = None

    st.subheader("Automation routing")
    use_n8n = st.checkbox("Send events to n8n", value=bool(DEFAULT_N8N_WEBHOOK_URL))
    n8n_webhook_url = st.text_input("n8n webhook URL", value=DEFAULT_N8N_WEBHOOK_URL)
    n8n_chat_response_field = st.text_input(
        "n8n chat response field",
        value=DEFAULT_N8N_CHAT_RESPONSE_FIELD,
        help="Use dot notation for nested fields, for example: data.answer",
    )

    use_telegram = st.checkbox(
        "Send notifications to Telegram",
        value=bool(DEFAULT_TELEGRAM_BOT_TOKEN and DEFAULT_TELEGRAM_CHAT_ID)
    )
    telegram_bot_token = st.text_input(
        "Telegram bot token",
        value=DEFAULT_TELEGRAM_BOT_TOKEN,
        type="password"
    )
    telegram_chat_id = st.text_input("Telegram chat id", value=DEFAULT_TELEGRAM_CHAT_ID)

    st.subheader("Quick actions")
    if st.button("Clear chat history", type="secondary", width="stretch"):
        st.session_state.messages = []
        st.rerun()

# --- Navigation ---
tabs = st.tabs(["AI assistant", "Document portal", "Management dashboard", "Automation hub"])

# --- TAB 1: AI ASSISTANT ---
with tabs[0]:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.header("AI property assistant")
    st.caption("Ask about leases, payments, or report maintenance issues.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    chat_delivery_mode = st.segmented_control(
        "Delivery mode",
        options=["UI only", "UI + n8n", "UI + Telegram", "UI + n8n + Telegram"],
        default="UI only",
    )

    chat_orchestration_mode = st.segmented_control(
        "Chat orchestration",
        options=["API direct", "n8n first (fallback API)", "n8n only"],
        default="API direct",
    )

    if chat_orchestration_mode != "API direct":
        st.caption("n8n should return JSON with a response field (default: response).")

    send_chat_to_n8n = chat_delivery_mode in {"UI + n8n", "UI + n8n + Telegram"}
    send_chat_to_telegram = chat_delivery_mode in {"UI + Telegram", "UI + n8n + Telegram"}

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
                    answer = ""
                    route_status = ""
                    n8n_failed = False

                    if chat_orchestration_mode in {"n8n first (fallback API)", "n8n only"}:
                        n8n_payload = {
                            "event": "chat_request",
                            "source": "streamlit_ui",
                            "message": prompt,
                            "thread_id": st.session_state.thread_id,
                            "tenant_id": tenant_id,
                        }
                        ok, detail, n8n_answer = call_n8n_chat(
                            webhook_url=n8n_webhook_url,
                            payload=n8n_payload,
                            response_field=n8n_chat_response_field,
                        )
                        if ok:
                            answer = n8n_answer
                            route_status = f"Answer source: n8n ({detail})"
                        else:
                            n8n_failed = True
                            route_status = f"n8n chat failed: {detail}"

                    if not answer and chat_orchestration_mode != "n8n only":
                        ok, detail, api_answer = call_api_chat(API_BASE_URL, payload)
                        if ok:
                            answer = api_answer
                            if n8n_failed:
                                route_status = f"Answer source: API fallback ({detail})"
                            else:
                                route_status = f"Answer source: API ({detail})"
                        else:
                            raise RuntimeError(f"API chat failed: {detail}")

                    if not answer:
                        raise RuntimeError(route_status or "Could not produce an answer.")

                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    if route_status:
                        st.caption(route_status)

                    now = datetime.now(timezone.utc).isoformat()
                    n8n_payload = {
                        "event": "chat_response",
                        "timestamp": now,
                        "thread_id": st.session_state.thread_id,
                        "tenant_id": tenant_id,
                        "question": prompt,
                        "answer": answer,
                    }
                    telegram_text = (
                        "RentalAI update\n"
                        f"Thread: {st.session_state.thread_id}\n"
                        f"Question: {prompt}\n\n"
                        f"Answer: {answer}"
                    )
                    statuses = notify_automation_channels(
                        use_n8n=use_n8n and send_chat_to_n8n,
                        n8n_webhook_url=n8n_webhook_url,
                        use_telegram=use_telegram and send_chat_to_telegram,
                        telegram_bot_token=telegram_bot_token,
                        telegram_chat_id=telegram_chat_id,
                        n8n_payload=n8n_payload,
                        telegram_text=telegram_text,
                    )
                    for status in statuses:
                        st.caption(status)
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# --- TAB 2: DOCUMENT PORTAL ---
with tabs[1]:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.header("Document ingestion")
    st.caption("Upload leases, invoices, or inspection photos to the AI memory.")
    st.markdown("<div class='section-note'>Tip: Upload clear PDF/DOCX files for best extraction quality.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt", "png", "jpg", "jpeg"])
        doc_type = st.selectbox("Document Type",
                                ["lease", "invoice", "maintenance_report", "inspection_photo", "general"])

    with col2:
        prop_id = st.number_input("Property ID (Optional)", value=0, step=1)
        if prop_id == 0: prop_id = None

        notify_ingestion_n8n = st.checkbox("Notify n8n on upload", value=use_n8n)
        notify_ingestion_telegram = st.checkbox("Notify Telegram on upload", value=False)

        if st.button("Ingest document", type="primary", width="stretch"):
            if uploaded_file:
                with st.spinner("Extracting and indexing..."):
                    try:
                        # Prepare multipart form data for FastAPI
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {"doc_type": doc_type}
                        if tenant_id is not None:
                            data["tenant_id"] = str(tenant_id)
                        if prop_id is not None:
                            data["property_id"] = str(prop_id)
                        res = requests.post(f"{API_BASE_URL}/ingest", files=files, data=data)
                        res.raise_for_status()
                        result_json = res.json()
                        st.success(f"Success! {result_json['message']}")

                        now = datetime.now(timezone.utc).isoformat()
                        n8n_payload = {
                            "event": "document_ingested",
                            "timestamp": now,
                            "thread_id": st.session_state.thread_id,
                            "tenant_id": tenant_id,
                            "property_id": prop_id,
                            "doc_type": doc_type,
                            "filename": uploaded_file.name,
                            "ingest_result": result_json,
                        }
                        telegram_text = (
                            "RentalAI ingestion\n"
                            f"File: {uploaded_file.name}\n"
                            f"Type: {doc_type}\n"
                            f"Tenant: {tenant_id if tenant_id is not None else 'N/A'}\n"
                            f"Property: {prop_id if prop_id is not None else 'N/A'}\n"
                            f"Status: {result_json['status']}"
                        )

                        statuses = notify_automation_channels(
                            use_n8n=notify_ingestion_n8n,
                            n8n_webhook_url=n8n_webhook_url,
                            use_telegram=notify_ingestion_telegram,
                            telegram_bot_token=telegram_bot_token,
                            telegram_chat_id=telegram_chat_id,
                            n8n_payload=n8n_payload,
                            telegram_text=telegram_text,
                        )
                        for status in statuses:
                            st.caption(status)
                    except Exception as e:
                        st.error(f"Upload failed: {e}")
            else:
                st.warning("Please select a file first.")

# --- TAB 3: MANAGEMENT DASHBOARD ---
with tabs[2]:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.header("Landlord insights")
    st.caption("Trigger high-level reports using the AI agents.")
    st.markdown("</div>", unsafe_allow_html=True)

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
        if st.button("Income forecast", type="primary", width="stretch"):
            with st.spinner("Analyzing..."):
                st.info(get_report("Give me a detailed rental income forecast for the next 3 months."))

    with col2:
        if st.button("Maintenance summary", type="primary", width="stretch"):
            with st.spinner("Analyzing..."):
                st.info(get_report("What is the current maintenance status? Which requests are urgent?"))

    with col3:
        if st.button("Overdue payments", type="primary", width="stretch"):
            with st.spinner("Analyzing..."):
                st.info(get_report("Who is currently overdue on rent and how much is owed?"))


# --- TAB 4: AUTOMATION HUB ---
with tabs[3]:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.header("Telegram + n8n integration")
    st.caption("Validate your automation channels before using them in production.")
    st.markdown("</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("n8n webhook")
        if st.button("Send test event to n8n", type="primary", width="stretch"):
            test_payload = {
                "event": "streamlit_test",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "thread_id": st.session_state.thread_id,
                "tenant_id": tenant_id,
                "message": "Test event from RentalAI Manager UI",
            }
            ok, detail = send_to_n8n(n8n_webhook_url, test_payload)
            if ok:
                st.success(f"n8n webhook test succeeded: {detail}")
            else:
                st.error(f"n8n webhook test failed: {detail}")

        if st.button("Test n8n chat response", type="secondary", width="stretch"):
            test_chat_payload = {
                "event": "chat_request",
                "source": "streamlit_ui_test",
                "message": "Please respond with a short health-check answer.",
                "thread_id": st.session_state.thread_id,
                "tenant_id": tenant_id,
            }
            ok, detail, answer = call_n8n_chat(
                webhook_url=n8n_webhook_url,
                payload=test_chat_payload,
                response_field=n8n_chat_response_field,
            )
            if ok:
                st.success(f"n8n chat test succeeded: {detail}")
                st.info(f"n8n reply: {answer}")
            else:
                st.error(f"n8n chat test failed: {detail}")

    with c2:
        st.subheader("Telegram bot")
        if st.button("Send test message to Telegram", type="primary", width="stretch"):
            test_message = (
                "RentalAI Telegram test\n"
                f"Thread: {st.session_state.thread_id}\n"
                "Status: Integration is reachable"
            )
            ok, detail = send_to_telegram(telegram_bot_token, telegram_chat_id, test_message)
            if ok:
                st.success(f"Telegram test succeeded: {detail}")
            else:
                st.error(f"Telegram test failed: {detail}")