"""Phase 4B Provenance Feature Extractor.

Extracts deterministic lexical and structural provenance features between proposed tool arguments
and prior tool observations in the causal interaction prefix.

Guarantees:
- Uses ONLY observations available strictly prior to the assistant decision step.
- Treats text overlap as a measurable signal, NOT an attack verdict.
- Zero dependency on ground-truth labels, attack names, or benchmark outcomes.
- Deterministic tokenization, normalization, and stopword filtering.
"""

import re
from typing import Any, Dict, List, Set, Tuple

STOPWORDS: Set[str] = {
    # English grammatical stopwords
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by", "of", "from",
    "as", "is", "was", "are", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "if", "then", "else", "when", "up", "down", "out", "over", "under", "again", "further",
    "once", "here", "there", "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can", "will",
    "just", "should", "now", "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "their", "our",
    # JSON / code keywords
    "null", "none", "true", "false", "type", "text", "content", "query", "id", "status",
}


def tokenize_text(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric and identifier tokens, stripping stopwords."""
    if not text:
        return []
    raw_tokens = re.findall(r"[a-zA-Z0-9_\-\.@]+", text.lower())
    clean_tokens: List[str] = []
    for tok in raw_tokens:
        tok = tok.strip(".-_@")
        if len(tok) >= 2 and tok not in STOPWORDS:
            clean_tokens.append(tok)
    return clean_tokens


def extract_leaf_values(obj: Any) -> List[str]:
    """Recursively collect leaf scalar values from a nested dictionary or list."""
    leaves: List[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            leaves.extend(extract_leaf_values(v))
    elif isinstance(obj, list):
        for item in obj:
            leaves.extend(extract_leaf_values(item))
    elif obj is not None:
        leaves.append(str(obj))
    return leaves


def extract_provenance_features(
    proposed_arguments: Dict[str, Any],
    available_prefix: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract 11 provenance features from proposed arguments and causal prefix messages."""
    # 1. Build call_id -> tool_name mapping from prior assistant steps
    call_to_tool: Dict[str, str] = {}
    for step in available_prefix:
        if step.get("role") == "assistant":
            for tc in step.get("tool_calls", []):
                cid = tc.get("call_id")
                t_name = tc.get("tool_name")
                if cid and t_name:
                    call_to_tool[cid] = str(t_name)

    # 2. Identify prior tool observations in available prefix
    prior_tool_steps = [s for s in available_prefix if s.get("role") == "tool"]
    prior_obs_count = len(prior_tool_steps)

    # 3. Extract distinct prior tool sources
    tool_sources: Set[str] = set()
    prior_obs_texts: List[str] = []

    for step in prior_tool_steps:
        # Check tool results for call_id lookup
        tool_results = step.get("tool_results", [])
        matched_source = False
        if tool_results:
            for tr in tool_results:
                cid = tr.get("call_id")
                if cid and cid in call_to_tool:
                    tool_sources.add(call_to_tool[cid])
                    matched_source = True
                elif tr.get("tool_name"):
                    tool_sources.add(str(tr.get("tool_name")))
                    matched_source = True

        if not matched_source:
            if step.get("name"):
                tool_sources.add(str(step.get("name")))
            else:
                tool_sources.add(f"tool_step_{step.get('step_index')}")


        # Collect raw text content
        content = step.get("content")
        if isinstance(content, str):
            prior_obs_texts.append(content)
        elif isinstance(content, list):
            # Formatted list of content blocks
            joined = " ".join(str(c.get("text", c.get("content", str(c)))) for c in content if isinstance(c, dict))
            prior_obs_texts.append(joined)
        elif content is not None:
            prior_obs_texts.append(str(content))

    distinct_source_count = len(tool_sources)
    combined_prior_text = "\n".join(prior_obs_texts)
    prior_char_len = len(combined_prior_text)

    # Tokenize prior observations
    per_obs_tokens: List[Set[str]] = [set(tokenize_text(txt)) for txt in prior_obs_texts]
    all_prior_tokens: Set[str] = set()
    for tok_set in per_obs_tokens:
        all_prior_tokens.update(tok_set)
    prior_token_count = len(all_prior_tokens)

    # 3. Process proposed arguments
    leaf_values = extract_leaf_values(proposed_arguments)
    combined_arg_text = " ".join(leaf_values)
    arg_char_len = sum(len(v) for v in leaf_values)

    has_non_empty = bool(proposed_arguments) and any(bool(v.strip()) for v in leaf_values if isinstance(v, str) or v)
    arg_tokens = tokenize_text(combined_arg_text)
    unique_arg_tokens = sorted(list(set(arg_tokens)))
    arg_token_count = len(unique_arg_tokens)

    # 4. Compute lexical overlap metrics
    if arg_token_count > 0 and all_prior_tokens:
        overlapping_tokens = [tok for tok in unique_arg_tokens if tok in all_prior_tokens]
        overlap_count = len(overlapping_tokens)
        overlap_fraction = round(overlap_count / arg_token_count, 6)

        # Max overlap with an individual observation
        max_single_overlap = 0.0
        for obs_tok_set in per_obs_tokens:
            if obs_tok_set:
                single_overlap_count = sum(1 for tok in unique_arg_tokens if tok in obs_tok_set)
                frac = single_overlap_count / arg_token_count
                if frac > max_single_overlap:
                    max_single_overlap = frac
        max_single_overlap = round(max_single_overlap, 6)
    else:
        overlap_count = 0
        overlap_fraction = 0.0
        max_single_overlap = 0.0

    # 5. Substring matching count
    # Count argument leaf segments (>= 4 chars, non-stopwords) occurring verbatim in prior observations
    substring_match_count = 0
    if prior_char_len > 0:
        prior_lower = combined_prior_text.lower()
        for leaf in leaf_values:
            clean_leaf = leaf.strip().lower()
            if len(clean_leaf) >= 4 and clean_leaf not in STOPWORDS:
                if clean_leaf in prior_lower:
                    substring_match_count += 1

    return {
        "prior_tool_observation_count": prior_obs_count,
        "distinct_prior_tool_source_count": distinct_source_count,
        "prior_observation_char_length": prior_char_len,
        "prior_observation_token_count": prior_token_count,
        "proposed_argument_char_length": arg_char_len,
        "proposed_argument_token_count": arg_token_count,
        "has_non_empty_arguments": has_non_empty,
        "overlapping_argument_token_count": overlap_count,
        "argument_token_overlap_fraction": overlap_fraction,
        "max_single_observation_token_overlap": max_single_overlap,
        "matching_argument_substring_count": substring_match_count,
    }
