"""Phase 4B Tool Schema Registry.

Provides access to official AgentDojo tool schemas for pre-execution structural validation.
Does NOT execute any tools. Extracts parameter names, required properties, and basic JSON Schema types.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolSchemaInfo(BaseModel):
    """Metadata and parameter schema for a registered tool."""
    name: str = Field(description="Unique tool name")
    description: str = Field(default="", description="Human-readable description of tool")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Declared parameter property schemas")
    required: List[str] = Field(default_factory=list, description="List of required parameter names")


class ToolSchemaRegistry:
    """Registry managing tool schemas for pre-execution structural analysis."""

    def __init__(self, benchmark_version: str = "v1", suite_name: str = "workspace"):
        self.benchmark_version = benchmark_version
        self.suite_name = suite_name
        self._registry: Dict[str, ToolSchemaInfo] = {}
        self._loaded: bool = False

    def load_suite_tools(self) -> None:
        """Load official tools from AgentDojo suite."""
        try:
            from agentdojo.task_suite.load_suites import get_suite
            suite = get_suite(self.benchmark_version, self.suite_name)
            for tool in suite.tools:
                schema = tool.parameters.model_json_schema()
                props = schema.get("properties", {})
                req = schema.get("required", [])
                desc = tool.description if hasattr(tool, "description") else getattr(tool, "__doc__", "") or ""
                self._registry[tool.name] = ToolSchemaInfo(
                    name=tool.name,
                    description=desc,
                    properties=props,
                    required=req,
                )
            self._loaded = True
        except Exception as e:
            # If agentdojo suite cannot be loaded, registry remains empty and warns
            self._loaded = False

    def register_tool(self, name: str, properties: Dict[str, Any], required: List[str], description: str = "") -> None:
        """Register or override a tool schema explicitly (useful for isolated unit tests)."""
        self._registry[name] = ToolSchemaInfo(
            name=name,
            description=description,
            properties=properties,
            required=required,
        )

    def is_tool_registered(self, tool_name: str) -> bool:
        """Check if tool exists in registry."""
        if not self._loaded and not self._registry:
            self.load_suite_tools()
        return tool_name in self._registry

    def get_tool_schema(self, tool_name: str) -> Optional[ToolSchemaInfo]:
        """Retrieve schema metadata for tool, returning None if unknown."""
        if not self._loaded and not self._registry:
            self.load_suite_tools()
        return self._registry.get(tool_name)

    def list_tool_names(self) -> List[str]:
        """List all registered tool names."""
        if not self._loaded and not self._registry:
            self.load_suite_tools()
        return sorted(list(self._registry.keys()))


# Global default instance
_default_registry: Optional[ToolSchemaRegistry] = None


def get_default_registry() -> ToolSchemaRegistry:
    """Return the singleton ToolSchemaRegistry instance for AgentDojo workspace."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolSchemaRegistry()
        _default_registry.load_suite_tools()
    return _default_registry
