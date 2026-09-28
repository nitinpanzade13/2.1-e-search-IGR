import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, FlatList, TouchableOpacity, SafeAreaView, ActivityIndicator, Linking
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { villageFetchApi } from '../api/village_fetch';
import { RecordDetail } from '../types/api';

export default function SearchResultsScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { villageId, year, docNo, villageName } = route.params || {};

  const [results, setResults] = useState<RecordDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadResults();
  }, [villageId, year, docNo]);

  const loadResults = async () => {
    try {
      setLoading(true);
      const res = await villageFetchApi.getRecords({
        village_id: villageId,
        year: year ? Number(year) : undefined,
        doc_no: docNo || undefined,
        page: 1,
        page_size: 50
      });
      setResults(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load records');
    } finally {
      setLoading(false);
    }
  };

  const openIndex2 = (url?: string) => {
    if (!url) return;
    const fullUrl = url.startsWith('http') ? url : `https://esearchigr.maharashtra.gov.in${url.startsWith('/') ? '' : '/'}${url}`;
    Linking.openURL(fullUrl).catch(console.error);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.loadingText}>Searching Database Records...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.button} onPress={() => navigation.goBack()}>
          <Text style={styles.buttonText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {villageName ? `${villageName} Records` : 'Search Results'} ({results.length})
        </Text>
      </View>

      <FlatList
        data={results}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No records found matching criteria in database.</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity 
            style={styles.card}
            onPress={() => navigation.navigate('RegistrationDetails', { registrationId: item.id })}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.docNo}>Doc No: {item.doc_no}/{item.year}</Text>
              <Text style={styles.docType}>{item.doc_type || 'Registration'}</Text>
            </View>
            <View style={styles.cardBody}>
              <Text style={styles.bodyText}><Text style={styles.bold}>Date:</Text> {item.date || 'N/A'}</Text>
              <Text style={styles.bodyText}><Text style={styles.bold}>Office:</Text> {item.office || 'N/A'}</Text>
              {item.seller && (
                <Text style={styles.bodyText} numberOfLines={1}>
                  <Text style={styles.bold}>Seller:</Text> {item.seller}
                </Text>
              )}
              {item.buyer && (
                <Text style={styles.bodyText} numberOfLines={1}>
                  <Text style={styles.bold}>Buyer:</Text> {item.buyer}
                </Text>
              )}
            </View>
            {item.indexii_url && (
              <TouchableOpacity 
                style={styles.indexLink}
                onPress={() => openIndex2(item.indexii_url)}
              >
                <Text style={styles.indexLinkText}>📄 View Index II</Text>
              </TouchableOpacity>
            )}
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  header: { padding: 16, backgroundColor: 'white', borderBottomWidth: 1, borderBottomColor: '#e2e8f0' },
  headerTitle: { fontSize: 18, fontWeight: 'bold', color: '#1e293b' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  loadingText: { fontSize: 16, fontWeight: '600', color: '#1e293b', marginTop: 16 },
  errorText: { fontSize: 16, color: '#ef4444', textAlign: 'center', marginBottom: 20 },
  button: { backgroundColor: '#2563eb', padding: 12, borderRadius: 8 },
  buttonText: { color: '#ffffff', fontWeight: 'bold' },
  list: { padding: 16 },
  empty: { padding: 32, alignItems: 'center' },
  emptyText: { fontSize: 15, color: '#94a3b8' },
  card: { backgroundColor: '#ffffff', padding: 16, borderRadius: 10, marginBottom: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#f1f5f9', paddingBottom: 8, marginBottom: 8 },
  docNo: { fontSize: 16, fontWeight: 'bold', color: '#1e293b' },
  docType: { fontSize: 14, color: '#2563eb', fontWeight: '600' },
  cardBody: {},
  bodyText: { fontSize: 13, color: '#475569', marginBottom: 4 },
  bold: { fontWeight: 'bold' },
  indexLink: { marginTop: 8, alignSelf: 'flex-start', paddingVertical: 4, paddingHorizontal: 8, backgroundColor: '#eff6ff', borderRadius: 4, borderWidth: 1, borderColor: '#bfdbfe' },
  indexLinkText: { color: '#2563eb', fontSize: 12, fontWeight: '600' }
});
