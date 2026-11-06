"""Optional real model execution. Imported only when --mode live is selected."""
import json
import os

from briefing import Report, ROOT


def run_live(packet: dict, contract: str, model: str | None) -> Report:
    if not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('Live mode needs OPENAI_API_KEY. The Inworld narration key is not an OpenAI key.')
    model = model or os.environ.get('OPENAI_MODEL')
    if not model:
        raise ValueError('Set OPENAI_MODEL or pass --model with a model available in your project.')
    try:
        from agents import Agent, Runner, RunConfig
    except ImportError as exc:
        raise ValueError('Install optional live dependencies: python -m pip install -r requirements.txt') from exc
    instructions = (ROOT / 'contracts' / f'{contract}.txt').read_text(encoding='utf-8')
    agent = Agent(
        name='Store manager sales brief',
        instructions=instructions,
        model=model,
        output_type=Report,
        tools=[],  # No publishing, browsing, email, or filesystem tool is exposed.
    )
    result = Runner.run_sync(
        agent,
        input=json.dumps(packet),  # Current task data stay separate from instructions.
        max_turns=1,
        run_config=RunConfig(tracing_disabled=True),
    )
    if not isinstance(result.final_output, Report):
        raise ValueError('The agent did not return a structured Report.')
    return result.final_output

