# Ron the Reminder (HNG Stage 3 AI Agent)

A simple, helpful AI agent built for the **HNG Stage 3 Task** to integrate with **Telex.im**.

"Ron the Reminder" is a from-scratch agent built in **Python** using **FastAPI** that allows users in a Telex.im chat to set reminders. The bot parses natural language time requests, sends an immediate confirmation, and then sends a follow-up message at the scheduled time using the A2A protocol's `pushNotificationConfig`.

---

## 🚀 Tech Stack

* **Framework:** **FastAPI** (for the web server)
* **Scheduling:** **APScheduler** (for the "clock" system)
* **HTTP Client:** **HTTPX** (for sending async push messages back to Telex)
* **Runtime:** **Uvicorn** (as the ASGI server)
* **Language:** **Python 3.10+**

---

## ✨ Features

* **A2A Protocol Compliant:** Understands and replies with the JSON-RPC 2.0 format used by Telex.im.
* **Time Parsing:** A simple regex parser understands commands like:
    * `/remindme "Task" in 10 minutes`
    * `/remindme "Task" at 16:30`
* **Immediate Confirmation:** Instantly replies to the user to confirm the reminder has been set.
* **Scheduled Push Messages:** Uses an internal scheduler (`APScheduler`) to send the reminder at the correct time, using the `pushNotificationConfig.url` provided in the initial request.
* **In-Memory Storage:** Uses a simple in-memory list to store pending reminders (beginner-friendly, no database required).

---

## ⚙️ API Endpoint

The entire agent lives on a single endpoint:

* **Endpoint:** `POST /a2a/ron`
* **Request Format:** `JSON-RPC 2.0` (as defined by the A2A protocol)
* **Action:**
    1.  Parses the `message.parts[0].text`.
    2.  If it's a valid reminder, it stores the reminder, time, `contextId`, and `pushNotificationConfig.url`.
    3.  Returns an immediate `JSONRPCResponse` with a confirmation message.
* **Scheduled Action:**
    1.  An `APScheduler` job runs every minute.
    2.  It checks the in-memory list for due reminders.
    3.  If a reminder is due, it sends a new `POST` request to the stored `pushNotificationConfig.url` with the reminder message.

---

## 📦 How to Run Locally

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/ron-reminder-bot.git](https://github.com/your-username/ron-reminder-bot.git)
    cd ron-reminder-bot
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    
    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```
    The server will be running on `http://localhost:8000`.

---

## 🧪 How to Test Locally

You can test the endpoint using `curl` in a separate terminal. This simulates a request from Telex.im.

### Test 1: Set a Reminder

This command attempts to set a reminder for 1 minute from now.

```bash
curl -X POST 'http://localhost:8000/a2a/ron' \
-H 'Content-Type: application/json' \
-d '{
  "jsonrpc": "2.0",
  "id": "test-123",
  "method": "message/send",
  "params": {
    "contextId": "local-test-chat",
    "message": {
      "role": "user",
      "parts": [
        {
          "kind": "text",
          "text": "/remindme \"Test the bot\" in 1 minute"
        }
      ]
    },
    "configuration": {
      "blocking": true,
      "pushNotificationConfig": {
        "url": "[https://httpbin.org/post](https://httpbin.org/post)"
      }
    }
  }
}'


  * **You will see:** An immediate JSON reply confirming the reminder.
  * **In your bot's terminal:** You will see a log that the reminder was set.
  * **After 1 minute:** You will see a log that the reminder was found and sent (e.g., `Sending reminder to local-test-chat...`).

### Test 2: Send an Invalid Command

```bash
curl -X POST 'http://localhost:8000/a2a/ron' \
-H 'Content-Type: application/json' \
-d '{
  "jsonrpc": "2.0",
  "id": "test-456",
  "method": "message/send",
  "params": {
    "contextId": "local-test-chat",
    "message": { "role": "user", "parts": [{ "kind": "text", "text": "hello" }] },
    "configuration": { "blocking": true, "pushNotificationConfig": { "url": "..." } }
  }
}'
```

  * **You will see:** The JSON reply with the help message (`"Sorry, I didn't quite get that..."`).

-----

## 🚀 Deployment

This app is ready to be deployed to any web service provider that supports Python ASGI, such as **Render** or **Railway**.

  * **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
  * **Dependencies:** `pip install -r requirements.txt`

The live, public endpoint will be `https://your-app-name.onrender.com/a2a/ron`.

-----

## 🔗 Telex.im Integration

To add this agent to your Telex.im workflow, use the following JSON configuration in the agent/workflow editor.

**Important:** Replace the `url` value with your own live, deployed URL (from Render or Railway).

```json
{
  "active": true,
  "category": "utilities",
  "description": "A simple agent that sets reminders in chat.",
  "id": "ron_the_reminder_agent",
  "long_description": "You are Ron the Reminder. Your job is to set reminders. Users will send you messages like /remindme \"task\" in 10 minutes or /remindme \"task\" at 17:30. You will confirm the reminder and send a message back at the specified time.",
  "name": "Ron the Reminder",
  "nodes": [
    {
      "id": "ron_agent_node",
      "name": "Ron the Reminder Agent",
      "parameters": {},
      "position": [
        800,
        -100
      ],
      "type": "a2a/mastra-a2a-node",
      "typeVersion": 1,
      "url": "https://YOUR_DEPLOYED_URL_[HERE.onrender.com/a2a/ron](https://HERE.onrender.com/a2a/ron)"
    }
  ],
  "pinData": {},
  "settings": {
    "executionOrder": "v1"
  },
  "short_description": "A simple, helpful reminder bot."
}
```

```
```
