import enum

class ProcessingStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    PDF_PENDING = "PDF_PENDING"
    PDF_DOWNLOADED = "PDF_DOWNLOADED"
    PARSE_PENDING = "PARSE_PENDING"
    PARSED = "PARSED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

class PartyRole(str, enum.Enum):
    EXECUTANT = "EXECUTANT"
    CLAIMANT = "CLAIMANT"
    WITNESS = "WITNESS"
    OTHER = "OTHER"

class SearchJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    TRUNCATED = "TRUNCATED"
    RATE_LIMITED = "RATE_LIMITED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class PdfTaskStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    PARSE_PENDING = "PARSE_PENDING"
    PARSED = "PARSED"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_PDF = "INVALID_PDF"
    FAILED = "FAILED"

class ArtifactType(str, enum.Enum):
    HTML_SEARCH = "HTML_SEARCH"
    PDF_INDEXII = "PDF_INDEXII"

class RequestKind(str, enum.Enum):
    SEARCH = "SEARCH"
    PDF = "PDF"
    OTHER = "OTHER"

class IngestionRunStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class BulkFetchJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RATE_LIMITED = "RATE_LIMITED"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class CoverageStatus(str, enum.Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    TRUNCATED = "TRUNCATED"
    UNKNOWN = "UNKNOWN"

class ScopeType(str, enum.Enum):
    STATE = "STATE"
    DISTRICT = "DISTRICT"
    TALUKA = "TALUKA"
    VILLAGE = "VILLAGE"
