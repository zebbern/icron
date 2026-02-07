"""Multi-model collaboration service for cross-provider discussions.

This module enables multiple LLM providers to collaborate on a task through
iterative dialogue where models question and build on each other's ideas
until reaching consensus.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from icron.config.schema import Config
from icron.providers.base import LLMProvider
from icron.providers.openai_provider import OpenAIProvider
from icron.providers.anthropic_provider import AnthropicProvider
from icron.providers.gemini_provider import GeminiProvider


# Provider display info with default models for each
PROVIDER_INFO: dict[str, dict[str, str]] = {
    "anthropic": {"name": "Claude", "emoji": "🟣", "model": "claude-sonnet-4-20250514"},
    "openrouter": {"name": "DeepSeek R1", "emoji": "🔀", "model": "deepseek/deepseek-r1-0528:free"},
    "openai": {"name": "GPT", "emoji": "🟢", "model": "gpt-4o"},
    "together": {"name": "Together", "emoji": "🔵", "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"},
    "groq": {"name": "Groq", "emoji": "⚡", "model": "llama-3.3-70b-versatile"},
    "gemini": {"name": "Gemini", "emoji": "💎", "model": "gemini-2.0-flash"},
    "zhipu": {"name": "Zhipu", "emoji": "🇨🇳", "model": "glm-4-flash"},
}

# Provider priority (higher = starts first and synthesizes)
PROVIDER_PRIORITY: dict[str, int] = {
    "anthropic": 100,
    "openrouter": 90,
    "openai": 80,
    "gemini": 70,
    "together": 60,
    "groq": 50,
    "zhipu": 40,
}

# Consensus marker - models should include this when they agree
CONSENSUS_MARKER = "[AGREED]"
MAX_ROUNDS = 5  # Maximum back-and-forth exchanges


@dataclass
class ProviderInstance:
    """A configured provider instance with metadata."""
    name: str
    emoji: str
    provider: LLMProvider
    model: str
    priority: int


@dataclass
class DialogueExchange:
    """A single exchange in the dialogue."""
    speaker: str
    emoji: str
    round: int
    content: str
    has_consensus: bool = False


@dataclass
class CollaborationResult:
    """Result of a multi-model collaboration."""
    task: str
    dialogue: list[DialogueExchange]
    final_synthesis: str
    providers_used: list[str]
    rounds_completed: int
    consensus_reached: bool
    success: bool
    error: str | None = None


class CollaborationService:
    """
    Multi-model collaboration service using iterative dialogue.
    
    Models take turns questioning and building on each other's ideas
    until they reach consensus or max rounds.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self._providers: list[ProviderInstance] | None = None
    
    def get_configured_providers(self) -> list[ProviderInstance]:
        """Get all providers that have valid API keys configured."""
        if self._providers is not None:
            return self._providers
        
        providers: list[ProviderInstance] = []
        
        for provider_name in PROVIDER_INFO:
            provider_config = getattr(self.config.providers, provider_name, None)
            if not provider_config:
                continue
            
            api_key = getattr(provider_config, "api_key", None)
            if not api_key:
                continue
            
            api_base = getattr(provider_config, "api_base", None)
            info = PROVIDER_INFO[provider_name]
            
            # Use user's configured model if available
            user_model = getattr(provider_config, "model", None)
            model = user_model or info["model"]
            
            try:
                if provider_name == "anthropic":
                    llm = AnthropicProvider(
                        api_key=api_key,
                        api_base=api_base,
                        default_model=model,
                    )
                elif provider_name == "gemini":
                    llm = GeminiProvider(
                        api_key=api_key,
                        api_base=api_base,
                        default_model=model,
                    )
                else:
                    base_urls = {
                        "openai": "https://api.openai.com/v1",
                        "openrouter": "https://openrouter.ai/api/v1",
                        "together": "https://api.together.xyz/v1",
                        "groq": "https://api.groq.com/openai/v1",
                        "zhipu": "https://open.bigmodel.cn/api/paas/v4/",
                    }
                    llm = OpenAIProvider(
                        api_key=api_key,
                        api_base=api_base or base_urls.get(provider_name),
                        default_model=model,
                    )
                
                providers.append(ProviderInstance(
                    name=info["name"],
                    emoji=info["emoji"],
                    provider=llm,
                    model=model,
                    priority=PROVIDER_PRIORITY.get(provider_name, 0),
                ))
                logger.debug(f"Collaboration: Found provider {info['name']} with model {model}")
                
            except Exception as e:
                logger.warning(f"Failed to initialize {provider_name}: {e}")
        
        providers.sort(key=lambda p: p.priority, reverse=True)
        self._providers = providers
        return providers
    
    def get_provider_count(self) -> int:
        """Get the number of configured providers."""
        return len(self.get_configured_providers())
    
    async def collaborate(
        self,
        task: str,
        callback: callable = None,
    ) -> CollaborationResult:
        """
        Run a multi-model collaboration using iterative dialogue.
        
        Models take turns:
        1. Model A proposes initial solution
        2. Model B critiques, questions, and adds ideas  
        3. Model A addresses feedback and refines
        4. Model B reviews and adds more thoughts
        5. Continue until consensus ([AGREED]) or max rounds
        6. Final synthesis combining best ideas
        
        Args:
            task: The task/question for the models to discuss.
            callback: Async function for progress updates.
        
        Returns:
            CollaborationResult with full dialogue and synthesis.
        """
        providers = self.get_configured_providers()
        
        if len(providers) < 2:
            return CollaborationResult(
                task=task,
                dialogue=[],
                final_synthesis="",
                providers_used=[p.name for p in providers],
                rounds_completed=0,
                consensus_reached=False,
                success=False,
                error=f"Need at least 2 providers. Found: {len(providers)}",
            )
        
        # Use first two providers (highest priority)
        model_a = providers[0]
        model_b = providers[1]
        
        dialogue: list[DialogueExchange] = []
        consensus_reached = False
        current_round = 1
        
        try:
            # Round 1: Model A proposes initial solution
            opening_prompt = self._build_opening_prompt(task)
            response_a = await self._get_response(model_a, opening_prompt, callback, current_round, "opening")
            dialogue.append(DialogueExchange(
                speaker=model_a.name,
                emoji=model_a.emoji,
                round=current_round,
                content=response_a,
            ))
            
            # Dialogue loop
            while current_round <= MAX_ROUNDS and not consensus_reached:
                # Model B responds to Model A
                prompt_b = self._build_response_prompt(task, dialogue, model_b.name)
                response_b = await self._get_response(model_b, prompt_b, callback, current_round, "response")
                
                has_consensus_b = CONSENSUS_MARKER in response_b
                dialogue.append(DialogueExchange(
                    speaker=model_b.name,
                    emoji=model_b.emoji,
                    round=current_round,
                    content=response_b,
                    has_consensus=has_consensus_b,
                ))
                
                if has_consensus_b:
                    # Check if Model A also agrees
                    prompt_final = self._build_consensus_check_prompt(task, dialogue, model_a.name)
                    response_final = await self._get_response(model_a, prompt_final, callback, current_round, "consensus")
                    
                    has_consensus_a = CONSENSUS_MARKER in response_final
                    dialogue.append(DialogueExchange(
                        speaker=model_a.name,
                        emoji=model_a.emoji,
                        round=current_round,
                        content=response_final,
                        has_consensus=has_consensus_a,
                    ))
                    
                    if has_consensus_a:
                        consensus_reached = True
                        break
                
                current_round += 1
                
                if current_round <= MAX_ROUNDS and not consensus_reached:
                    # Model A responds to Model B
                    prompt_a = self._build_response_prompt(task, dialogue, model_a.name)
                    response_a = await self._get_response(model_a, prompt_a, callback, current_round, "response")
                    
                    has_consensus_a = CONSENSUS_MARKER in response_a
                    dialogue.append(DialogueExchange(
                        speaker=model_a.name,
                        emoji=model_a.emoji,
                        round=current_round,
                        content=response_a,
                        has_consensus=has_consensus_a,
                    ))
                    
                    if has_consensus_a:
                        # Check if Model B agrees
                        prompt_final = self._build_consensus_check_prompt(task, dialogue, model_b.name)
                        response_final = await self._get_response(model_b, prompt_final, callback, current_round, "consensus")
                        
                        has_consensus_b = CONSENSUS_MARKER in response_final
                        dialogue.append(DialogueExchange(
                            speaker=model_b.name,
                            emoji=model_b.emoji,
                            round=current_round,
                            content=response_final,
                            has_consensus=has_consensus_b,
                        ))
                        
                        if has_consensus_b:
                            consensus_reached = True
                            break
            
            # Final Synthesis
            synthesis = await self._synthesize(task, dialogue, model_a, callback)
            
            return CollaborationResult(
                task=task,
                dialogue=dialogue,
                final_synthesis=synthesis,
                providers_used=[model_a.name, model_b.name],
                rounds_completed=current_round,
                consensus_reached=consensus_reached,
                success=True,
            )
            
        except Exception as e:
            logger.error(f"Collaboration failed: {e}")
            return CollaborationResult(
                task=task,
                dialogue=dialogue,
                final_synthesis="",
                providers_used=[p.name for p in providers[:2]],
                rounds_completed=current_round,
                consensus_reached=False,
                success=False,
                error=str(e),
            )
    
    def _build_opening_prompt(self, task: str) -> str:
        """Build the opening prompt for first model."""
        return f"""You are collaborating with another AI model to find the best solution to a task.
You will have a back-and-forth discussion, building on each other's ideas.

**TASK**: {task}

**YOUR ROLE**: Propose an initial solution. Be thorough but concise.

**DIALOGUE RULES**:
- Be specific and provide reasoning
- The other model will critique and add ideas
- You'll refine based on their feedback
- When you believe the solution is complete and optimal, include [AGREED] in your response
- Keep responses focused (max 400 words)

Now provide your initial proposal:"""

    def _build_response_prompt(self, task: str, dialogue: list[DialogueExchange], responder_name: str) -> str:
        """Build a response prompt that shows the full dialogue history."""
        history = self._format_dialogue_history(dialogue)
        
        return f"""You are collaborating with another AI model to find the best solution to a task.

**TASK**: {task}

**DIALOGUE SO FAR**:
{history}

**YOUR ROLE** ({responder_name}): 
Continue the discussion. You should:
1. **Acknowledge** good points from the previous response
2. **Question** anything unclear or potentially problematic
3. **Add** your own ideas or improvements
4. **Refine** the proposed solution

If you believe the current solution is optimal and complete, include [AGREED] in your response to signal consensus.

Keep your response focused (max 400 words). Be constructive and specific.

Your response:"""

    def _build_consensus_check_prompt(self, task: str, dialogue: list[DialogueExchange], responder_name: str) -> str:
        """Build a prompt to check if the other model agrees."""
        history = self._format_dialogue_history(dialogue)
        
        return f"""You are collaborating with another AI model.

**TASK**: {task}

**DIALOGUE SO FAR**:
{history}

The other model has signaled they're satisfied with the solution ([AGREED]).

**Do you agree the solution is now optimal?**
- If YES: Say [AGREED] and briefly confirm why the solution is good
- If NO: Explain what's still missing or needs refinement

Your response (max 200 words):"""

    def _format_dialogue_history(self, dialogue: list[DialogueExchange]) -> str:
        """Format the dialogue history for prompts."""
        parts = []
        for ex in dialogue:
            marker = " ✓" if ex.has_consensus else ""
            parts.append(f"**{ex.emoji} {ex.speaker} (Round {ex.round}){marker}**:\n{ex.content}")
        return "\n\n---\n\n".join(parts)
    
    async def _get_response(
        self,
        provider: ProviderInstance,
        prompt: str,
        callback: callable,
        round_num: int,
        phase: str,
    ) -> str:
        """Get a response from a provider and send to callback."""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await provider.provider.chat(messages, model=provider.model)
            content = response.content or ""
            
            # Send to callback for display
            if callback:
                has_agreed = CONSENSUS_MARKER in content
                marker = " ✅" if has_agreed else ""
                display = f"{provider.emoji} **{provider.name}** (Round {round_num}){marker}:\n\n{content}"
                await callback(provider.name, f"round_{round_num}_{phase}", display)
            
            return content
            
        except Exception as e:
            logger.error(f"Error from {provider.name}: {e}")
            error_msg = f"[Error: {e}]"
            if callback:
                await callback(provider.name, "error", f"{provider.emoji} **{provider.name}**: {error_msg}")
            return error_msg
    
    async def _synthesize(
        self,
        task: str,
        dialogue: list[DialogueExchange],
        synthesizer: ProviderInstance,
        callback: callable,
    ) -> str:
        """Create final synthesis from the dialogue."""
        history = self._format_dialogue_history(dialogue)
        
        prompt = f"""You participated in a collaborative discussion to solve a task.

**TASK**: {task}

**FULL DIALOGUE**:
{history}

Now create the **FINAL SOLUTION** that:
1. Takes the best ideas from the entire discussion
2. Addresses all concerns that were raised
3. Is actionable and complete
4. Represents the collaborative consensus

Provide a clear, well-structured final answer:"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await synthesizer.provider.chat(messages, model=synthesizer.model)
            content = response.content or ""
            
            if callback:
                await callback(
                    synthesizer.name,
                    "synthesis",
                    f"✨ **Final Synthesis** (by {synthesizer.emoji} {synthesizer.name}):\n\n{content}"
                )
            
            return content
            
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return f"[Synthesis failed: {e}]"
