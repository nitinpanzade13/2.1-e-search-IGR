import { apiClient } from './client';
import { District, Taluka, Village } from '../types/api';

export const getDistricts = async (): Promise<District[]> => {
  const { data } = await apiClient.get('/locations/districts');
  return data;
};

export const getTalukas = async (districtId: string): Promise<Taluka[]> => {
  const { data } = await apiClient.get(`/locations/districts/${districtId}/talukas`);
  return data;
};

export const getVillages = async (talukaId: string): Promise<Village[]> => {
  const { data } = await apiClient.get(`/locations/talukas/${talukaId}/villages`);
  return data;
};
