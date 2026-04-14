from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

HF_C_MODEL_REPO    = "2451-22-749-016/graphcodebert-c-bug-detector"
HF_JAVA_MODEL_REPO = "2451-22-749-016/graphcodebert-java-bug-detector"


def _resolve_path(path_value: str | None, default_relative: str | None = None) -> Path | None:
    if path_value:
        path = Path(path_value)
    elif default_relative:
        path = ROOT_DIR / default_relative
    else:
        return None

    if not path.is_absolute():
        path = ROOT_DIR / path

    return path.resolve()


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    graphcodebert_c_model_id: str
    graphcodebert_java_model_id: str
    google_application_credentials: Path | None
    gcp_project_id: str | None
    gcp_location: str
    gemini_model: str
    default_scan_folder: Path

    def validate_for_llm(self) -> None:
        if not self.google_application_credentials:
            raise ValueError(
                "GOOGLE_APPLICATION_CREDENTIALS is not set. Add it to .env."
            )

        if not self.google_application_credentials.exists():
            raise FileNotFoundError(
                f"Credential file not found: {self.google_application_credentials}"
            )

        if not self.gcp_project_id:
            raise ValueError("GCP_PROJECT_ID is not set. Add it to .env.")


def get_settings() -> Settings:
    return Settings(
        root_dir=ROOT_DIR,
        graphcodebert_c_model_id=os.getenv("GRAPHCODEBERT_C_MODEL_ID", HF_C_MODEL_REPO),
        graphcodebert_java_model_id=os.getenv("GRAPHCODEBERT_JAVA_MODEL_ID", HF_JAVA_MODEL_REPO),
        google_application_credentials=_resolve_path(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        ),
        gcp_project_id=os.getenv("GCP_PROJECT_ID"),
        gcp_location=os.getenv("GCP_LOCATION", "global"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        default_scan_folder=_resolve_path(
            os.getenv("DEFAULT_SCAN_FOLDER"),
            "test_project",
        ),
    )
