import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, Alert, ScrollView } from 'react-native';
import { villageFetchApi } from '../../api/village_fetch';
import { useNavigation } from '@react-navigation/native';
import { VillageFetchResponse, SystemStatsSummary } from '../../types/api';

export default function BulkDashboardScreen() {
  const [jobs, setJobs] = useState<VillageFetchResponse[]>([]);
  const [stats, setStats] = useState<SystemStatsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const navigation = useNavigation<any>();

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [jobsData, statsData] = await Promise.all([
        villageFetchApi.listVillageFetches(),
        villageFetchApi.getStatsSummary().catch((err) => {
          console.warn("Failed to fetch system stats:", err.message);
          return null;
        })
      ]);
      setJobs(jobsData);
      setStats(statsData);
    } catch (err: unknown) {
      if (err instanceof Error) {
        Alert.alert("Error", err.message || "Failed to fetch jobs");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>;
    let isMounted = true;
    
    const poll = async () => {
      if (!isMounted) return;
      await fetchData();
      if (isMounted) {
        timeout = setTimeout(poll, 4000);
      }
    };

    poll();
    return () => {
      isMounted = false;
      clearTimeout(timeout);
    };
  }, [fetchData]);

  const renderBadge = (status: string) => {
    let backgroundColor = '#e2e8f0';
    let color = '#475569';
    if (status === 'COMPLETED') { backgroundColor = '#d1fae5'; color = '#065f46'; }
    if (status === 'FAILED') { backgroundColor = '#fee2e2'; color = '#991b1b'; }
    if (status === 'RUNNING') { backgroundColor = '#dbeafe'; color = '#1e40af'; }
    if (status === 'PAUSED') { backgroundColor = '#ffedd5'; color = '#c2410c'; }
    if (status === 'QUEUED') { backgroundColor = '#f3e8ff'; color = '#6b21a8'; }
    
    return (
      <View style={[styles.badge, { backgroundColor }]}>
        <Text style={[styles.badgeText, { color }]}>{status}</Text>
      </View>
    );
  };

  const renderItem = ({ item }: { item: VillageFetchResponse }) => {
    const createdDate = new Date(item.created_at).toLocaleString();
    return (
      <TouchableOpacity 
        style={styles.jobCard} 
        onPress={() => navigation.navigate('BulkDetail', { jobId: item.id })}
      >
        <View style={styles.jobHeader}>
          <Text style={styles.jobTitle}>{item.village_name || 'Village Fetch'}</Text>
          {renderBadge(item.status)}
        </View>
        <Text style={styles.jobSubText}>
          {item.district_name} &gt; {item.taluka_name} | Year: {item.year} | {createdDate}
        </Text>
        <View style={styles.jobDetailRow}>
          <Text style={styles.jobText}>Records Saved: <Text style={{ fontWeight: 'bold', color: '#10b981' }}>{item.unique_records_saved}</Text></Text>
          <Text style={styles.jobText}>Found: {item.records_found}</Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Village Fetches</Text>
        <TouchableOpacity style={styles.refreshBtn} onPress={fetchData}>
          <Text style={styles.refreshBtnText}>↻</Text>
        </TouchableOpacity>
      </View>
      
      {stats && (
        <View style={styles.statsContainer}>
          <Text style={styles.sectionTitle}>Acquisition Overview</Text>
          <View style={styles.statsGrid}>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Total Records</Text>
              <Text style={styles.statValue}>{stats.total_records}</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Village Fetches</Text>
              <Text style={styles.statValue}>{stats.total_village_fetches}</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statLabel}>Villages Covered</Text>
              <Text style={styles.statValue}>{stats.villages_covered}</Text>
            </View>
          </View>
        </View>
      )}

      <View style={styles.buttonRow}>
        <TouchableOpacity 
          style={[styles.createButton, { flex: 1, marginRight: 10 }]}
          onPress={() => navigation.navigate('BulkCreate')}
        >
          <Text style={styles.createButtonText}>+ New Village Fetch</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[styles.createButton, { flex: 1, backgroundColor: '#64748b' }]}
          onPress={() => navigation.navigate('NetworkSettings')}
        >
          <Text style={styles.createButtonText}>Network Settings</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.sectionTitle}>Recent Village Fetches</Text>
      {loading && jobs.length === 0 ? (
        <ActivityIndicator size="large" color="#2563eb" style={{ marginTop: 20 }} />
      ) : (
        <FlatList
          data={jobs}
          scrollEnabled={false}
          keyExtractor={item => item.id}
          renderItem={renderItem}
          contentContainerStyle={{ paddingBottom: 20 }}
          ListEmptyComponent={
            <View style={styles.emptyCard}>
              <Text style={{ color: '#64748b' }}>No village fetches recorded yet.</Text>
            </View>
          }
        />
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f8fafc' },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  title: { fontSize: 24, fontWeight: 'bold', color: '#1e293b' },
  refreshBtn: { padding: 10, backgroundColor: '#e2e8f0', borderRadius: 20, width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  refreshBtnText: { fontSize: 18, color: '#475569', fontWeight: 'bold' },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b', marginBottom: 10 },
  statsContainer: { marginBottom: 16 },
  statsGrid: { flexDirection: 'row', justifyContent: 'space-between' },
  statCard: { width: '31%', backgroundColor: 'white', padding: 12, borderRadius: 8, borderWidth: 1, borderColor: '#e2e8f0' },
  statLabel: { fontSize: 11, color: '#64748b', marginBottom: 4 },
  statValue: { fontSize: 18, fontWeight: 'bold', color: '#1e293b' },
  createButton: { backgroundColor: '#2563eb', padding: 14, borderRadius: 8, alignItems: 'center', marginBottom: 16 },
  buttonRow: { flexDirection: 'row', marginBottom: 10 },
  createButtonText: { color: 'white', fontWeight: 'bold', fontSize: 15 },
  jobCard: { backgroundColor: 'white', padding: 14, borderRadius: 8, marginBottom: 10, borderWidth: 1, borderColor: '#e2e8f0' },
  jobHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  jobTitle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  badgeText: { fontSize: 11, fontWeight: 'bold' },
  jobSubText: { fontSize: 12, color: '#64748b', marginBottom: 8 },
  jobDetailRow: { flexDirection: 'row', justifyContent: 'space-between' },
  jobText: { fontSize: 13, color: '#475569' },
  emptyCard: { backgroundColor: 'white', padding: 24, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#e2e8f0', marginTop: 10 }
});
