from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from phistyle_platform.registry.registry import list_registered_apps
from phistyle_platform.runtime.runtime import list_agents, run_agent
from phistyle_platform.runtime.types import UnknownAgentError
from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.router import resolve_llm_test_route
from services.llm_router.types import LLMRequest, ModelRole


app = FastAPI(title="PhiStyle OS API")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRunRequest(BaseModel):
    agent_id: str
    input: dict[str, Any]


class LLMTestRequest(BaseModel):
    role: str
    prompt: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/apps")
def apps() -> list[dict[str, str]]:
    return list_registered_apps()


@app.get("/agents")
def agents() -> list[dict[str, str]]:
    return list_agents()


@app.post("/agents/run")
def run_agent_endpoint(request: AgentRunRequest) -> dict[str, Any]:
    try:
        result = run_agent(request.agent_id, request.input)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "agent_id": result.agent_id,
        "status": result.status,
        "output": result.output,
    }


@app.post("/llm/test")
def llm_test_endpoint(request: LLMTestRequest) -> dict[str, Any]:
    try:
        role, provider_id = resolve_llm_test_route(request.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if provider_id == "fable":
        return {
            "provider_id": "fable",
            "model": "fable-5",
            "dry_run": True,
            "content": f"[dry-run:fable] {request.prompt}",
            "metadata": {
                "role": role.value,
                "reason": "Fable is scaffolded but not enabled for real calls in Phase 6C",
            },
        }
    if provider_id != "deepseek":
        raise HTTPException(status_code=400, detail=f"Unsupported provider route: {provider_id}")
    response = DeepSeekProvider().chat(LLMRequest(role=role, prompt=request.prompt))
    return {
        "provider_id": response.provider_id,
        "model": response.model,
        "dry_run": response.dry_run,
        "content": response.content,
        "metadata": response.metadata,
    }
