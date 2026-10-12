"""Phase 4B Structural Feature Extractor.

Extracts deterministic structural and schema-conformance features from proposed tool calls
using the official ToolSchemaRegistry.

Guarantees:
- Validates proposed calls strictly before execution without running any tool.
- Never inspects runtime execution results or errors.
- Handles unknown tools, missing schemas, and malformed inputs with explicit, documented indicators.
"""

from typing import Any, Dict, List, Optional
from agentwatch.features.registry import ToolSchemaRegistry, get_default_registry


def check_single_type(val: Any, type_str: str) -> bool:
    """Check if runtime value satisfies a JSON Schema primitive type."""
    if val is None:
        return type_str == "null"
    if type_str == "string":
        return isinstance(val, str)
    if type_str == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if type_str == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    if type_str == "boolean":
        return isinstance(val, bool)
    if type_str == "array":
        return isinstance(val, list)
    if type_str == "object":
        return isinstance(val, dict)
    if type_str == "null":
        return val is None
    return True


def check_type_compatibility(val: Any, prop_schema: Dict[str, Any]) -> bool:
    """Check if runtime value satisfies a parameter's JSON Schema specification."""
    if not isinstance(prop_schema, dict):
        return True

    # Handle anyOf unions (e.g. Union[T, None])
    if "anyOf" in prop_schema and isinstance(prop_schema["anyOf"], list):
        return any(check_type_compatibility(val, branch) for branch in prop_schema["anyOf"])

    # Handle declared type
    declared_type = prop_schema.get("type")
    if declared_type is None:
        # If no type constraint specified, accept value
        return True

    if isinstance(declared_type, list):
        return any(check_single_type(val, t) for t in declared_type)
    elif isinstance(declared_type, str):
        return check_single_type(val, declared_type)

    return True


def extract_structural_features(
    proposed_tool_name: str,
    proposed_arguments: Dict[str, Any],
    call_id: Optional[str] = None,
    registry: Optional[ToolSchemaRegistry] = None,
) -> Dict[str, Any]:
    """Extract 14 structural and schema conformance features for a proposed tool call."""
    reg = registry or get_default_registry()

    # 1. Tool existence and schema resolution
    is_tool_known = reg.is_tool_registered(proposed_tool_name)
    schema_info = reg.get_tool_schema(proposed_tool_name) if is_tool_known else None
    is_schema_avail = schema_info is not None

    # 2. Call ID validation
    is_call_id_valid = bool(call_id and str(call_id).strip())

    # 3. Provided arguments count
    args_dict = proposed_arguments if isinstance(proposed_arguments, dict) else {}
    provided_arg_count = len(args_dict)

    if not is_schema_avail or schema_info is None:
        # Schema unavailable: report explicit missing/unknown status
        return {
            "is_tool_name_known": is_tool_known,
            "is_schema_available": False,
            "is_call_id_valid": is_call_id_valid,
            "provided_argument_count": provided_arg_count,
            "declared_property_count": -1,
            "required_argument_count": -1,
            "missing_required_argument_count": 0,
            "has_missing_required_arguments": False,
            "unexpected_argument_key_count": 0,
            "has_unexpected_argument_keys": False,
            "type_mismatch_count": 0,
            "has_type_mismatches": False,
            "schema_conformant_argument_count": 0,
            "is_completely_schema_conformant": False,
        }

    # Schema is available: evaluate conformance
    declared_props = schema_info.properties
    required_args = schema_info.required

    declared_property_count = len(declared_props)
    required_argument_count = len(required_args)

    # Check missing required arguments
    missing_required = [req for req in required_args if req not in args_dict]
    missing_req_count = len(missing_required)
    has_missing_req = missing_req_count > 0

    # Check unexpected argument keys and type mismatches
    unexpected_keys = []
    type_mismatches = []
    conformant_args = 0

    for arg_name, arg_val in args_dict.items():
        if arg_name not in declared_props:
            unexpected_keys.append(arg_name)
        else:
            # Key is declared; check value type compatibility
            prop_spec = declared_props[arg_name]
            if check_type_compatibility(arg_val, prop_spec):
                conformant_args += 1
            else:
                type_mismatches.append(arg_name)

    unexpected_key_count = len(unexpected_keys)
    has_unexpected_keys = unexpected_key_count > 0

    type_mismatch_count = len(type_mismatches)
    has_type_mismatch = type_mismatch_count > 0

    is_completely_conformant = (
        is_tool_known
        and is_schema_avail
        and not has_missing_req
        and not has_unexpected_keys
        and not has_type_mismatch
    )

    return {
        "is_tool_name_known": True,
        "is_schema_available": True,
        "is_call_id_valid": is_call_id_valid,
        "provided_argument_count": provided_arg_count,
        "declared_property_count": declared_property_count,
        "required_argument_count": required_argument_count,
        "missing_required_argument_count": missing_req_count,
        "has_missing_required_arguments": has_missing_req,
        "unexpected_argument_key_count": unexpected_key_count,
        "has_unexpected_argument_keys": has_unexpected_keys,
        "type_mismatch_count": type_mismatch_count,
        "has_type_mismatches": has_type_mismatch,
        "schema_conformant_argument_count": conformant_args,
        "is_completely_schema_conformant": is_completely_conformant,
    }
