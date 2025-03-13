"""
Gemini AI Provider Module

This module implements the Gemini AI provider for the AI Agent API, integrating
with Google's Generative AI service. It handles chat sessions, content generation,
and message management while maintaining a consistent AI personality.
"""

from typing import Any, override

import google.generativeai as genai
import structlog
from google.generativeai.types import ContentDict

from flare_ai_defai.ai.base import BaseAIProvider, ModelResponse
from flare_ai_defai.ai.rag import RAGProcessor

logger = structlog.get_logger(__name__)


SYSTEM_INSTRUCTION = """
You are Artemis, an AI assistant specialized in helping users navigate
the Flare blockchain ecosystem. As an expert in blockchain data and operations,
you assist users with:

- Account creation and management on the Flare network
- Token swaps and transfers
- Understanding blockchain data structures and smart contracts
- Explaining technical concepts in accessible terms
- Monitoring network status and transaction processing

Your personality combines technical precision with light wit - you're
knowledgeable but approachable, occasionally using clever remarks while staying
focused on providing accurate, actionable guidance. You prefer concise responses
that get straight to the point, but can elaborate when technical concepts
need more explanation.

When helping users:
- Prioritize security best practices
- Verify user understanding of important steps
- Provide clear warnings about risks when relevant
- Format technical information (addresses, hashes, etc.) in easily readable ways

If users request operations you cannot directly perform, clearly explain what
steps they need to take themselves while providing relevant guidance.

You maintain professionalism while allowing your subtle wit to make interactions
more engaging - your goal is to be helpful first, entertaining second.
"""


class GeminiProvider(BaseAIProvider):
    """
    Provider class for Google's Gemini AI service.

    This class implements the BaseAIProvider interface to provide AI capabilities
    through Google's Gemini models. It manages chat sessions, generates content,
    and maintains conversation history.

    Attributes:
        chat (genai.ChatSession | None): Active chat session
        model (genai.GenerativeModel): Configured Gemini model instance
        chat_history (list[ContentDict]): History of chat interactions
        logger (BoundLogger): Structured logger for the provider
        rag_processor (RAGProcessor): Processor for retrieval augmented generation
    """

    def __init__(self, api_key: str, model: str, **kwargs: str) -> None:
        """
        Initialize the Gemini provider with API credentials and model configuration.

        Args:
            api_key (str): Google API key for authentication
            model (str): Gemini model identifier to use
            **kwargs (str): Additional configuration parameters including:
                - system_instruction: Custom system prompt for the AI personality
                - knowledge_base_path: Optional path to knowledge base for RAG
        """
        genai.configure(api_key=api_key)
        self.chat: genai.ChatSession | None = None
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=kwargs.get("system_instruction", SYSTEM_INSTRUCTION),
        )
        self.chat_history: list[ContentDict] = [
            ContentDict(parts=["Hi, I'm Artemis"], role="model")
        ]
        self.logger = logger.bind(service="gemini")
        self.rag_processor = RAGProcessor(kwargs.get("knowledge_base_path"))

    @override
    def reset(self) -> None:
        """
        Reset the provider state.

        Clears chat history and terminates active chat session.
        """
        self.chat_history = []
        self.chat = None
        self.logger.debug(
            "reset_gemini", chat=self.chat, chat_history=self.chat_history
        )

    @override
    def generate(
        self,
        prompt: str,
        response_mime_type: str | None = None,
        response_schema: Any | None = None,
    ) -> ModelResponse:
        """
        Generate content using the Gemini model.

        Args:
            prompt (str): Input prompt for content generation
            response_mime_type (str | None): Expected MIME type for the response
            response_schema (Any | None): Schema defining the response structure

        Returns:
            ModelResponse: Generated content with metadata including:
                - text: Generated text content
                - raw_response: Complete Gemini response object
                - metadata: Additional response information including:
                    - candidate_count: Number of generated candidates
                    - prompt_feedback: Feedback on the input prompt
        """
        generation_config = {}
        if response_mime_type:
            generation_config["response_mime_type"] = response_mime_type
        if response_schema:
            generation_config["response_schema"] = response_schema

        # Create a new chat for this generation
        chat = self.model.start_chat(history=[])
        response = chat.send_message(
            prompt,
            generation_config=(
                genai.GenerationConfig(**generation_config)
                if generation_config
                else None
            ),
        )

        self.logger.debug("generate", prompt=prompt, response_text=response.text)
        return ModelResponse(
            text=response.text,
            raw_response=response,
            metadata={
                "candidate_count": len(response.candidates),
                "prompt_feedback": response.prompt_feedback,
            },
        )

    @override
    def send_message(
        self,
        msg: str,
    ) -> ModelResponse:
        """
        Send a message in a chat session and get the response.

        Initializes a new chat session if none exists, using the current chat history.

        Args:
            msg (str): Message to send to the chat session

        Returns:
            ModelResponse: Response from the chat session including:
                - text: Generated response text
                - raw_response: Complete Gemini response object
                - metadata: Additional response information including:
                    - candidate_count: Number of generated candidates
                    - prompt_feedback: Feedback on the input message
        """
        if not self.chat:
            self.chat = self.model.start_chat(history=self.chat_history)
        response = self.chat.send_message(msg)
        self.logger.debug("send_message", msg=msg, response_text=response.text)
        return ModelResponse(
            text=response.text,
            raw_response=response,
            metadata={
                "candidate_count": len(response.candidates),
                "prompt_feedback": response.prompt_feedback,
            },
        )

    @override
    async def send_message_with_image(
        self, msg: str, image: bytes, mime_type: str
    ) -> ModelResponse:
        """
        Send a message with an image using the Gemini vision model.

        Args:
            msg: Text message to send
            image: Binary image data
            mime_type: MIME type of the image (e.g. image/jpeg)

        Returns:
            ModelResponse containing the generated response
        """
        if not self.chat:
            self.chat = self.model.start_chat(history=self.chat_history)

        # Retrieve relevant documents using RAG
        retrieved_docs = await self.rag_processor.retrieve_relevant_docs(query=msg)

        # Augment the prompt with retrieved context
        augmented_prompt = self.rag_processor.augment_prompt(
            query=msg, retrieved_docs=retrieved_docs
        )

        # Send augmented prompt with image to chat
        response = self.chat.send_message(
            [augmented_prompt, {"mime_type": mime_type, "data": image}]
        )

        self.logger.debug(
            "send_message_with_image",
            msg=msg,
            mime_type=mime_type,
            augmented_prompt=augmented_prompt,
            response_text=response.text,
        )

        return ModelResponse(
            text=response.text,
            raw_response=response,
            metadata={
                "candidate_count": len(response.candidates),
                "prompt_feedback": response.prompt_feedback,
                "retrieved_docs": [
                    {"content": doc.content, "metadata": doc.metadata}
                    for doc in retrieved_docs.documents
                ],
            },
        )
