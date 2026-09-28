import { apiClient } from './client';

export interface NetworkConfig {
  id: string;
  profile_name: string;
  interface_name: string;
  priority: number;
  is_enabled: boolean;
  connection_timeout: number;
  validation_timeout: number;
  created_at?: string;
  updated_at?: string;
}

export type NetworkConfigCreate = Omit<NetworkConfig, 'id' | 'created_at' | 'updated_at'>;

export const getNetworkConfigs = async () => {
  const response = await apiClient.get<NetworkConfig[]>('/network/configs');
  return response.data;
};

export const createNetworkConfig = async (data: NetworkConfigCreate) => {
  const response = await apiClient.post<NetworkConfig>('/network/configs', data);
  return response.data;
};

export const updateNetworkConfig = async (id: string, data: Partial<NetworkConfigCreate>) => {
  const response = await apiClient.put<NetworkConfig>(`/network/configs/${id}`, data);
  return response.data;
};

export const deleteNetworkConfig = async (id: string) => {
  const response = await apiClient.delete<{ok: boolean}>(`/network/configs/${id}`);
  return response.data;
};
