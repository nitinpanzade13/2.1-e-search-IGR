import { villageFetchApi } from './village_fetch';
import { RecordDetailListResponse } from '../types/api';

export interface SearchParams {
  year: number;
  village_id: string;
  survey_query?: string;
  page?: number;
  page_size?: number;
}

export const getSearchResults = async (
  villageId: string, 
  year?: number, 
  surveyQuery?: string, 
  page: number = 1, 
  pageSize: number = 50
): Promise<RecordDetailListResponse> => {
  return villageFetchApi.getRecords({
    village_id: villageId,
    year,
    doc_no: surveyQuery,
    page,
    page_size: pageSize
  });
};
