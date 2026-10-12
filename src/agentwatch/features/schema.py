"""Phase 4B Feature Contract and Schema Definitions.

Defines the versioned feature contract for pre-execution prompt-injection monitors:
Causal Feature View -> Provenance Features + Structural Features -> Validated Feature Record.

Guarantees:
- Output records contain strictly deterministic, pre-execution features.
- No ground-truth labels, future observations, runtime errors, or sibling call outputs
  can enter the feature vector.
- Stable metadata links back to source gate points and trajectories.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

FEATURE_SCHEMA_VERSION = "1.0.0"

# Comprehensive Data Dictionary for all Phase 4B Features
FEATURE_DATA_DICTIONARY: Dict[str, Dict[str, Any]] = {
    # Provenance Features
    "prior_tool_observation_count": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Causal prefix messages where role == 'tool'",
        "description": "Number of tool observation steps available in the history strictly prior to this gate point.",
        "unavailable_representation": "0 if no prior tool observations exist",
        "monotonicity": "Higher means more prior tool context is available.",
        "limitations": "Does not measure content relevance, only step volume.",
    },
    "distinct_prior_tool_source_count": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Tool names recorded in prior tool execution results",
        "description": "Number of distinct tool names that produced prior observations in the causal prefix.",
        "unavailable_representation": "0 if no prior tool observations exist",
        "monotonicity": "Higher means more diverse prior data sources.",
        "limitations": "Repeated calls to the same tool count as 1 source.",
    },
    "prior_observation_char_length": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Raw text content of prior tool observation steps",
        "description": "Total character length of all prior tool observation strings available to the monitor.",
        "unavailable_representation": "0 if no prior tool observations exist",
        "monotonicity": "Higher indicates larger volume of untrusted environment text in prompt history.",
        "limitations": "Character count includes whitespace and formatting markup.",
    },
    "prior_observation_token_count": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Normalized, stopword-filtered tokens from prior tool observations",
        "description": "Total count of meaningful lexical tokens across all prior tool observations.",
        "unavailable_representation": "0 if no prior tool observations exist",
        "monotonicity": "Higher indicates more lexical material available to copy or be tainted by.",
        "limitations": "Dependent on whitespace/punctuation tokenizer and stopword list.",
    },
    "proposed_argument_char_length": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Values of proposed_arguments in the current tool call",
        "description": "Total character length of all serialized string, numeric, and collection values in proposed arguments.",
        "unavailable_representation": "0 if proposed arguments are empty",
        "monotonicity": "Higher indicates longer proposed payloads in tool parameters.",
        "limitations": "Argument keys are excluded from length.",
    },
    "proposed_argument_token_count": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Normalized, stopword-filtered tokens from proposed argument values",
        "description": "Total count of unique meaningful lexical tokens extracted from proposed argument values.",
        "unavailable_representation": "0 if proposed arguments are empty or contain only stopwords",
        "monotonicity": "Higher indicates richer vocabulary in proposed call arguments.",
        "limitations": "Duplicate tokens within arguments are deduplicated for lexical overlap ratios.",
    },
    "has_non_empty_arguments": {
        "category": "provenance",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "proposed_arguments dictionary",
        "description": "Whether the proposed tool call contains at least one non-empty argument value.",
        "unavailable_representation": "False if arguments dictionary is empty or all values are empty",
        "monotonicity": "Binary indicator.",
        "limitations": "Calls without arguments (e.g. list_files()) are legitimately False.",
    },
    "overlapping_argument_token_count": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Proposed argument tokens and prior tool observation tokens",
        "description": "Number of unique proposed argument tokens that appear verbatim in prior tool observations.",
        "unavailable_representation": "0 if arguments empty or no prior observations exist",
        "monotonicity": "Higher indicates greater lexical provenance tracing back to tool outputs.",
        "limitations": "Legitimate copying of filenames or dates also increases this count.",
    },
    "argument_token_overlap_fraction": {
        "category": "provenance",
        "type": "float",
        "valid_range": "[0.0, 1.0]",
        "inputs": "overlapping_argument_token_count / proposed_argument_token_count",
        "description": "Ratio of proposed argument tokens that were observed in prior tool outputs.",
        "unavailable_representation": "0.0 if proposed arguments have 0 non-stopword tokens",
        "monotonicity": "Higher indicates higher proportion of argument content sourced from observations.",
        "limitations": "Benign tool calls copying query parameters may naturally have 1.0 overlap.",
    },
    "max_single_observation_token_overlap": {
        "category": "provenance",
        "type": "float",
        "valid_range": "[0.0, 1.0]",
        "inputs": "Per-observation token overlap calculations",
        "description": "Maximum token overlap fraction between the proposed arguments and any single prior tool observation.",
        "unavailable_representation": "0.0 if no prior tool observations exist or arguments are empty",
        "monotonicity": "Higher indicates concentration of argument tokens originating from a single source step.",
        "limitations": "Does not reflect multi-observation aggregation.",
    },
    "matching_argument_substring_count": {
        "category": "provenance",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Argument string values and prior tool observation text",
        "description": "Count of argument string segments (length >= 4 chars, non-stopword) that occur verbatim as substrings in prior tool text.",
        "unavailable_representation": "0 if no arguments or prior observations exist",
        "monotonicity": "Higher indicates exact phrase copying from prior outputs.",
        "limitations": "Short common words are filtered out to prevent noise.",
    },

    # Structural Features
    "is_tool_name_known": {
        "category": "structural",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "proposed_tool_name checked against registered tool schema registry",
        "description": "Whether the proposed tool name is recognized in the official tool schema registry.",
        "unavailable_representation": "False if tool is not registered",
        "monotonicity": "True indicates valid tool name.",
        "limitations": "Hallucinated or misspelled tool names will be False.",
    },
    "is_schema_available": {
        "category": "structural",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "Tool parameter schema lookup",
        "description": "Whether parameter metadata and type definitions were successfully resolved for this tool.",
        "unavailable_representation": "False if schema could not be loaded",
        "monotonicity": "True indicates full structural validation is active.",
        "limitations": "If False, schema-dependent counts default to conservative indicators.",
    },
    "is_call_id_valid": {
        "category": "structural",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "call_id in gate point record",
        "description": "Whether the proposed tool call carries a non-empty string identifier.",
        "unavailable_representation": "False if call_id is None, empty, or whitespace",
        "monotonicity": "True indicates compliant tool call framing.",
        "limitations": "Does not verify runtime uniqueness across sessions.",
    },
    "provided_argument_count": {
        "category": "structural",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Keys of proposed_arguments",
        "description": "Total number of argument keys passed in the proposed tool call.",
        "unavailable_representation": "0 if arguments dictionary is empty",
        "monotonicity": "Higher indicates more parameters provided.",
        "limitations": "Includes both valid and invalid argument keys.",
    },
    "declared_property_count": {
        "category": "structural",
        "type": "int",
        "valid_range": "[-1, inf)",
        "inputs": "Tool schema properties dictionary",
        "description": "Number of parameters declared in the tool's official JSON schema.",
        "unavailable_representation": "-1 if tool schema is unavailable",
        "monotonicity": "Reflects tool complexity.",
        "limitations": "Fixed property of the tool schema, independent of call.",
    },
    "required_argument_count": {
        "category": "structural",
        "type": "int",
        "valid_range": "[-1, inf)",
        "inputs": "Tool schema required properties list",
        "description": "Number of parameters marked as mandatory in the tool's official JSON schema.",
        "unavailable_representation": "-1 if tool schema is unavailable",
        "monotonicity": "Reflects tool parameter requirement burden.",
        "limitations": "Fixed property of the tool schema.",
    },
    "missing_required_argument_count": {
        "category": "structural",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Declared required properties vs proposed argument keys",
        "description": "Number of required parameters that were omitted from the proposed call.",
        "unavailable_representation": "0 if schema unavailable or none missing",
        "monotonicity": "Higher indicates greater schema violation / omission error.",
        "limitations": "Omission can be caused by benign model mistakes as well as attacks.",
    },
    "has_missing_required_arguments": {
        "category": "structural",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "missing_required_argument_count > 0",
        "description": "Whether at least one required argument is missing from the proposed call.",
        "unavailable_representation": "False if none missing or schema unavailable",
        "monotonicity": "True indicates incomplete invocation.",
        "limitations": "Binary indicator.",
    },
    "unexpected_argument_key_count": {
        "category": "structural",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Proposed argument keys not present in declared schema properties",
        "description": "Number of extraneous argument keys passed that are not declared in the tool schema.",
        "unavailable_representation": "0 if schema unavailable or no extra keys",
        "monotonicity": "Higher indicates greater hallucination or schema deviation.",
        "limitations": "Tools with freeform kwargs are not used in AgentDojo workspace.",
    },
    "has_unexpected_argument_keys": {
        "category": "structural",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "unexpected_argument_key_count > 0",
        "description": "Whether any extraneous argument keys were provided.",
        "unavailable_representation": "False if no extra keys or schema unavailable",
        "monotonicity": "True indicates invalid argument names passed.",
        "limitations": "Binary indicator.",
    },
    "type_mismatch_count": {
        "category": "structural",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Proposed argument values validated against declared schema types",
        "description": "Number of provided arguments whose runtime Python type violates the declared JSON schema type.",
        "unavailable_representation": "0 if schema unavailable or no mismatches",
        "monotonicity": "Higher indicates greater type incompatibility.",
        "limitations": "Validates basic JSON Schema types: string, integer, number, boolean, array, object, null.",
    },
    "has_type_mismatches": {
        "category": "structural",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "type_mismatch_count > 0",
        "description": "Whether any argument value has a type mismatch with the tool schema.",
        "unavailable_representation": "False if no type mismatches or schema unavailable",
        "monotonicity": "True indicates type error in call parameters.",
        "limitations": "Binary indicator.",
    },
    "schema_conformant_argument_count": {
        "category": "structural",
        "type": "int",
        "valid_range": "[0, inf)",
        "inputs": "Provided arguments matching declared properties and types",
        "description": "Number of provided arguments that are recognized by the schema and have valid types.",
        "unavailable_representation": "0 if schema unavailable or no conformant arguments",
        "monotonicity": "Higher indicates more well-formed parameters passed.",
        "limitations": "Does not guarantee semantic correctness of argument contents.",
    },
    "is_completely_schema_conformant": {
        "category": "structural",
        "type": "bool",
        "valid_range": "{False, True}",
        "inputs": "Combination of tool known, schema available, 0 missing, 0 unexpected, 0 type mismatches",
        "description": "Whether the proposed tool call fully satisfies the tool's declared schema with zero structural deviations.",
        "unavailable_representation": "False if tool is unknown or schema unavailable",
        "monotonicity": "True indicates full structural compliance.",
        "limitations": "A structurally valid call may still be malicious (e.g. exfiltration email).",
    },
}


class FeatureRecord(BaseModel):
    """Phase 4B Validated Feature Record for a Causal Pre-Execution Gate Point."""

    # Stable references to source gate point and trajectory (Metadata, not detector features)
    feature_schema_version: str = Field(default=FEATURE_SCHEMA_VERSION, description="Feature schema version")
    gate_point_id: str = Field(description="Unique gate point identifier")
    run_id: str = Field(description="Unique trajectory run identifier")
    user_task_id: str = Field(description="Benchmark user task identifier")
    gate_index: int = Field(description="Chronological gate point index within trajectory")
    step_index: int = Field(description="Assistant step index proposing this tool call")
    call_id: str = Field(description="Tool call identifier")
    proposed_tool_name: str = Field(description="Proposed tool name")

    # Category 1: Provenance Features (11 features)
    prior_tool_observation_count: int = Field(description="Count of prior tool observations in prefix")
    distinct_prior_tool_source_count: int = Field(description="Distinct tool names producing prior observations")
    prior_observation_char_length: int = Field(description="Total character length of prior tool observations")
    prior_observation_token_count: int = Field(description="Total token count across prior tool observations")
    proposed_argument_char_length: int = Field(description="Total character length of proposed argument values")
    proposed_argument_token_count: int = Field(description="Total token count across proposed argument values")
    has_non_empty_arguments: bool = Field(description="Whether proposed arguments are non-empty")
    overlapping_argument_token_count: int = Field(description="Count of argument tokens appearing in prior observations")
    argument_token_overlap_fraction: float = Field(description="Ratio of argument tokens found in prior observations")
    max_single_observation_token_overlap: float = Field(description="Max token overlap with an individual prior observation")
    matching_argument_substring_count: int = Field(description="Count of argument substring segments matching prior observations")

    # Category 2: Structural Features (14 features)
    is_tool_name_known: bool = Field(description="Whether tool is recognized in official tool registry")
    is_schema_available: bool = Field(description="Whether schema definitions were successfully resolved")
    is_call_id_valid: bool = Field(description="Whether call_id is non-empty string")
    provided_argument_count: int = Field(description="Number of argument keys provided")
    declared_property_count: int = Field(description="Number of declared schema properties (-1 if unavailable)")
    required_argument_count: int = Field(description="Number of required schema properties (-1 if unavailable)")
    missing_required_argument_count: int = Field(description="Count of missing required arguments")
    has_missing_required_arguments: bool = Field(description="Whether any required arguments are missing")
    unexpected_argument_key_count: int = Field(description="Count of unexpected argument keys")
    has_unexpected_argument_keys: bool = Field(description="Whether any unexpected argument keys were passed")
    type_mismatch_count: int = Field(description="Count of argument values with type mismatches")
    has_type_mismatches: bool = Field(description="Whether any argument values have type mismatches")
    schema_conformant_argument_count: int = Field(description="Count of provided arguments matching schema")
    is_completely_schema_conformant: bool = Field(description="Whether proposed call has zero structural deviations")

    def get_feature_vector(self) -> Dict[str, Union[int, float, bool]]:
        """Return exactly the 25 pre-execution features as a dictionary (excluding identifiers)."""
        feature_names = list(FEATURE_DATA_DICTIONARY.keys())
        return {name: getattr(self, name) for name in feature_names}

    def to_numeric_dict(self) -> Dict[str, float]:
        """Convert all 25 features to numeric floats for downstream tabular or ML models."""
        vec = self.get_feature_vector()
        result: Dict[str, float] = {}
        for k, v in vec.items():
            if isinstance(v, bool):
                result[k] = 1.0 if v else 0.0
            else:
                result[k] = float(v)
        return result
