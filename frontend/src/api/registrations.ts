import { apiClient } from './client';
import { RecordDetail } from '../types/api';

export const getRegistrationDetails = async (id: string): Promise<RecordDetail> => {
  const { data } = await apiClient.get<RecordDetail>(`/records/${id}`);
  return data;
};
