"""
LLM Service - Handles communication with Claude API
"""
import os
from anthropic import Anthropic


class LLMService:
    """Service for interacting with Claude AI"""
    
    def __init__(self):
        """Initialize Claude client"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        
        # System prompt for restaurant agent
        self.system_prompt = """You are a friendly AI assistant for Luigi's Italian Restaurant.

Your job is to help customers make reservations over the phone.

Guidelines:
- Be warm, friendly, and professional
- Keep responses SHORT (1-2 sentences) - this is a phone call
- Ask for: party size, date, time, and name
- Confirm all details before finalizing
- If asked about menu or hours, politely say you can transfer them to the restaurant

Remember: Keep responses brief and conversational. You're speaking, not writing.
"""
    
    def get_response(self, user_message: str, conversation_history: list = None) -> str:
        """
        Get AI response from Claude
        
        Args:
            user_message: What the user just said
            conversation_history: List of previous messages (optional)
            
        Returns:
            Claude's response as text
        """
        # Build messages list
        messages = conversation_history or []
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,  # Keep responses short for phone calls
                system=self.system_prompt,
                messages=messages
            )
            
            # Extract text from response
            return response.content[0].text
            
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return "I'm sorry, I'm having trouble thinking right now. Could you repeat that?"


# Create a singleton instance
llm_service = LLMService()
