"""
LLM Service - Handles communication with Claude API
Now includes tool/function calling for restaurant operations
"""
import os
import json
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()


class LLMService:
    """Service for interacting with Claude AI with tool support"""

    def __init__(self):
        """Initialize Claude client"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

        # System prompt for restaurant agent with tool usage
        self.system_prompt = """You are a friendly AI assistant for Luigi's Italian Restaurant.

Your job is to help customers make, check, and cancel reservations over the phone.

CRITICAL: When users say "today", "tomorrow", "this week", etc., you MUST:
1. FIRST call get_current_date tool to know what today's date is
2. THEN calculate the actual date they mean
3. Use the YYYY-MM-DD format when calling other tools

Example:
- User: "I need a table for tomorrow at 7pm"
- You: Call get_current_date() → today is 2026-01-03
- You: tomorrow = 2026-01-04
- You: Call check_availability(party_size=X, date="2026-01-04", time="19:00")

Guidelines:
- Be warm, friendly, and professional
- Keep responses SHORT (1-2 sentences max) - this is a phone call
- Use tools to check availability BEFORE confirming reservations
- If a time is unavailable, suggest the alternative times provided by the tool
- Always confirm all details before creating a reservation
- For cancellations, find the reservation and cancel it

Tools you have:
- get_current_date: Get today's actual date (USE THIS FIRST for relative dates!)
- check_availability: Check if a time slot is available
- create_reservation: Create a confirmed reservation
- get_reservations: Look up existing reservations
- cancel_reservation: Cancel a reservation

Important: 
- ALWAYS call get_current_date when user says relative dates like "today", "tomorrow", "next week"
- ALWAYS check availability before creating a reservation
- Keep responses conversational and brief
- Dates should be in YYYY-MM-DD format when using tools
- Times should be in 24-hour HH:MM format when using tools (convert from 12-hour if needed)

Remember: You're speaking on a phone call, not writing an email. Be concise!
"""

    def get_response_with_tools(
            self,
            user_message: str,
            conversation_history: list = None,
            tools: list = None
    ) -> dict:
        """
        Get AI response from Claude with tool support

        Args:
            user_message: What the user just said
            conversation_history: List of previous messages
            tools: List of tool definitions (function calling schema)

        Returns:
            Dict with response text and any tool calls
        """
        # Build messages list
        messages = conversation_history or []
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # Call Claude API with tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=messages,
                tools=tools or []
            )

            # Extract response
            result = {
                "stop_reason": response.stop_reason,
                "content": []
            }

            # Process content blocks
            for block in response.content:
                if block.type == "text":
                    result["content"].append({
                        "type": "text",
                        "text": block.text
                    })
                elif block.type == "tool_use":
                    result["content"].append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            return result

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return {
                "stop_reason": "error",
                "content": [{
                    "type": "text",
                    "text": "I'm sorry, I'm having trouble right now. Could you repeat that?"
                }]
            }


# Create a singleton instance
llm_service = LLMService()
