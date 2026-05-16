"""Event extraction pipeline. app.py calls these functions; no Flask imports here."""

import json
import re
import ast

from .router import ProviderRouter

_EXTRACTION_SYSTEM = (
    "You are a structured event extraction engine. "
    "Given a narrative description of an event, extract the following fields "
    "and output them as a single JSON object.\n\n"
    "Required JSON fields:\n"
    '  "title": concise 3-8 word title (string)\n'
    '  "circumstance": 1-3 sentence factual description (string)\n'
    '  "actor_names": list of person names mentioned (non-empty list of strings; if no named individuals, use \"Unknown\")\n'
    '  "actor_actions": object mapping each actor name to a short factual action/role summary when available\n'
    '  "source": one of "self-report", "observation", "third-party" (string)\n\n'
    "Output ONLY valid JSON. No explanation, no prose. Start your response with {"
)


def _strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    return cleaned


def _balanced_json_candidate(text: str) -> str:
    cleaned = _strip_code_fences(text)
    start = cleaned.find("{")
    if start < 0:
        return ""

    snippet = cleaned[start:]
    end = snippet.rfind("}")
    if end >= 0:
        return snippet[: end + 1]

    # Conservative recovery for truncated objects.
    candidate = snippet.rstrip()
    if candidate.endswith(","):
        candidate = candidate[:-1]
    if candidate.endswith("["):
        candidate += "]"
    if candidate.endswith(":"):
        candidate += ' ""'

    missing_brackets = max(0, candidate.count("[") - candidate.count("]"))
    missing_braces = max(0, candidate.count("{") - candidate.count("}"))
    candidate += ("]" * missing_brackets) + ("}" * missing_braces)
    return candidate


def _parse_json_object(text: str) -> dict:
    candidate = _balanced_json_candidate(text)
    if not candidate:
        raise ValueError(f"Model output contained no JSON: {text[:300]}")

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model output was not valid JSON: {exc}") from exc


_WIKI_SYNTHESIS_SYSTEM = (
    "You maintain a personal intelligence wiki. "
    "Given a person's profile, a list of events they appeared in, and optionally an existing wiki page, "
    "write or update a concise markdown knowledge page about this person. "
    "The page should capture: who they are, their professional role, key interaction patterns, "
    "and any notable patterns or signals from recent events. "
    "Output ONLY the markdown page content. Start with # <Person Name>."
)


def synthesize_person_page(
    router: ProviderRouter,
    person_profile: str,
    events: list,
    existing_page: str = None,
) -> str:
    """
    Synthesize or update a wiki page for a person.

    Returns the new markdown page content string, or empty string if the model
    returns blank output.
    """
    prompt_parts = []
    if existing_page:
        prompt_parts.append(f"## Existing Wiki Page\n{existing_page}")
    prompt_parts.append(f"## Person Profile\n{person_profile}")
    if events:
        events_block = "\n".join(f"- {e}" for e in events)
        prompt_parts.append(f"## Events\n{events_block}")
    prompt_parts.append("Write the updated wiki page:")

    prompt = "\n\n".join(prompt_parts)
    result = router.route("wiki_synthesis", prompt, _WIKI_SYNTHESIS_SYSTEM)
    return "" if not result.text.strip() else result.text


_TOPIC_SYNTHESIS_SYSTEM = (
    "You maintain a personal intelligence wiki. "
    "Given a topic label, a list of relevant people, and their individual wiki pages, "
    "write a concise markdown knowledge page about this topic. "
    "The page should capture: what the topic is, who is involved, key patterns or outcomes, "
    "and any notable signals or open questions. "
    "End the page with a '## Sources' section listing the contributing person slugs. "
    "Output ONLY the markdown page content. Start with # <Topic Label>."
)


def synthesize_topic_page(
    router: ProviderRouter,
    label: str,
    people_pages: dict,
) -> str:
    """Synthesize a topic wiki page from a dict of {slug: page_content}.

    Returns the markdown string, or empty string on blank model output.
    """
    parts = [f"## Topic\n{label}"]
    for slug, content in people_pages.items():
        parts.append(f"## Person: {slug}\n{content}")
    parts.append("Write the topic wiki page:")
    prompt = "\n\n".join(parts)
    result = router.route("wiki_synthesis", prompt, _TOPIC_SYNTHESIS_SYSTEM)
    return "" if not result.text.strip() else result.text


def extract_event(
    router: ProviderRouter,
    narrative: str,
    date: str,
    time_str: str = "",
) -> dict:
    """
    First-pass extraction: narrative + date → structured dict.

    Returns a dict with keys: title, circumstance, actor_names, actor_actions, source,
    observed_at, _model_id, _latency_ms.

    Raises ValueError if the model output cannot be parsed as JSON.
    """
    prompt = f"Date: {date}"
    if time_str:
        prompt += f" {time_str}"
    prompt += f"\n\nNarrative:\n{narrative}\n\nExtract event fields as JSON:"

    result = router.route("extraction", prompt, _EXTRACTION_SYSTEM)

    data = _parse_json_object(result.text)

    observed_at = f"{date}T{time_str}:00" if time_str else f"{date}T00:00:00"
    actor_actions_raw = data.get("actor_actions", {})
    actor_actions = {}
    if isinstance(actor_actions_raw, dict):
        for actor_name, action_summary in actor_actions_raw.items():
            actor_name_clean = str(actor_name or "").strip()
            action_summary_clean = re.sub(r"\s+", " ", str(action_summary or "")).strip()
            if actor_name_clean and action_summary_clean:
                actor_actions[actor_name_clean] = action_summary_clean

    return {
        "title": str(data.get("title", "")).strip(),
        "circumstance": str(data.get("circumstance", "")).strip(),
        "actor_names": [str(n).strip() for n in data.get("actor_names", []) if n],
        "actor_actions": actor_actions,
        "source": str(data.get("source", "self-report")),
        "observed_at": observed_at,
        "_model_id": result.model_id,
        "_latency_ms": result.latency_ms,
    }


_JUDGE_SYSTEM = (
    "You are an extraction quality judge for a personal intelligence system. "
    "You will receive a raw narrative and the structured extraction produced by an extractor model. "
    "Your job: determine whether the extraction is complete and correct. "
    "actor_names must contain only human people mentioned in the narrative. "
    "Do not include organizations, companies, teams, projects, systems, locations, accounts, bills, tasks, or any non-person entities. "
    "If uncertain whether a name refers to a human person, exclude it from actor_names. "
    "Focus especially on actor completeness for people — are all named people from the narrative present in actor_names?\n\n"
    "Return ONLY a JSON object with these keys:\n"
    '  "pass": true if extraction is complete and correct, false otherwise\n'
    '  "actor_completeness_ok": true if all named individuals in the narrative appear in actor_names\n'
    '  "source_ok": true if the source classification is plausible given the narrative\n'
    '  "flags": list of strings describing any problems found (empty list if pass is true)\n'
    '  "suggested_actor_names": corrected actor list if pass is false; copy of original actor_names if pass is true\n\n'
    "Output ONLY valid JSON. No explanation, no prose. Start your response with {"
)


def _normalize_suggested_actor_names(value) -> list[str]:
    """Normalize judge-suggested actor names to a clean list of strings."""
    parsed = value
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("[") and raw.endswith("]"):
            try:
                literal = ast.literal_eval(raw)
                if isinstance(literal, list):
                    parsed = literal
                else:
                    parsed = [value]
            except (ValueError, SyntaxError):
                parsed = [value]
        else:
            parsed = [value]

    if not isinstance(parsed, list):
        parsed = [parsed]

    out = []
    for name in parsed:
        clean = re.sub(r"\s+", " ", str(name or "")).strip()
        if clean:
            out.append(clean)
    return out


def judge_extraction(
    router: ProviderRouter,
    narrative: str,
    extraction_result: dict,
    raw_text: str,
) -> tuple:
    """Run a judge LLM call to verify the extraction.

    Returns (verdict_dict, corrected_actor_list_or_None).

    - If verdict["pass"] is True: returns (verdict, None).
    - If verdict["pass"] is False and all suggested names pass the safety gate
      (each is a case-insensitive substring of raw_text): returns (verdict, suggested_actor_names).
    - If any suggested name fails the gate: returns (verdict, None).
    - On any exception: returns ({"pass": True, "flags": []}, None) — non-blocking.
    """
    try:
        actor_names = extraction_result.get("actor_names", [])
        prompt = (
            f"Raw narrative:\n{narrative}\n\n"
            f"Extraction result:\n"
            f"  actor_names: {actor_names}\n"
            f"  source: {extraction_result.get('source', '')}\n"
            f"  title: {extraction_result.get('title', '')}\n\n"
            "Judge this extraction:"
        )
        result = router.route("extraction_judge", prompt, _JUDGE_SYSTEM)
        verdict = _parse_json_object(result.text)

        if verdict.get("pass", True):
            return verdict, None

        suggested = _normalize_suggested_actor_names(
            verdict.get("suggested_actor_names", actor_names)
        )
        if not suggested:
            suggested = [str(n).strip() for n in actor_names if str(n or "").strip()]
        raw_lower = raw_text.lower()
        gate_passed = all(name.lower() in raw_lower for name in suggested)
        if gate_passed:
            return verdict, suggested
        return verdict, None
    except Exception:
        return {"pass": True, "flags": []}, None
