# n8n Chat Workflow for Streamlit

This workflow matches the Streamlit chat orchestration options added in the UI.

## File to import

- n8n/workflows/rentalai-chat-orchestrator.json

## What the workflow does

1. Receives POST requests from Streamlit at webhook path rentalai-chat.
2. Normalizes payload fields:
   - event
   - source
   - message
   - thread_id
   - tenant_id
3. Validates that message is present.
4. Calls Property API chat endpoint:
   - POST ${API_BASE_URL}/chat
5. Returns JSON response to Streamlit:
   - response
   - thread_id
   - source

## Expected incoming payload from Streamlit

{
  "event": "chat_request",
  "source": "streamlit_ui",
  "message": "Who is overdue this month?",
  "thread_id": "user_default_123",
  "tenant_id": 2
}

## Response contract for Streamlit

{
  "response": "Tenant 3 and Tenant 7 are currently overdue.",
  "thread_id": "user_default_123",
  "source": "n8n"
}

Streamlit should use response as the answer field.
If you change it, also update the sidebar field n8n chat response field in the UI.

## Setup steps

1. Import the workflow JSON into n8n.
2. Set environment variable API_BASE_URL for n8n runtime.
   - local example: http://localhost:8000
   - docker compose example: http://api:8000
3. Activate the workflow.
4. Copy the production webhook URL and paste it in Streamlit sidebar n8n webhook URL.
5. In Streamlit AI assistant tab, set Chat orchestration to:
   - n8n first (fallback API), or
   - n8n only

## Optional extension

You can extend this workflow by adding Telegram send nodes after Format Success Response
if you want n8n to own outbound delivery too.
