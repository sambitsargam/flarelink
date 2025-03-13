"""
OpenAI Provider Module

This module implements the OpenAI provider for the AI Agent API, integrating
with OpenAI's API service. It handles chat sessions, content generation,
and message management while maintaining a consistent AI personality.
"""

from typing import Any, override

import structlog
import openai
from openai import OpenAI

from flare_ai_social.ai.base import BaseAIProvider, ModelResponse, Message

logger = structlog.get_logger(__name__)


class OpenAIProvider(BaseAIProvider):
    """
    Provider class for OpenAI's API service.

    This class implements the BaseAIProvider interface to provide AI capabilities
    through OpenAI models. It manages chat sessions, generates content,
    and maintains conversation history.

    Attributes:
        client (OpenAI): OpenAI client instance
        model_name (str): Name of the OpenAI model to use
        system_instruction (str | None): System instruction for the AI
        chat_history (list[dict]): History of chat interactions
        logger (BoundLogger): Structured logger for the provider
    """

    def __init__(
        self, api_key: str, model_name: str, system_instruction: str | None = None
    ) -> None:
        """
        Initialize the OpenAI provider with API credentials and model configuration.

        Args:
            api_key (str): OpenAI API key for authentication
            model_name (str): OpenAI model identifier to use (e.g., "gpt-4", "gpt-3.5-turbo")
            system_instruction (str | None): Custom system prompt for the AI personality
        """
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name
        self.system_instruction = system_instruction
        self.chat_history: list[dict[str, str]] = []
        
        # Initialize with system message if provided
        if system_instruction:
            self.chat_history.append({"role": "system", "content": system_instruction})
            
        self.logger = logger.bind(service="openai")
        self.logger.info(
            "model setup", model_name="gemini-2.0-pro", system_instruction=system_instruction
        )

    @override
    def reset(self) -> None:
        """
        Reset the provider state.

        Clears chat history, maintaining only the system instruction if present.
        """
        self.chat_history = []
        if self.system_instruction:
            self.chat_history.append({"role": "system", "content": self.system_instruction})
        self.logger.debug("reset_openai", chat_history=self.chat_history)

    @override
    def generate_content(
        self,
        prompt: str,
        response_mime_type: str | None = None,
        response_schema: Any | None = None,
    ) -> ModelResponse:
        """
        Generate content using the OpenAI model without maintaining conversation context.

        Args:
            prompt (str): Input prompt for content generation
            response_mime_type (str | None): Expected MIME type for the response
            response_schema (Any | None): Schema defining the response structure

        Returns:
            ModelResponse: Generated content with metadata including:
                - text: Generated text content
                - raw_response: Complete OpenAI response object
                - metadata: Additional response information
        """
        messages = []
        if self.system_instruction:
            messages.append({"role": "system", "content": self.system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        # Configure response format if needed
        response_format = None
        if response_mime_type == "application/json" or (response_schema is not None):
            response_format = {"type": "json_object"}
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format=response_format,
        )
        
        # Extract the response text
        response_text = response.choices[0].message.content or ""
        
        return ModelResponse(
            text=response_text,
            raw_response=response,
            metadata={
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "finish_reason": response.choices[0].finish_reason,
            },
        )

    @override
    def send_message(self, msg: str) -> ModelResponse:
        """
        Send a message in a chat session and get the response.

        Maintains conversation history for context.

        Args:
            msg (str): Message to send to the chat session

        Returns:
            ModelResponse: Response from the chat session including:
                - text: Generated response text
                - raw_response: Complete OpenAI response object
                - metadata: Additional response information
        """
        # Add user message to history
        self.chat_history.append({"role": "user", "content": msg})
        
        # Send the complete conversation history
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.chat_history,
        )
        
        # Extract the response text
        response_text = response.choices[0].message.content or ""
        
        # Add assistant response to history
        self.chat_history.append({"role": "assistant", "content": response_text})
        
        self.logger.debug("send_message", msg=msg, response_text=response_text)
        
        return ModelResponse(
            text=response_text,
            raw_response=response,
            metadata={
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "finish_reason": response.choices[0].finish_reason,
            },
        )
