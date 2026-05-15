import json
import shutil
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = BASE_DIR / "storage" / "sessions"
UPLOADS_DIR = BASE_DIR / "uploads"

# Ensure directories exist
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

class SessionManager:
    @staticmethod
    def _get_path(session_id: str) -> Path:
        return SESSIONS_DIR / f"{session_id}.json"

    @staticmethod
    def save_session(session_id: str, data: dict):
        if not session_id:
            return
        
        # Merge if exists
        existing = SessionManager.load_session(session_id)
        if existing:
            existing.update(data)
            data = existing
        else:
            if "created_at" not in data:
                data["created_at"] = datetime.now().isoformat()
            if "title" not in data:
                data["title"] = "New Chat"

        data["updated_at"] = datetime.now().isoformat()

        with open(SessionManager._get_path(session_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_session(session_id: str) -> dict:
        path = SessionManager._get_path(session_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    @staticmethod
    def list_sessions() -> list:
        sessions = []
        for file in SESSIONS_DIR.glob("*.json"):
            sid = file.stem
            data = SessionManager.load_session(sid)
            if data:
                sessions.append({
                    "id": sid,
                    "title": data.get("title", "New Chat"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "dataset_path": data.get("dataset_path", ""),
                    "dataset_name": data.get("dataset_name", "")
                })
        # Sort descending by updated_at
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions

    @staticmethod
    def delete_session(session_id: str):
        path = SessionManager._get_path(session_id)
        if path.exists():
            path.unlink()

    @staticmethod
    def update_dataset(session_id: str, original_file_path: str, dataset_name: str):
        if not original_file_path or not os.path.exists(original_file_path):
            return
            
        ext = Path(original_file_path).suffix
        persistent_path = UPLOADS_DIR / f"{session_id}_{dataset_name}{ext}"
        
        shutil.copy2(original_file_path, persistent_path)
        
        SessionManager.save_session(session_id, {
            "dataset_path": str(persistent_path),
            "dataset_name": dataset_name
        })

    @staticmethod
    def append_message(session_id: str, role: str, content: str):
        data = SessionManager.load_session(session_id)
        if "history" not in data:
            data["history"] = []
        data["history"].append({"role": role, "content": content})
        SessionManager.save_session(session_id, data)
