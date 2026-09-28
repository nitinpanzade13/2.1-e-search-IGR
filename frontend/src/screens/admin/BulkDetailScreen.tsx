import React, { useEffect, useState, useCallback } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  ActivityIndicator, 
  Alert, 
  Linking 
} from 'react-native';
import { villageFetchApi } from '../../api/village_fetch';
import { useRoute } from '@react-navigation/native';
import { VillageFetchResponse, RecordDetail } from '../../types/api';

export default function BulkDetailScreen() {
  const [job, setJob] = useState<VillageFetchResponse | null>(null);
  const [records, setRecords] = useState<RecordDetail[]>([]);
  const [totalRecords, setTotalRecords] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 50;

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const route = useRoute<any>();
  const { jobId } = route.params;

  const fetchRecords = useCallback(async (p: number = 1) => {
    try {
      const data = await villageFetchApi.getVillageFetchRecords(jobId, p, pageSize);
      setRecords(data.items);
      setTotalRecords(data.total);
      setPage(data.page);
    } catch (err: unknown) {
      console.warn("Failed to fetch records page", err);
    }
  }, [jobId]);

  const fetchDetails = useCallback(async () => {
    try {
      const data = await villageFetchApi.getVillageFetch(jobId);
      setJob(data);

      await fetchRecords(page);

      if (['COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'].includes(data.status)) {
        return true; // terminal state
      }
      return false;
    } catch (err: unknown) {
      if (err instanceof Error) {
        Alert.alert("Error fetching details", err.message);
      }
      return true;
    } finally {
      setLoading(false);
    }
  }, [jobId, page, fetchRecords]);

  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>;
    let isMounted = true;
    
    const poll = async () => {
      if (!isMounted) return;
      const isTerminal = await fetchDetails();
      if (!isTerminal && isMounted) {
        timeout = setTimeout(poll, 2500);
      }
    };

    poll();
    return () => {
      isMounted = false;
      clearTimeout(timeout);
    };
  }, [fetchDetails]);

  const handleAction = (action: 'pause' | 'resume' | 'cancel') => {
    Alert.alert(`Confirm ${action}`, `Are you sure you want to ${action} this fetch?`, [
      { text: 'Cancel', style: 'cancel' },
      { 
        text: 'Confirm', 
        onPress: async () => {
          try {
            setActionLoading(true);
            if (action === 'pause') await villageFetchApi.pauseVillageFetch(jobId);
            if (action === 'resume') await villageFetchApi.resumeVillageFetch(jobId);
            if (action === 'cancel') await villageFetchApi.cancelVillageFetch(jobId);
            await fetchDetails();
          } catch (err: unknown) {
            if (err instanceof Error) {
              Alert.alert('Error', err.message);
            }
          } finally {
            setActionLoading(false);
          }
        }
      }
    ]);
  };

  const openIndex2 = (url?: string) => {
    if (!url) {
      Alert.alert("Index II", "No Index II document URL available for this record.");
      return;
    }
    const fullUrl = url.startsWith('http') ? url : `https://esearchigr.maharashtra.gov.in${url.startsWith('/') ? '' : '/'}${url}`;
    Linking.openURL(fullUrl).catch(() => {
      Alert.alert("Error", `Could not open Index II link: ${fullUrl}`);
    });
  };

  const renderBadge = (status: string) => {
    let backgroundColor = '#e2e8f0';
    let color = '#475569';
    if (status === 'COMPLETED') { backgroundColor = '#d1fae5'; color = '#065f46'; }
    if (status === 'PARTIAL') { backgroundColor = '#fef3c7'; color = '#92400e'; }
    if (status === 'FAILED') { backgroundColor = '#fee2e2'; color = '#991b1b'; }
    if (status === 'RUNNING') { backgroundColor = '#dbeafe'; color = '#1e40af'; }
    if (status === 'PAUSED') { backgroundColor = '#ffedd5'; color = '#c2410c'; }
    if (status === 'QUEUED') { backgroundColor = '#f3e8ff'; color = '#6b21a8'; }
    if (status === 'CANCELLED') { backgroundColor = '#f1f5f9'; color = '#64748b'; }
    
    return (
      <View style={[styles.badge, { backgroundColor }]}>
        <Text style={[styles.badgeText, { color }]}>{status}</Text>
      </View>
    );
  };

  if (loading && !job) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={{ marginTop: 12, color: '#64748b' }}>Loading village fetch details...</Text>
      </View>
    );
  }

  if (!job) {
    return (
      <View style={styles.centerContainer}>
        <Text style={{ fontSize: 16, color: '#64748b' }}>Village fetch job not found.</Text>
      </View>
    );
  }

  const totalPages = Math.ceil(totalRecords / pageSize) || 1;
  // Calculate current survey position in the range
  const getCurrentSurveyDisplay = () => {
    if (!job.current_search_value) {
      return `(${job.survey_range_start || 1}/${job.survey_range_end || 100})`;
    }
    
    const currentVal = parseInt(job.current_search_value);
    const start = job.survey_range_start || 1;
    const end = job.survey_range_end || 100;
    
    // If current value is within range, show position
    if (currentVal >= start && currentVal <= end) {
      return `(${currentVal - start + 1}/${end - start + 1})`;
    }
    
    // Fallback to showing the value
    return `(${job.current_search_value}/${end})`;
  };
  
  const currentSurveyDisplay = getCurrentSurveyDisplay();

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Village: {job.village_name || 'Village'}</Text>
          <Text style={styles.subTitle}>
            Year: <Text style={{ fontWeight: 'bold', color: '#1e293b' }}>{job.year}</Text> | {job.district_name} &gt; {job.taluka_name}
          </Text>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          {renderBadge(job.status)}
          <TouchableOpacity style={styles.refreshBtn} onPress={() => fetchDetails()}>
            <Text style={styles.refreshBtnText}>↻</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Live Metrics Grid matching exact requested view */}
      <View style={styles.metricsCard}>
        <Text style={styles.metricsCardTitle}>Live Acquisition Progress</Text>
        <View style={styles.metricsGrid}>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Current Survey</Text>
            <Text style={[styles.metricValue, { color: '#2563eb' }]}>{currentSurveyDisplay}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Surveys Processed</Text>
            <Text style={styles.metricValue}>{job.processed_search_count}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Records Returned</Text>
            <Text style={styles.metricValue}>{job.records_found.toLocaleString()}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Unique Saved</Text>
            <Text style={[styles.metricValue, { color: '#10b981' }]}>{job.unique_records_saved.toLocaleString()}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Duplicates</Text>
            <Text style={[styles.metricValue, { color: '#f59e0b' }]}>{job.duplicates_skipped.toLocaleString()}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Truncated Searches</Text>
            <Text style={[styles.metricValue, { color: job.truncated_searches_count > 0 ? '#b45309' : '#1e293b' }]}>
              {job.truncated_searches_count}
            </Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Errors</Text>
            <Text style={[styles.metricValue, { color: job.errors_count > 0 ? '#ef4444' : '#1e293b' }]}>
              {job.errors_count}
            </Text>
          </View>
        </View>

        {job.last_error && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>Latest Error: {job.last_error}</Text>
          </View>
        )}

        {job.truncated_searches_count > 0 && (
          <View style={styles.truncationNoteBox}>
            <Text style={styles.truncationNoteText}>
              ⚠️ {job.truncated_searches_count} search(es) hit IGR's 5,000 row cap and were marked TRUNCATED. All returned rows were saved.
            </Text>
          </View>
        )}
      </View>

      {/* Control Actions */}
      <View style={styles.actionRow}>
        {['RUNNING', 'QUEUED'].includes(job.status) && (
          <TouchableOpacity 
            style={[styles.actionBtn, { backgroundColor: '#f59e0b' }]} 
            onPress={() => handleAction('pause')}
            disabled={actionLoading}
          >
            <Text style={styles.actionBtnText}>Pause</Text>
          </TouchableOpacity>
        )}
        {job.status === 'PAUSED' && (
          <TouchableOpacity 
            style={[styles.actionBtn, { backgroundColor: '#10b981' }]} 
            onPress={() => handleAction('resume')}
            disabled={actionLoading}
          >
            <Text style={styles.actionBtnText}>Resume</Text>
          </TouchableOpacity>
        )}
        {!['COMPLETED', 'PARTIAL', 'CANCELLED'].includes(job.status) && (
          <TouchableOpacity 
            style={[styles.actionBtn, { backgroundColor: '#ef4444' }]} 
            onPress={() => handleAction('cancel')}
            disabled={actionLoading}
          >
            <Text style={styles.actionBtnText}>Cancel</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Village Record Table */}
      <View style={styles.sectionHeaderRow}>
        <Text style={styles.sectionTitle}>
          Record Details ({totalRecords.toLocaleString()} unique rows)
        </Text>
        <Text style={styles.pageInfo}>
          Page {page} of {totalPages}
        </Text>
      </View>

      {records.length === 0 ? (
        <View style={styles.emptyTable}>
          <Text style={{ color: '#64748b' }}>
            {job.status === 'RUNNING' ? 'Fetching and saving records from IGR...' : 'No records stored for this fetch.'}
          </Text>
        </View>
      ) : (
        <ScrollView horizontal={true} showsHorizontalScrollIndicator={true}>
          <View style={styles.table}>
            {/* Table Header: 10 columns matching IGR portal layout */}
            <View style={styles.tableHeaderRow}>
              <Text style={[styles.th, { width: 140 }]}>अनुक्रमांक (Doc No / Year)</Text>
              <Text style={[styles.th, { width: 110 }]}>दस्त नोंदणी दिनांक</Text>
              <Text style={[styles.th, { width: 140 }]}>दस्ताचा प्रकार</Text>
              <Text style={[styles.th, { width: 120 }]}>मोबदला (बाजारभाव)</Text>
              <Text style={[styles.th, { width: 160 }]}>दुय्यम निबंधक कार्यालय</Text>
              <Text style={[styles.th, { width: 230 }]}>पक्षकारांचे नाव (Parties)</Text>
              <Text style={[styles.th, { width: 250 }]}>मिळकत वर्णन (Description)</Text>
              <Text style={[styles.th, { width: 90 }]}>क्षेत्रफळ</Text>
              <Text style={[styles.th, { width: 90 }]}>आकारणी</Text>
              <Text style={[styles.th, { width: 120 }]}>इतर / Index II</Text>
              <Text style={[styles.th, { width: 90 }]}>Survey</Text>
            </View>

            {/* Table Body */}
            {records.map((r, idx) => (
              <View key={r.id || idx} style={[styles.tableRow, idx % 2 === 1 && styles.tableRowAlt]}>
                <View style={[styles.td, { width: 140 }]}>
                  <Text style={{ fontWeight: 'bold', color: '#1e293b' }}>
                    {r.doc_no || '-'}/{r.year}
                  </Text>
                  {r.is_truncated && (
                    <Text style={styles.truncatedTag}>TRUNCATED</Text>
                  )}
                </View>
                <Text style={[styles.td, { width: 110 }]}>{r.date || '-'}</Text>
                <Text style={[styles.td, { width: 140 }]}>{r.doc_type || '-'}</Text>
                <Text style={[styles.td, { width: 120 }]}>-</Text>
                <Text style={[styles.td, { width: 160 }]}>{r.office || '-'}</Text>
                <Text style={[styles.td, { width: 230 }]}>
                  {r.seller ? `विक्रेता: ${r.seller}\n` : ''}
                  {r.buyer ? `खरेदीदार: ${r.buyer}` : ''}
                </Text>
                <Text style={[styles.td, { width: 250 }]}>{r.other_info || '-'}</Text>
                <Text style={[styles.td, { width: 90 }]}>-</Text>
                <Text style={[styles.td, { width: 90 }]}>-</Text>
                <View style={[styles.td, { width: 120, justifyContent: 'center' }]}>
                  {r.indexii_url ? (
                    <TouchableOpacity 
                      style={styles.indexLinkBtn} 
                      onPress={() => openIndex2(r.indexii_url)}
                    >
                      <Text style={styles.indexLinkText}>📄 View Index II</Text>
                    </TouchableOpacity>
                  ) : (
                    <Text style={{ color: '#94a3b8', fontSize: 12 }}>N/A</Text>
                  )}
                </View>
                <View style={[styles.td, { width: 90, justifyContent: 'center' }]}>
                  <Text style={styles.surveyTag}>{r.source_query || '-'}</Text>
                </View>
              </View>
            ))}
          </View>
        </ScrollView>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <View style={styles.paginationRow}>
          <TouchableOpacity 
            style={[styles.pageBtn, page <= 1 && styles.pageBtnDisabled]}
            disabled={page <= 1}
            onPress={() => fetchRecords(page - 1)}
          >
            <Text style={styles.pageBtnText}>&lt; Previous</Text>
          </TouchableOpacity>
          <Text style={styles.pageIndicator}>Page {page} of {totalPages}</Text>
          <TouchableOpacity 
            style={[styles.pageBtn, page >= totalPages && styles.pageBtnDisabled]}
            disabled={page >= totalPages}
            onPress={() => fetchRecords(page + 1)}
          >
            <Text style={styles.pageBtnText}>Next &gt;</Text>
          </TouchableOpacity>
        </View>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f8fafc' },
  centerContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  title: { fontSize: 22, fontWeight: 'bold', color: '#1e293b' },
  subTitle: { fontSize: 13, color: '#64748b', marginTop: 2 },
  refreshBtn: { padding: 8, backgroundColor: '#e2e8f0', borderRadius: 20, width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  refreshBtnText: { fontSize: 18, color: '#475569', fontWeight: 'bold' },
  
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 12, fontWeight: 'bold' },

  metricsCard: { backgroundColor: 'white', padding: 16, borderRadius: 10, borderWidth: 1, borderColor: '#e2e8f0', marginBottom: 16 },
  metricsCardTitle: { fontSize: 15, fontWeight: 'bold', color: '#1e293b', marginBottom: 12 },
  metricsGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: 12 },
  metricItem: { width: '31%', backgroundColor: '#f8fafc', padding: 10, borderRadius: 8, borderWidth: 1, borderColor: '#edf2f7' },
  metricLabel: { fontSize: 11, color: '#64748b', marginBottom: 4 },
  metricValue: { fontSize: 16, fontWeight: 'bold', color: '#0f172a' },

  errorBox: { backgroundColor: '#fee2e2', padding: 10, borderRadius: 6, marginTop: 12 },
  errorText: { color: '#991b1b', fontSize: 12 },

  truncationNoteBox: { backgroundColor: '#fef3c7', padding: 10, borderRadius: 6, marginTop: 12, borderWidth: 1, borderColor: '#fde68a' },
  truncationNoteText: { color: '#92400e', fontSize: 12, fontWeight: '500' },

  actionRow: { flexDirection: 'row', justifyContent: 'flex-start', gap: 10, marginBottom: 16 },
  actionBtn: { paddingVertical: 10, paddingHorizontal: 20, borderRadius: 6, alignItems: 'center' },
  actionBtnText: { color: 'white', fontWeight: 'bold', fontSize: 14 },

  sectionHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' },
  pageInfo: { fontSize: 12, color: '#64748b' },

  emptyTable: { backgroundColor: 'white', padding: 30, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#e2e8f0' },
  table: { backgroundColor: 'white', borderRadius: 8, borderWidth: 1, borderColor: '#cbd5e1', overflow: 'hidden' },
  tableHeaderRow: { flexDirection: 'row', backgroundColor: '#f1f5f9', borderBottomWidth: 1, borderBottomColor: '#cbd5e1' },
  th: { padding: 10, fontWeight: 'bold', fontSize: 12, color: '#334155' },
  tableRow: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: '#f1f5f9', alignItems: 'center' },
  tableRowAlt: { backgroundColor: '#f8fafc' },
  td: { padding: 10, fontSize: 12, color: '#1e293b' },
  indexLinkBtn: { backgroundColor: '#eff6ff', paddingVertical: 4, paddingHorizontal: 8, borderRadius: 4, borderWidth: 1, borderColor: '#bfdbfe' },
  indexLinkText: { color: '#2563eb', fontSize: 11, fontWeight: '600' },
  truncatedTag: { fontSize: 9, color: '#b45309', backgroundColor: '#fef3c7', paddingHorizontal: 4, paddingVertical: 1, borderRadius: 3, marginTop: 2, alignSelf: 'flex-start', fontWeight: 'bold' },
  surveyTag: { fontSize: 11, color: '#475569', backgroundColor: '#f1f5f9', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, textAlign: 'center', fontWeight: 'bold' },

  paginationRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 16, gap: 16 },
  pageBtn: { paddingVertical: 8, paddingHorizontal: 14, backgroundColor: '#2563eb', borderRadius: 6 },
  pageBtnDisabled: { backgroundColor: '#cbd5e1' },
  pageBtnText: { color: 'white', fontWeight: 'bold', fontSize: 12 },
  pageIndicator: { fontSize: 13, color: '#475569' }
});
