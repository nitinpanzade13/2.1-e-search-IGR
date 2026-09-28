import { villageFetchApi } from './village_fetch';
import { VillageFetchCreateRequest, VillageFetchResponse } from '../types/api';

export const adminApi = {
  getSystemStats: async () => {
    return villageFetchApi.getStatsSummary();
  },
  createBulkFetch: async (payload: VillageFetchCreateRequest) => {
    return villageFetchApi.createVillageFetch(payload);
  },
  listBulkFetches: async (skip: number = 0, limit: number = 50) => {
    return villageFetchApi.listVillageFetches(skip, limit);
  },
  getBulkFetchJob: async (id: string) => {
    return villageFetchApi.getVillageFetch(id);
  },
  pauseJob: async (id: string) => {
    return villageFetchApi.pauseVillageFetch(id);
  },
  resumeJob: async (id: string) => {
    return villageFetchApi.resumeVillageFetch(id);
  },
  cancelJob: async (id: string) => {
    return villageFetchApi.cancelVillageFetch(id);
  }
};
