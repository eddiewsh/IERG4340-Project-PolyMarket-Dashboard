import json
import os
import re
from glob import glob


def _norm_words(text: str) -> list[str]:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return [w for w in t.split(" ") if w]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _area_from_files(files: list[str]) -> str:
    joined = " ".join(files).lower()
    if "\\frontend\\" in joined or "/frontend/" in joined:
        if "aichatpanel" in joined or "chathistory" in joined or "/rag/" in joined:
            return "Frontend — Chat / RAG UI"
        if "newspanel" in joined:
            return "Frontend — News UI"
        if "market" in joined:
            return "Frontend — Polymarket UI"
        return "Frontend"
    if "\\backend\\" in joined or "/backend/" in joined:
        if "\\services\\news\\" in joined or "/services/news/" in joined or "\\api\\routes\\news" in joined:
            return "Backend — News"
        if "\\services\\rag\\" in joined or "/services/rag/" in joined or "\\api\\routes\\rag" in joined:
            return "Backend — RAG / Gemini"
        if "monitor" in joined or "polymarket" in joined:
            return "Backend — Polymarket / Monitor"
        return "Backend"
    return "Other"


def _rewrite_user_intent(user_text: str, area: str) -> str:
    t = (user_text or "").strip()
    t = re.sub(r"\bplz\b", "please", t, flags=re.I)
    t = re.sub(r"\bpls\b", "please", t, flags=re.I)
    t = re.sub(r"\bu\b", "you", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    low = t.lower()

    # Paraphrase into a clean request (do not quote verbatim).
    if "news" in low and ("disappear" in low or "always disappear" in low):
        return f"Stabilize the news feed so items do not randomly vanish after refresh/polling. ({area})"
    if "all" in low and "global" in low and "news" in low:
        return f"Fix the All/Global news view so it reliably loads articles on first open. ({area})"
    if "breaking" in low and ("delete" in low or "remove" in low):
        return f"Remove the Breaking News toggle and simplify the news UI behavior. ({area})"
    if "polymarket" in low and ("few" in low or "200" in low or "infinity" in low or "scroll" in low):
        return f"Increase Polymarket list capacity by adding pagination and infinite scrolling (target 200+ items). ({area})"
    if "orange" in low and ("button" in low or "click" in low):
        return f"Fix the non-clickable action button in the chat panel. ({area})"
    if "new chat" in low and ("immediate" in low or "create" in low):
        return f"Create a new conversation immediately when starting a new chat, and persist messages correctly. ({area})"
    if "history" in low and ("show" in low or "chat history" in low):
        return f"Make chat history selection load and display the correct conversation in the chat panel. ({area})"

    # Default: do NOT copy raw prompt text. Create a short request summary from keywords.
    stop = {
        "the","a","an","and","or","to","of","in","on","for","with","is","are","was","were","be","been",
        "it","this","that","these","those","i","you","we","they","he","she","my","your","our","their",
        "please","plz","pls","can","could","would","should","why","what","when","where","how",
        "fix","make","use","need","want","dont","don't","no","not","still","just",
    }
    words = [w for w in _norm_words(t) if w not in stop]
    uniq: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        uniq.append(w)
        if len(uniq) >= 6:
            break
    topic = ", ".join(uniq) if uniq else "general improvements"
    return f"General improvements request focused on: {topic}. ({area})"


def _is_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _english_output(note: str, files: list[str]) -> str:
    n = (note or "").strip()
    if not n:
        return "Implemented the requested changes."
    if not _is_cjk(n):
        return n
    # If note is Chinese, replace with a neutral English output.
    # (We intentionally avoid machine translation here; we keep it concise and accurate.)
    touched = ", ".join(sorted({os.path.basename(f) for f in files})[:6])
    extra = f" (Touched: {touched})" if touched else ""
    return "Implemented the requested changes and updated the relevant frontend/backend logic accordingly." + extra


def _correct_english(user_text: str) -> str:
    t = (user_text or "").strip()
    t = re.sub(r"\bplz\b", "please", t, flags=re.I)
    t = re.sub(r"\bpls\b", "please", t, flags=re.I)
    t = re.sub(r"\bdont\b", "don't", t, flags=re.I)
    t = re.sub(r"\bim\b", "I'm", t, flags=re.I)
    t = re.sub(r"\bu\b", "you", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    if t:
        t = t[0].upper() + t[1:]
        if not t.endswith((".", "?", "!")):
            t += "."
    return t


def _function_from_files_and_intent(files: list[str], intent: str) -> str:
    f = " ".join(files).lower()
    i = (intent or "").lower()
    if "newspanel.tsx" in f or "news" in i:
        if "updated time" in i or "updated_at" in f or "updated:" in i:
            return "News UI: show updated time"
        if "all/global" in i or "global" in i:
            return "News UI: All/Global loading"
        if "disappear" in i or "vanish" in i:
            return "News feed: cache stability"
        return "News UI"
    if "monitor_markets" in f or "marketcardlist" in f or "polymarket" in i:
        if "pagination" in i or "infinite" in i or "200" in i:
            return "Polymarket list: pagination + infinite scroll"
        return "Polymarket list"
    if "aichatpanel" in f or "rag.py" in f or "chat" in i or "summarize" in i:
        if "non-clickable" in i or "button" in i:
            return "Chat UI: action button clickable"
        if "history selection" in i or "history" in i:
            return "Chat UI: load selected history"
        if "saved" in i or "persist" in i:
            return "Chat/RAG: persist summarize to history"
        if "gemini" in i or "flash" in i:
            return "Gemini: model selection / chat summary"
        return "Chat/RAG UI"
    if "gemini_embedder" in f:
        return "Gemini client: request/limit handling"
    return "General"


def _iter_transcript_files(root: str) -> list[str]:
    paths: list[str] = []
    for p in glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        if f"{os.path.sep}subagents{os.path.sep}" in p:
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read()
            if '"name":"ApplyPatch"' in txt or '"name": "ApplyPatch"' in txt:
                paths.append(p)
        except Exception:
            continue
    paths.sort(key=lambda p: os.path.getmtime(p))
    return paths


def _extract_entries(path: str) -> list[dict]:
    entries: list[dict] = []
    last_user: str | None = None
    files: set[str] = set()
    last_assistant_text: str | None = None

    def flush():
        nonlocal last_user, files, last_assistant_text
        if last_user and files:
            notes = (last_assistant_text or "").strip()
            if notes:
                parts = [p.strip() for p in re.split(r"\n\s*\n", notes) if p.strip()]
                parts = [
                    p
                    for p in parts
                    if not (
                        p.startswith("**")
                        and any(k in p for k in ("Patching", "Debugging", "Updating", "Applying", "Exploring"))
                    )
                ]
                parts = [
                    p
                    for p in parts
                    if not re.match(r"^(I need to|I'm |I’m |Let's |I plan to|I will |I’ll )", p)
                ]
                notes = "\n\n".join(parts[:3])
            entries.append(
                {
                    "user": last_user,
                    "files": sorted(files),
                    "assistant_notes": notes[:800].strip(),
                }
            )
        last_user = None
        files = set()
        last_assistant_text = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            role = obj.get("role")
            msg = obj.get("message", {}) or {}
            content = msg.get("content", []) or []

            if role == "user":
                flush()
                text_parts: list[str] = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text_parts.append(c.get("text", "") or "")
                text = "\n".join(text_parts).strip()
                if text:
                    m = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.S)
                    last_user = (m.group(1).strip() if m else text).strip()

            elif role == "assistant":
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use" and c.get("name") == "ApplyPatch":
                        patch = c.get("input", "") or ""
                        for mm in re.finditer(r"\*\*\* (?:Update|Add) File: (.+)", patch):
                            files.add(mm.group(1).strip())
                    if c.get("type") == "text":
                        t = (c.get("text", "") or "").strip()
                        if t and "[REDACTED]" not in t:
                            # Prefer concise "done/fixed" summaries over internal planning text.
                            prefer = any(
                                k in t
                                for k in (
                                    "已修",
                                    "已做完",
                                    "已完成",
                                    "Done",
                                    "Already switched",
                                    "已把",
                                    "已改",
                                    "已加",
                                    "已移除",
                                )
                            )
                            if prefer or last_assistant_text is None:
                                last_assistant_text = t

    flush()
    return entries


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    transcripts_root = os.environ.get(
        "CURSOR_AGENT_TRANSCRIPTS",
        r"C:\Users\szeho\.cursor\projects\c-Users-szeho-Music-startup-IERG4340\agent-transcripts",
    )

    out_dir = os.path.join(repo_root, "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "prompt-log.md")

    tpaths = _iter_transcript_files(transcripts_root)
    all_entries: list[dict] = []
    for p in tpaths:
        tid = os.path.basename(p).replace(".jsonl", "")
        for e in _extract_entries(p):
            e["transcript"] = tid
            all_entries.append(e)

    # Group entries by area (one section per module/function area).
    groups_by_area: dict[str, dict] = {}
    area_order: list[str] = []
    for e in all_entries:
        files = e.get("files") or []
        area = _area_from_files(files)
        if area not in groups_by_area:
            groups_by_area[area] = {"area": area, "files": set(), "entries": []}
            area_order.append(area)
        g = groups_by_area[area]
        g["entries"].append(e)
        g["files"].update(files)
    groups = [groups_by_area[a] for a in area_order]

    with open(out_path, "w", encoding="utf-8") as w:
        w.write("## Prompt Log（Function / Request / Output）\n\n")
        w.write("Format: Function → Request (corrected English) → Output.\n\n")
        for i, g in enumerate(groups, start=1):
            area = g["area"]
            entries = g["entries"]
            # Build combined intent list (dedup).
            intents: list[str] = []
            for e in entries:
                intent = _rewrite_user_intent(e.get("user", ""), area)
                if intent and intent not in intents:
                    intents.append(intent)

            # Prefer later entry notes within the group.
            note = ""
            for e in reversed(entries):
                note = (e.get("assistant_notes") or "").strip()
                if note:
                    break

            func = _function_from_files_and_intent(sorted(g["files"]), " ".join(intents))
            w.write(f"### {i}. Function\n\n{func}\n\n")
            w.write("### Request\n\n")
            seen_corr: set[str] = set()
            for e in entries:
                orig = (e.get("user") or "").strip()
                if not orig:
                    continue
                corr = _correct_english(orig)
                if not corr or corr in seen_corr:
                    continue
                seen_corr.add(corr)
                w.write(f"- {corr}\n")
            w.write("\n")
            w.write("### Output\n\n")
            w.write(_english_output(note, sorted(g["files"])) + "\n\n")

    print(out_path)
    print(f"entries={len(all_entries)} groups={len(groups)} transcripts_with_applypatch={len(tpaths)}")


if __name__ == "__main__":
    main()

