from pydantic import BaseModel
from typing import Dict

class ItemCounts(BaseModel):
    total: int

class RegistrationStats(BaseModel):
    total: int
    by_status: Dict[str, int]

class PdfTaskStats(BaseModel):
    total: int
    by_status: Dict[str, int]

class JobStats(BaseModel):
    total: int
    by_status: Dict[str, int]

class WorkerHealthStats(BaseModel):
    worker_type: str
    is_online: bool
    last_heartbeat: str | None = None
    current_job_id: str | None = None

class AdminStatsResponse(BaseModel):
    registrations: RegistrationStats
    pdf_tasks: PdfTaskStats
    parties: ItemCounts
    properties: ItemCounts
    artifacts: ItemCounts
    search_jobs: JobStats
    bulk_fetch_jobs: JobStats
    worker_health: list[WorkerHealthStats] = []
