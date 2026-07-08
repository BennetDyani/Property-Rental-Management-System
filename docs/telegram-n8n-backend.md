# Telegram -> n8n -> backend setup

This is the recommended production chat path if you want to remove Streamlit from the user messaging loop.

## Architecture

1. Telegram sends updates to n8n.
2. n8n extracts the chat message and sender metadata.
3. n8n calls the backend `/chat` endpoint.
4. n8n sends the backend response back to Telegram.

## Import file

- n8n/workflows/rentalai-telegram-bridge.json

## What the workflow expects

Environment variables in n8n:

- API_BASE_URL
- TELEGRAM_BOT_TOKEN

Examples:

- Local backend: http://localhost:8000
- Docker backend: http://api:8000

## Import steps

1. Import `n8n/workflows/rentalai-telegram-bridge.json` into n8n.
2. Save the workflow.
3. Set the two environment variables in n8n.
4. Activate the workflow.
5. Copy the production webhook URL from the `Telegram Webhook` node.

## Connect Telegram to n8n

Use your bot token and call Telegram `setWebhook` with the n8n production webhook URL.

Example:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-n8n-host/webhook/telegram-rentalai
```

If the call succeeds, Telegram will start delivering bot messages directly to n8n.

## Backend payload sent by n8n

The workflow currently sends:

```json
{
  "message": "My sink is leaking",
  "thread_id": "telegram_123456789",
  "tenant_id": null
}
```

`thread_id` is derived from the Telegram chat id, so conversation memory stays consistent per chat.

## Telegram reply path

The workflow posts the backend response to:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendMessage
```

with:

```json
{
  "chat_id": 123456789,
  "text": "Your backend answer"
}
```

## Tenant mapping note

This workflow does not assume Telegram users already map to internal tenant ids.

Recommended first rollout:

1. Run with `tenant_id: null`.
2. Let the assistant answer general questions.
3. Add tenant mapping later in n8n or the backend only when you have a stable identity rule.

Good mapping strategies later:

1. n8n lookup table keyed by Telegram chat id or username.
2. Backend table that stores external channel identities and maps them to tenant ids.
3. A verification flow where the user provides unit number, email, or phone before sensitive actions.

## Smoke test

1. Activate the workflow.
2. Register the Telegram webhook.
3. Send a message to the bot in Telegram.
4. Confirm the n8n execution calls `/chat` and `sendMessage`.

## When to add backend changes

Add backend identity mapping only if you need tenant-specific authenticated actions from Telegram, such as:

- payment lookups for a specific person
- maintenance logging tied to one tenant
- document access scoped to a tenant

Until then, the direct Telegram -> n8n -> backend flow is enough.
