from __future__ import annotations

from dataclasses import dataclass

from algenta.runtime_model_source_registration import SourceRegistration


@dataclass(frozen=True)
class ImportPreview:
    registration: SourceRegistration
    preview: str

    def to_dict(self) -> dict[str, object]:
        return {
            "registration": self.registration.to_dict(),
            "preview": self.preview,
        }


@dataclass(frozen=True)
class ImportFailure:
    source_ref: str
    code: str
    message: str
    name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_ref": self.source_ref,
            "code": self.code,
            "message": self.message,
            "name": self.name,
        }


@dataclass(frozen=True)
class ImportBundlePreview:
    registrations: list[SourceRegistration]
    failures: list[ImportFailure]
    preview: str

    def to_dict(self) -> dict[str, object]:
        return {
            "registrations": [registration.to_dict() for registration in self.registrations],
            "failures": [failure.to_dict() for failure in self.failures],
            "preview": self.preview,
        }
