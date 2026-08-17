def sanitize_citations(artifact: dict, allowed_ids: set[str]) -> dict:
    artifact["citations"] = [x for x in artifact.get("citations", []) if x in allowed_ids]
    for section in artifact.get("sections", []):
        section["citations"] = [x for x in section.get("citations", []) if x in allowed_ids]
    proposal = artifact.get("action_proposal")
    if proposal:
        proposal["evidence_ids"] = [x for x in proposal.get("evidence_ids", []) if x in allowed_ids]
    return artifact
