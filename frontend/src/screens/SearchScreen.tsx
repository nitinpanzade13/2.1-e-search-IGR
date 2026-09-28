import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, TextInput, TouchableOpacity, SafeAreaView, ScrollView,
  ActivityIndicator, Modal, FlatList 
} from 'react-native';
import { useNavigation } from '@react-navigation/native';

import { District, Taluka, Village } from '../types/api';
import * as locationApi from '../api/locations';
import * as searchApi from '../api/search';

export default function SearchScreen() {
  const navigation = useNavigation<any>();
  
  const [districts, setDistricts] = useState<District[]>([]);
  const [talukas, setTalukas] = useState<Taluka[]>([]);
  const [villages, setVillages] = useState<Village[]>([]);

  const [selectedDistrict, setSelectedDistrict] = useState<District | null>(null);
  const [selectedTaluka, setSelectedTaluka] = useState<Taluka | null>(null);
  const [selectedVillage, setSelectedVillage] = useState<Village | null>(null);
  
  const [year, setYear] = useState<string>('');
  const [surveyQuery, setSurveyQuery] = useState<string>('');

  const [loadingDistricts, setLoadingDistricts] = useState(true);
  const [loadingTalukas, setLoadingTalukas] = useState(false);
  const [loadingVillages, setLoadingVillages] = useState(false);
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDistricts();
  }, []);

  const loadDistricts = async () => {
    try {
      const data = await locationApi.getDistricts();
      setDistricts(data);
    } catch (err) {
      setError('Failed to load districts. Is the backend running?');
    } finally {
      setLoadingDistricts(false);
    }
  };

  const handleDistrictChange = async (district: District) => {
    setSelectedDistrict(district);
    setSelectedTaluka(null);
    setSelectedVillage(null);
    setTalukas([]);
    setVillages([]);
    
    setLoadingTalukas(true);
    try {
      const data = await locationApi.getTalukas(district.id);
      setTalukas(data);
    } catch (err) {
      setError('Failed to load talukas');
    } finally {
      setLoadingTalukas(false);
    }
  };

  const handleTalukaChange = async (taluka: Taluka) => {
    setSelectedTaluka(taluka);
    setSelectedVillage(null);
    setVillages([]);
    
    setLoadingVillages(true);
    try {
      const data = await locationApi.getVillages(taluka.id);
      setVillages(data);
    } catch (err) {
      setError('Failed to load villages');
    } finally {
      setLoadingVillages(false);
    }
  };

  const handleSearch = async () => {
    if (!selectedDistrict || !selectedTaluka || !selectedVillage || !year) {
      setError('Please fill all required fields');
      return;
    }
    
    navigation.navigate('SearchResults', {
      villageId: selectedVillage.id,
      year: parseInt(year, 10),
      docNo: surveyQuery.trim(),
      villageName: selectedVillage.name_en
    });
  };

  const Selector = ({ label, value, items, onSelect, disabled, loading }: any) => {
    const [modalVisible, setModalVisible] = useState(false);
    
    return (
      <View style={styles.inputGroup}>
        <Text style={styles.label}>{label}</Text>
        <TouchableOpacity 
          style={[styles.selector, disabled && styles.selectorDisabled]}
          onPress={() => !disabled && setModalVisible(true)}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#2563eb" />
          ) : (
            <Text style={[styles.selectorText, !value && styles.placeholderText]}>
              {value ? value.name_en : `Select ${label}`}
            </Text>
          )}
        </TouchableOpacity>

        <Modal visible={modalVisible} animationType="slide" transparent={true}>
          <View style={styles.modalContainer}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Select {label}</Text>
                <TouchableOpacity onPress={() => setModalVisible(false)}>
                  <Text style={styles.closeText}>Close</Text>
                </TouchableOpacity>
              </View>
              <FlatList
                data={items}
                keyExtractor={(item) => item.id}
                renderItem={({ item }) => (
                  <TouchableOpacity 
                    style={styles.modalItem}
                    onPress={() => {
                      onSelect(item);
                      setModalVisible(false);
                    }}
                  >
                    <Text style={styles.modalItemText}>{item.name_en}</Text>
                  </TouchableOpacity>
                )}
              />
            </View>
          </View>
        </Modal>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.headerTitle}>Search Criteria</Text>
        
        {error && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        <Selector 
          label="District" 
          value={selectedDistrict} 
          items={districts} 
          onSelect={handleDistrictChange} 
          loading={loadingDistricts}
        />

        <Selector 
          label="Taluka" 
          value={selectedTaluka} 
          items={talukas} 
          onSelect={handleTalukaChange} 
          disabled={!selectedDistrict}
          loading={loadingTalukas}
        />

        <Selector 
          label="Village" 
          value={selectedVillage} 
          items={villages} 
          onSelect={(v: Village) => setSelectedVillage(v)} 
          disabled={!selectedTaluka}
          loading={loadingVillages}
        />

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Year</Text>
          <TextInput 
            style={styles.input}
            value={year}
            onChangeText={setYear}
            keyboardType="numeric"
            placeholder="e.g. 2026"
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Survey Number (Optional)</Text>
          <TextInput 
            style={styles.input}
            value={surveyQuery}
            onChangeText={setSurveyQuery}
            placeholder="e.g. 1"
          />
        </View>

        <TouchableOpacity 
          style={[styles.searchButton, isSubmitting && styles.searchButtonDisabled]}
          onPress={handleSearch}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <Text style={styles.searchButtonText}>Search</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  scroll: { padding: 24 },
  headerTitle: { fontSize: 24, fontWeight: 'bold', color: '#1e293b', marginBottom: 24 },
  errorBox: { backgroundColor: '#fef2f2', padding: 12, borderRadius: 8, marginBottom: 16, borderWidth: 1, borderColor: '#f87171' },
  errorText: { color: '#ef4444' },
  inputGroup: { marginBottom: 20 },
  label: { fontSize: 14, fontWeight: '600', color: '#475569', marginBottom: 8 },
  selector: { backgroundColor: '#ffffff', borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 8, padding: 16 },
  selectorDisabled: { backgroundColor: '#f1f5f9' },
  selectorText: { fontSize: 16, color: '#1e293b' },
  placeholderText: { color: '#94a3b8' },
  input: { backgroundColor: '#ffffff', borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 8, padding: 16, fontSize: 16, color: '#1e293b' },
  searchButton: { backgroundColor: '#2563eb', padding: 18, borderRadius: 12, alignItems: 'center', marginTop: 12 },
  searchButtonDisabled: { opacity: 0.7 },
  searchButtonText: { color: '#ffffff', fontSize: 18, fontWeight: 'bold' },
  
  // Modal styles
  modalContainer: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.5)' },
  modalContent: { backgroundColor: '#ffffff', borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '70%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: '#e2e8f0' },
  modalTitle: { fontSize: 18, fontWeight: 'bold' },
  closeText: { color: '#2563eb', fontSize: 16 },
  modalItem: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#f1f5f9' },
  modalItemText: { fontSize: 16, color: '#1e293b' }
});
