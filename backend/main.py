"""FastAPI Gateway for MCP Enterprise Data Analyst.

Provides:
- POST /chat : Main conversational enterprise analyst endpoint
- GET /health : Non-leaking diagnostic healthcheck for FastAPI, MySQL, ChromaDB
- GET /sources : Metadata about connected data sources and indexed policy documents
- Static frontend serving for ChatGPT-style UI
- Structured logging & request telemetry
"""

import time
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.config import settings
from backend.models.schemas import ChatRequest, ChatResponse, HealthResponse, SourceItem, VisualizationConfig
from backend.agent import agent
from backend.mysql import mysql_manager
from backend.chroma import chroma_manager

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("enterprise_analyst.api")

app = FastAPI(
    title="MCP Enterprise Data Analyst",
    description="Enterprise AI Data Analyst with Hybrid RAG, MCP Tools, Deterministic Analytics & Guardrails",
    version="1.0.0",
)

# CORS middleware for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("--> Incoming Request [%s] %s %s", request_id, request.method, request.url.path)
    
    response = await call_next(request)
    
    latency_ms = round((time.time() - start_time) * 1000, 2)
    logger.info("<-- Finished Request [%s] Status: %s in %s ms", request_id, response.status_code, latency_ms)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(latency_ms)
    return response


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    """Processes natural language enterprise questions through LangGraph and MCP."""
    start_time = time.time()
    user_msg = payload.message.strip()
    session_id = payload.conversation_id or str(uuid.uuid4())

    try:
        agent_result = agent.process_query(user_msg)

        sources = [
            SourceItem(
                type=s["type"],
                name=s.get("name"),
                metadata=s.get("metadata"),
            )
            for s in agent_result.get("sources", [])
        ]

        vis = None
        if agent_result.get("visualization"):
            vis = VisualizationConfig(**agent_result["visualization"])

        response = ChatResponse(
            answer=agent_result["answer"],
            sources=sources,
            data=agent_result.get("data"),
            visualization=vis,
            guardrail_flags=agent_result.get("guardrail_flags"),
            conversation_id=session_id,
        )

        duration = round((time.time() - start_time) * 1000, 2)
        logger.info("Processed /chat query in %s ms. Intent: %s, Tools: %s", duration, agent_result.get("intent"), agent_result.get("mcp_tools_called"))
        return response

    except Exception as e:
        logger.error("Error processing /chat query: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal analysis error. Please retry.")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check verifying connectivity without leaking credentials."""
    mysql_status = mysql_manager.check_health()
    chroma_status = chroma_manager.check_health()

    components = {
        "fastapi": "healthy",
        "mysql": mysql_status.get("status", "unknown"),
        "chromadb": chroma_status.get("status", "unknown"),
        "llm_engine": "groq (openai/gpt-oss-120b)",
    }

    overall_status = "healthy"
    if any(s == "unhealthy" for s in [components["mysql"], components["chromadb"]]):
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        components=components,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/sources")
async def list_sources():
    """Returns metadata about available enterprise databases and knowledge libraries."""
    return {
        "databases": [
            {
                "name": "enterprise_analytics",
                "engine": "MySQL",
                "tables": ["regions", "customers", "products", "orders", "order_items"],
                "views": ["order_revenue"],
                "description": "5,000+ orders, 550 customers across 5 geographical regions with verified revenue.",
            }
        ],
        "documents": [
            {
                "title": "Global Enterprise Software & Services Refund Policy",
                "version": "v4.2",
                "type": "refund_policy.txt",
                "scope": "30-day evaluation, SLA credit tiers, CFO approval matrix",
            },
            {
                "title": "Commercial Pricing Strategy and Discount Authority Matrix",
                "version": "v5.1",
                "type": "discount_policy.txt",
                "scope": "Enterprise volume tiers, North/West regional incentive programs",
            },
            {
                "title": "Enterprise Software Performance Warranty and SLA Guarantee",
                "version": "v3.8",
                "type": "warranty_policy.txt",
                "scope": "99.99% cloud uptime SLA, 24-hour critical bug hotfix guarantees",
            },
            {
                "title": "Standard Operating Procedure for Enterprise Incident Escalation",
                "version": "v6.0",
                "type": "escalation_sop.txt",
                "scope": "Severity 1-4 incident matrix, TAM & VP Customer Engineering escalation",
            },
        ],
    }


# Mount Frontend Static Files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def serve_index():
    """Serves the ChatGPT-like frontend."""
    return FileResponse("frontend/index.html")
