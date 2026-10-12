"""AgentWatch Features Subpackage."""

from agentwatch.features.schema import (
    FeatureRecord,
    FEATURE_SCHEMA_VERSION,
    FEATURE_DATA_DICTIONARY,
)
from agentwatch.features.registry import ToolSchemaRegistry, get_default_registry
from agentwatch.features.provenance import extract_provenance_features
from agentwatch.features.structural import extract_structural_features
from agentwatch.features.extractor import (
    GatePointFeatureExtractor,
    export_features_to_json,
    export_features_to_csv,
)
from agentwatch.features.evaluation import (
    CandidateRuleConfig,
    ExploratoryNegativeEvaluationReport,
    run_exploratory_benign_evaluation,
    assert_positive_metrics_blocked,
)

__all__ = [
    "FeatureRecord",
    "FEATURE_SCHEMA_VERSION",
    "FEATURE_DATA_DICTIONARY",
    "ToolSchemaRegistry",
    "get_default_registry",
    "extract_provenance_features",
    "extract_structural_features",
    "GatePointFeatureExtractor",
    "export_features_to_json",
    "export_features_to_csv",
    "CandidateRuleConfig",
    "ExploratoryNegativeEvaluationReport",
    "run_exploratory_benign_evaluation",
    "assert_positive_metrics_blocked",
]
