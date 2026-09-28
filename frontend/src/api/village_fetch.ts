import { apiClient } from './client';
import { 
  VillageFetchResponse, 
  VillageFetchCreateRequest, 
  RecordDetailListResponse, 
  RecordDetail,
  SystemStatsSummary 
} from '../types/api';

export const villageFetchApi = {
  createVillageFetch: async (payload: VillageFetchCreateRequest): Promise<VillageFetchResponse> => {
    const response = await apiClient.post<VillageFetchResponse>('/village-fetches', payload);
    return response.data;
  },

  listVillageFetches: async (skip: number = 0, limit: number = 50, village_id?: string): Promise<VillageFetchResponse[]> => {
    let url = `/village-fetches?skip=${skip}&limit=${limit}`;
    if (village_id) {
      url += `&village_id=${village_id}`;
    }
    const response = await apiClient.get<VillageFetchResponse[]>(url);
    return response.data;
  },

  getVillageFetch: async (id: string): Promise<VillageFetchResponse> => {
    const response = await apiClient.get<VillageFetchResponse>(`/village-fetches/${id}`);
    return response.data;
  },

  getVillageFetchRecords: async (
    fetchId: string, 
    page: number = 1, 
    pageSize: number = 50,
    q?: string
  ): Promise<RecordDetailListResponse> => {
    let url = `/village-fetches/${fetchId}/records?page=${page}&page_size=${pageSize}`;
    if (q) {
      url += `&q=${encodeURIComponent(q)}`;
    }
    const response = await apiClient.get<RecordDetailListResponse>(url);
    return response.data;
  },

  pauseVillageFetch: async (id: string): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post<{ status: string; message: string }>(`/village-fetches/${id}/pause`);
    return response.data;
  },

  resumeVillageFetch: async (id: string): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post<{ status: string; message: string }>(`/village-fetches/${id}/resume`);
    return response.data;
  },

  cancelVillageFetch: async (id: string): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post<{ status: string; message: string }>(`/village-fetches/${id}/cancel`);
    return response.data;
  },

  getRecords: async (params: {
    village_id?: string;
    year?: number;
    doc_no?: string;
    q?: string;
    page?: number;
    page_size?: number;
  }): Promise<RecordDetailListResponse> => {
    const response = await apiClient.get<RecordDetailListResponse>('/records', { params });
    return response.data;
  },

  getRecordDetail: async (id: string): Promise<RecordDetail> => {
    const response = await apiClient.get<RecordDetail>(`/records/${id}`);
    return response.data;
  },

  getStatsSummary: async (): Promise<SystemStatsSummary> => {
    const response = await apiClient.get<SystemStatsSummary>('/records/stats/summary');
    return response.data;
  },
};
