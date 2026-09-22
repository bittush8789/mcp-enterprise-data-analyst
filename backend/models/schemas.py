"""Pydantic Schemas for MCP Enterprise Data Analyst."""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# --- Chat API Schemas ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="Natural language user query")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation tracking ID")


class SourceItem(BaseModel):
    type: str = Field(..., description="Source type: 'mysql' or 'chroma'")
    name: Optional[str] = Field(default=None, description="Name of table, view, or document")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata such as version, chunk_id, etc.")


class VisualizationConfig(BaseModel):
    type: str = Field(..., description="Chart type: 'bar', 'line', 'pie', or 'kpi'")
    x: Optional[List[Any]] = Field(default=None, description="X-axis category labels")
    y: Optional[List[Any]] = Field(default=None, description="Y-axis metric values")
    title: Optional[str] = Field(default=None, description="Display title for visualization")
    series: Optional[List[Dict[str, Any]]] = Field(default=None, description="Multi-series data if applicable")
    kpi_value: Optional[Union[str, float, int]] = Field(default=None, description="Single headline KPI value")
    kpi_label: Optional[str] = Field(default=None, description="Headline KPI label")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Verified, grounded natural language answer")
    sources: List[SourceItem] = Field(default_factory=list, description="Enterprise data and document sources")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Structured dataset returned by analytics")
    visualization: Optional[VisualizationConfig] = Field(default=None, description="Configured visualization payload")
    guardrail_flags: Optional[List[str]] = Field(default=None, description="Any safety or validation notifications")
    conversation_id: Optional[str] = Field(default=None, description="Conversation session ID")


# --- MCP Tool Schemas ---

class MCPToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPToolResult(BaseModel):
    source: str = Field(..., description="'mysql' or 'chroma'")
    metric: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    results: Optional[List[Dict[str, Any]]] = None
    row_count: Optional[int] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


# --- Standard Evidence Object (Requirement 24) ---

class EvidenceSource(BaseModel):
    type: str = Field(..., description="'mysql' or 'chroma'")
    name: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    documents: Optional[List[Dict[str, Any]]] = None


class EvidenceObject(BaseModel):
    question: str
    intent: str = "GENERAL"
    sources: List[EvidenceSource] = Field(default_factory=list)
    analytics_summary: Optional[Dict[str, Any]] = None
    is_valid: bool = False
    validation_notes: List[str] = Field(default_factory=list)


# --- System Health Schemas ---

class HealthResponse(BaseModel):
    status: str
    components: Dict[str, str]
    timestamp: str
