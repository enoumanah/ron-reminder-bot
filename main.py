import uvicorn
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from contextlib import asynccontextmanager
import httpx
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import re # We'll use this for parsing time
import uuid # NEW: To create unique IDs for our push messages

# --- (A) A2A PROTOCOL MODELS (INBOUND) ---
# These models handle the request *from* Telex *to* our bot.

class MessagePart(BaseModel):
    kind: Literal["text", "data", "file"]
    text: Optional[str] = None

class A2AMessage(BaseModel):
    role: Literal["user", "agent", "system"]
    parts: List[MessagePart]
    messageId: str = Field(default_factory=str) # Simplified

class PushNotificationConfig(BaseModel):
    url: str # This is the CRUCIAL URL we use to send a message back
    token: Optional[str] = None

class MessageConfiguration(BaseModel):
    blocking: bool = True
    pushNotificationConfig: Optional[PushNotificationConfig] = None

class MessageParams(BaseModel):
    message: A2AMessage
    contextId: str # This identifies the chat
    configuration: MessageConfiguration = Field(default_factory=MessageConfiguration)

class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str
    method: Literal["message/send", "execute"]
    params: MessageParams

# This is the "Result" the bot sends back *immediately*
class TaskResult(BaseModel):
    contextId: str
    status: Literal["completed", "working", "failed"] = "completed"
    message: A2AMessage # The bot's reply message

# This is the final response wrapper
class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: TaskResult

# --- (B) A2A PROTOCOL MODELS (OUTBOUND PUSH) ---
# NEW: These models are for *our bot* to send a message *to* Telex.
# This is what we use when a reminder is due.

class OutboundMessageParams(BaseModel):
    contextId: str
    message: A2AMessage

class OutboundJSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    method: Literal["message/push"] = "message/push"
    params: OutboundMessageParams

# --- (C) SCHEDULER & APP SETUP ---

async_http_client: Optional[httpx.AsyncClient] = None
scheduler = AsyncIOScheduler()

# NEW: Updated reminders list structure to store more info
# (reminder_time, message_text, notification_url, context_id)
reminders: List[tuple[datetime, str, str, str]] = []

# NEW: A simple helper function to parse time strings
def parse_reminder_text(text: str) -> Optional[tuple[str, datetime]]:
    """
    Parses a reminder string.
    Returns (reminder_message, reminder_time) or None.
    """
    # Simple regex for: /remindme "message" in X minutes/hours/at HH:MM
    
    # Match: "message" in X minutes
    match = re.search(r'/remindme\s+"(.*?)"\s+in\s+(\d+)\s+minutes?', text, re.IGNORECASE)
    if match:
        message = match.group(1)
        minutes = int(match.group(2))
        reminder_time = datetime.now() + timedelta(minutes=minutes)
        return (message, reminder_time)

    # Match: "message" at HH:MM
    match = re.search(r'/remindme\s+"(.*?)"\s+at\s+(\d{1,2}):(\d{2})', text, re.IGNORECASE)
    if match:
        message = match.group(1)
        hour = int(match.group(2))
        minute = int(match.group(3))
        now = datetime.now()
        reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If the time is already past for today, set it for tomorrow
        if reminder_time < now:
            reminder_time += timedelta(days=1)
        return (message, reminder_time)
        
    return None

# NEW: This is the function our "clock" will call.
async def check_reminders():
    """
    This function runs every minute.
    It checks the `reminders` list for any due reminders.
    """
    global reminders
    now = datetime.now()
    
    # Find reminders that are due
    due_reminders = [r for r in reminders if r[0] <= now]
    
    # Keep only the reminders that are not due
    reminders = [r for r in reminders if r[0] > now]
    
    if due_reminders:
        print(f"Found {len(due_reminders)} due reminders. Sending...")
        # Create a list of tasks to send all due reminders concurrently
        tasks = []
        for reminder_time, message, url, context_id in due_reminders:
            tasks.append(send_reminder_message(url, context_id, message))
        
        # Send them all!
        await asyncio.gather(*tasks)

# NEW: This function sends the actual reminder message back to Telex.
async def send_reminder_message(push_url: str, context_id: str, message_text: str):
    """
    Sends a "message/push" request to the telex.im push notification URL.
    """
    global async_http_client
    if not async_http_client:
        print("Error: HTTP client not initialized.")
        return

    print(f"Sending reminder to {context_id}: {message_text}")
    
    try:
        # 1. Create the reminder message payload
        reminder_message_part = MessagePart(kind="text", text=f"🔔 REMINDER: {message_text}")
        reminder_a2a_message = A2AMessage(role="agent", parts=[reminder_message_part])
        
        # 2. Create the push request parameters
        outbound_params = OutboundMessageParams(
            contextId=context_id,
            message=reminder_a2a_message
        )
        
        # 3. Create the final JSON-RPC push request
        outbound_request = OutboundJSONRPCRequest(params=outbound_params)
        
        # 4. Send the request
        response = await async_http_client.post(
            push_url,
            json=outbound_request.model_dump(mode='json'), # Use model_dump for Pydantic v2
            timeout=10.0
        )
        
        # Check if Telex accepted our push
        if 200 <= response.status_code < 300:
            print(f"Successfully sent reminder to {context_id}")
        else:
            print(f"Error sending reminder to {context_id}: {response.status_code} {response.text}")
            
    except Exception as e:
        print(f"Exception while sending reminder: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This code runs on startup
    global async_http_client
    async_http_client = httpx.AsyncClient()
    print("FastAPI is starting up...")
    
    # Start the clock!
    # NEW: Add our `check_reminders` function to the scheduler
    scheduler.add_job(check_reminders, 'interval', minutes=1, id="check_reminders_job")
    scheduler.start()
    print("Scheduler started. Ron is watching the clock (checking every 1 min).")
    
    yield
    
    # This code runs on shutdown
    print("FastAPI is shutting down...")
    await async_http_client.aclose()
    scheduler.shutdown()
    print("Scheduler shut down.")

app = FastAPI(
    title="Ron the Reminder Bot",
    description="A simple A2A agent for setting reminders.",
    lifespan=lifespan
)

# --- (D) API ENDPOINTS ---

@app.get("/health")
async def health_check():
    """A simple health check to see if the server is running."""
    return {"status": "healthy", "agent": "Ron the Reminder"}

@app.post("/a2a/ron")
async def a2a_endpoint(request: JSONRPCRequest):
    """
    This is the main (and only) endpoint that telex.im will call.
    It handles all communication.
    """
    
    # 1. Get the user's message
    user_message_text = ""
    for part in request.params.message.parts:
        if part.kind == "text":
            user_message_text = part.text.strip()
            break
    
    # 2. NEW: Try to parse the message
    parsed_data = parse_reminder_text(user_message_text)
    
    if parsed_data:
        # --- Success: We understood the reminder ---
        message_text, reminder_time = parsed_data
        
        # Get the all-important URL and contextId
        push_url = request.params.configuration.pushNotificationConfig.url
        context_id = request.params.contextId
        
        if not push_url:
            # We can't send a reminder if we don't know where to send it!
            print("Error: No pushNotificationConfig.url provided.")
            reply_text = "Sorry, I can't set a reminder. The chat configuration is missing my callback URL."
        
        else:
            # NEW: Add to our in-memory list
            reminders.append((reminder_time, message_text, push_url, context_id))
            print(f"Reminder set for {context_id} at {reminder_time}. Total reminders: {len(reminders)}")
            
            # Send a nice confirmation message
            time_str = reminder_time.strftime("%-I:%M %p on %b %d") # e.g., "4:30 PM on Oct 31"
            reply_text = f"✅ Got it! I'll remind you to \"{message_text}\" at {time_str}."
        
    else:
        # --- Fail: We didn't understand ---
        reply_text = (
            "Sorry, I didn't quite get that. Please use a format like:\n"
            "• `/remindme \"Task\" in 10 minutes`\n"
            "• `/remindme \"Task\" at 16:30`"
        )

    # 3. Build the immediate response
    reply_message = A2AMessage(
        role="agent",
        parts=[MessagePart(kind="text", text=reply_text)]
    )
    
    task_result = TaskResult(
        contextId=request.params.contextId,
        message=reply_message
    )
    
    return JSONRPCResponse(id=request.id, result=task_result)


if __name__ == "__main__":
    print("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)