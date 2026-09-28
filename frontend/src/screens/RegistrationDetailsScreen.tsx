import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, ScrollView, SafeAreaView, ActivityIndicator, TouchableOpacity, Linking, Alert
} from 'react-native';
import { useRoute } from '@react-navigation/native';
import * as regApi from '../api/registrations';
import { RecordDetail } from '../types/api';

export default function RegistrationDetailsScreen() {
  const route = useRoute<any>();
  const { registrationId } = route.params;

  const [reg, setReg] = useState<RecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const details = await regApi.getRegistrationDetails(registrationId);
        setReg(details);
      } catch (err: unknown) {
        setError('Failed to load registration details');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [registrationId]);

  const openIndex2 = (url?: string) => {
    if (!url) {
      Alert.alert("Index II", "No Index II URL available.");
      return;
    }
    const fullUrl = url.startsWith('http') ? url : `https://esearchigr.maharashtra.gov.in${url.startsWith('/') ? '' : '/'}${url}`;
    Linking.openURL(fullUrl).catch(() => {
      Alert.alert("Error", `Could not open link: ${fullUrl}`);
    });
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  if (error || !reg) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error || "Record not found"}</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Document Information</Text>
          <View style={styles.card}>
            <View style={styles.row}>
              <Text style={styles.label}>Doc No / Year:</Text>
              <Text style={styles.value}>{reg.doc_no}/{reg.year}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>Type:</Text>
              <Text style={styles.value}>{reg.doc_type || 'N/A'}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>Office:</Text>
              <Text style={styles.value}>{reg.office || 'N/A'}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>Date:</Text>
              <Text style={styles.value}>{reg.date || 'N/A'}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.label}>Fetched At:</Text>
              <Text style={styles.value}>{new Date(reg.fetched_at).toLocaleString()}</Text>
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Parties</Text>
          <View style={styles.card}>
            <View style={styles.partyBox}>
              <Text style={styles.partyRole}>लिखून देणारा (Seller):</Text>
              <Text style={styles.partyName}>{reg.seller || 'N/A'}</Text>
            </View>
            <View style={[styles.partyBox, { borderTopWidth: 1, borderTopColor: '#f1f5f9', marginTop: 10, paddingTop: 10 }]}>
              <Text style={styles.partyRole}>लिखून घेणारा (Buyer):</Text>
              <Text style={styles.partyName}>{reg.buyer || 'N/A'}</Text>
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Property & Other Information</Text>
          <View style={styles.card}>
            <Text style={styles.descText}>{reg.other_info || 'No description available'}</Text>
          </View>
        </View>

        {reg.indexii_url && (
          <TouchableOpacity 
            style={styles.indexButton} 
            onPress={() => openIndex2(reg.indexii_url)}
          >
            <Text style={styles.indexButtonText}>📄 View Original Index II on IGR</Text>
          </TouchableOpacity>
        )}

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  scroll: { padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  errorText: { fontSize: 16, color: '#ef4444', textAlign: 'center' },
  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 16, fontWeight: 'bold', color: '#1e293b', marginBottom: 8 },
  card: { backgroundColor: '#ffffff', borderRadius: 8, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#f8fafc' },
  label: { fontSize: 14, color: '#64748b' },
  value: { fontSize: 14, color: '#1e293b', fontWeight: '600' },
  partyBox: {},
  partyRole: { fontSize: 12, color: '#64748b', fontWeight: 'bold' },
  partyName: { fontSize: 14, color: '#1e293b', marginTop: 2 },
  descText: { fontSize: 14, color: '#334155', lineHeight: 20 },
  indexButton: { backgroundColor: '#2563eb', padding: 16, borderRadius: 8, alignItems: 'center', marginTop: 10, marginBottom: 30 },
  indexButtonText: { color: 'white', fontWeight: 'bold', fontSize: 15 }
});
