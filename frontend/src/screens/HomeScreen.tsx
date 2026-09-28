import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, SafeAreaView, ActivityIndicator, ScrollView } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { apiClient } from '../api/client';
import { adminApi } from '../api/admin_api';

export default function HomeScreen() {
  const navigation = useNavigation<any>();
  const [status, setStatus] = useState<string>('Checking...');
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const { data } = await apiClient.get('/health');
        setStatus(data.status === 'ok' ? 'Connected' : 'Error');
      } catch (err) {
        setStatus('Disconnected');
      }
    };
    const fetchStats = async () => {
      try {
        const data = await adminApi.getSystemStats();
        setStats(data);
      } catch (err) {
        // Stats failed to load, ignore
      }
    };
    checkHealth();
    fetchStats();
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>Maharashtra IGR</Text>
          <Text style={styles.subtitle}>e-Search</Text>
          <Text style={styles.subtext}>Property Registration Search</Text>
        </View>

        <View style={styles.content}>
          <TouchableOpacity 
            style={styles.button}
            onPress={() => navigation.navigate('Search')}
          >
            <Text style={styles.buttonText}>Search Registration</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.button, { marginTop: 20, backgroundColor: '#475569' }]}
            onPress={() => navigation.navigate('BulkDashboard')}
          >
            <Text style={styles.buttonText}>Admin Dashboard</Text>
          </TouchableOpacity>
        </View>

        {stats && (
          <View style={styles.statsContainer}>
            <Text style={styles.statsTitle}>Acquisition Stats</Text>
            <View style={styles.statsGrid}>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>Total Records</Text>
                <Text style={styles.statValue}>{stats.total_records || 0}</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statLabel}>Village Fetches</Text>
                <Text style={styles.statValue}>{stats.total_village_fetches || 0}</Text>
              </View>
              <View style={[styles.statCard, { width: '100%' }]}>
                <Text style={styles.statLabel}>Villages Covered</Text>
                <Text style={styles.statValue}>{stats.villages_covered || 0}</Text>
              </View>
            </View>
          </View>
        )}
      </ScrollView>
      <View style={styles.footer}>
        <View style={styles.statusRow}>
          <View style={[styles.statusDot, { backgroundColor: status === 'Connected' ? '#4ade80' : '#f87171' }]} />
          <Text style={styles.statusText}>Backend: {status}</Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  scrollContent: {
    flexGrow: 1,
  },
  header: {
    padding: 32,
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1e293b',
  },
  subtitle: {
    fontSize: 32,
    fontWeight: '900',
    color: '#2563eb',
    marginTop: 4,
  },
  subtext: {
    fontSize: 16,
    color: '#64748b',
    marginTop: 8,
  },
  content: {
    padding: 24,
  },
  button: {
    backgroundColor: '#2563eb',
    padding: 18,
    borderRadius: 12,
    alignItems: 'center',
    shadowColor: '#2563eb',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  buttonText: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  statsContainer: {
    padding: 24,
    paddingTop: 0,
  },
  statsTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1e293b',
    marginBottom: 12,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  statCard: {
    width: '48%',
    backgroundColor: '#ffffff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  statLabel: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 4,
  },
  statValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#0f172a',
  },
  footer: {
    padding: 16,
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    backgroundColor: '#ffffff',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  statusText: {
    fontSize: 14,
    color: '#64748b',
  }
});
