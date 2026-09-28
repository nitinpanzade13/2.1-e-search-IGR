export interface District {
  id: string;
  name_en: string;
  name_mr?: string;
  source_id: string;
}

export interface Taluka {
  id: string;
  name_en: string;
  name_mr?: string;
  source_id: string;
  district_id: string;
}

export interface Village {
  id: string;
  name_en: string;
  name_mr?: string;
  source_id: string;
  taluka_id: string;
}

export interface VillageFetchCreateRequest {
  district_id: string;
  taluka_id: string;
  village_id: string;
  year: number;
  survey_range_start?: number;
  survey_range_end?: number;
  search_query?: string;
  search_values?: string[];
  article_id?: string;
  article_name?: string;
}

export interface VillageFetchResponse {
  id: string;
  village_id: string;
  village_name?: string;
  taluka_name?: string;
  district_name?: string;
  year: number;
  status: 'QUEUED' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'CANCELLED';
  survey_range_start: number;
  survey_range_end: number;
  current_search_value?: string;
  processed_search_count: number;
  records_found: number;
  unique_records_saved: number;
  duplicates_skipped: number;
  truncated_searches_count: number;
  errors_count: number;
  last_error?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface RecordDetail {
  id: string;
  village_id: string;
  year: number;
  sr_no?: string;
  doc_no: string;
  doc_type?: string;
  office?: string;
  date?: string;
  seller?: string;
  buyer?: string;
  other_info?: string;
  indexii_url?: string;
  source_query?: string;
  is_truncated?: boolean;
  reported_count?: number;
  fetched_at: string;
}

export interface RecordDetailListResponse {
  items: RecordDetail[];
  total: number;
  page: number;
  page_size: number;
}

export interface SystemStatsSummary {
  total_records: number;
  total_village_fetches: number;
  villages_covered: number;
}

// Aliases for compatibility
export type BulkFetchJob = VillageFetchResponse;
export type BulkFetchCreateRequest = VillageFetchCreateRequest;
export type Registration = RecordDetail;
