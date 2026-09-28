import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert, ActivityIndicator, TextInput } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { villageFetchApi } from '../../api/village_fetch';
import * as locationsApi from '../../api/locations';
import { useNavigation } from '@react-navigation/native';
import { District, Taluka, Village, VillageFetchCreateRequest } from '../../types/api';

export default function BulkCreateScreen() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState<number>(currentYear);
  const [surveyRangeStart, setSurveyRangeStart] = useState<string>('1');
  const [surveyRangeEnd, setSurveyRangeEnd] = useState<string>('100');
  const [useRange, setUseRange] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('1');
  
  const [districts, setDistricts] = useState<District[]>([]);
  const [talukas, setTalukas] = useState<Taluka[]>([]);
  const [villages, setVillages] = useState<Village[]>([]);
  
  const [districtId, setDistrictId] = useState('');
  const [talukaId, setTalukaId] = useState('');
  const [villageId, setVillageId] = useState('');
  
  const [loadingDistricts, setLoadingDistricts] = useState(true);
  const [loadingTalukas, setLoadingTalukas] = useState(false);
  const [loadingVillages, setLoadingVillages] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const navigation = useNavigation<any>();

  useEffect(() => {
    setLoadingDistricts(true);
    locationsApi.getDistricts()
      .then(setDistricts)
      .catch((err: Error) => {
        Alert.alert("Error loading districts", err.message);
      })
      .finally(() => setLoadingDistricts(false));
  }, []);

  useEffect(() => {
    setTalukaId('');
    setTalukas([]);
    setVillageId('');
    setVillages([]);
    if (districtId) {
      setLoadingTalukas(true);
      locationsApi.getTalukas(districtId)
        .then(setTalukas)
        .catch(console.error)
        .finally(() => setLoadingTalukas(false));
    }
  }, [districtId]);

  useEffect(() => {
    setVillageId('');
    setVillages([]);
    if (talukaId) {
      setLoadingVillages(true);
      locationsApi.getVillages(talukaId)
        .then(setVillages)
        .catch(console.error)
        .finally(() => setLoadingVillages(false));
    }
  }, [talukaId]);

  const handleSubmit = async () => {
    if (!districtId) {
      Alert.alert('Validation Error', 'Please select a District.');
      return;
    }
    if (!talukaId) {
      Alert.alert('Validation Error', 'Please select a Taluka.');
      return;
    }
    if (!villageId) {
      Alert.alert('Validation Error', 'Please select a Village. (Village is the only fetching unit)');
      return;
    }

    // Validate survey range
    const start = parseInt(surveyRangeStart);
    const end = parseInt(surveyRangeEnd);
    
    if (isNaN(start) || isNaN(end)) {
      Alert.alert('Validation Error', 'Please enter valid numbers for survey range.');
      return;
    }
    
    if (start < 1) {
      Alert.alert('Validation Error', 'Survey range start must be at least 1.');
      return;
    }
    
    if (end < start) {
      Alert.alert('Validation Error', 'Survey range end must be greater than or equal to start.');
      return;
    }
    
    if (end - start > 1000) {
      Alert.alert('Warning', `You are fetching ${end - start + 1} surveys. This may take a long time and hit rate limits. Consider smaller ranges.`);
      // Continue anyway, just warning
    }

    try {
      setSubmitting(true);
      const payload: VillageFetchCreateRequest = {
        district_id: districtId,
        taluka_id: talukaId,
        village_id: villageId,
        year: year,
        survey_range_start: start,
        survey_range_end: end,
        search_query: useRange ? undefined : searchQuery.trim() || undefined
      };

      const response = await villageFetchApi.createVillageFetch(payload);
      navigation.navigate('BulkDetail', { jobId: response.id });
    } catch (e: unknown) {
      if (e instanceof Error) {
        Alert.alert('Error', e.message);
      } else {
        Alert.alert('Error', 'An unknown error occurred');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const years = Array.from({ length: currentYear - 1984 }, (_, i) => currentYear - i);

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>New Village Record Fetch</Text>
      <Text style={styles.subtitle}>
        Fetch records for a single village from IGR. District and Taluka serve as hierarchy filters.
      </Text>
      
      {/* 1. District Selection */}
      <Text style={styles.label}>District *</Text>
      <View style={styles.pickerContainer}>
        {loadingDistricts ? (
          <ActivityIndicator style={{ padding: 12 }} color="#2563eb" />
        ) : (
          <Picker selectedValue={districtId} onValueChange={setDistrictId}>
            <Picker.Item label="Select District..." value="" />
            {districts.map(d => (
              <Picker.Item key={d.id} label={d.name_en} value={d.id} />
            ))}
          </Picker>
        )}
      </View>

      {/* 2. Taluka Selection */}
      <Text style={styles.label}>Taluka *</Text>
      <View style={[styles.pickerContainer, (!districtId || loadingTalukas) && styles.disabledPicker]}>
        {loadingTalukas ? (
          <ActivityIndicator style={{ padding: 12 }} color="#2563eb" />
        ) : (
          <Picker 
            selectedValue={talukaId} 
            onValueChange={setTalukaId} 
            enabled={!!districtId && talukas.length > 0}
          >
            <Picker.Item label={districtId ? "Select Taluka..." : "Select District first"} value="" />
            {talukas.map(t => (
              <Picker.Item key={t.id} label={t.name_en} value={t.id} />
            ))}
          </Picker>
        )}
      </View>

      {/* 3. Village Selection (The Fetch Unit) */}
      <Text style={styles.label}>Village (Fetching Unit) *</Text>
      <View style={[styles.pickerContainer, (!talukaId || loadingVillages) && styles.disabledPicker]}>
        {loadingVillages ? (
          <ActivityIndicator style={{ padding: 12 }} color="#2563eb" />
        ) : (
          <Picker 
            selectedValue={villageId} 
            onValueChange={setVillageId} 
            enabled={!!talukaId && villages.length > 0}
          >
            <Picker.Item label={talukaId ? "Select Village..." : "Select Taluka first"} value="" />
            {villages.map(v => (
              <Picker.Item key={v.id} label={v.name_en} value={v.id} />
            ))}
          </Picker>
        )}
      </View>

      {/* 4. Year Selection */}
      <Text style={styles.label}>Registration Year *</Text>
      <View style={styles.pickerContainer}>
        <Picker selectedValue={year} onValueChange={(val) => setYear(Number(val))}>
          {years.map(y => (
            <Picker.Item key={y} label={y.toString()} value={y} />
          ))}
        </Picker>
      </View>

      {/* 5. Survey Range Selection */}
      <Text style={styles.label}>Survey Range *</Text>
      <View style={styles.rangeContainer}>
        <View style={styles.rangeInputContainer}>
          <Text style={styles.rangeLabel}>From</Text>
          <TextInput
            style={styles.rangeInput}
            value={surveyRangeStart}
            onChangeText={setSurveyRangeStart}
            placeholder="1"
            keyboardType="numeric"
            autoCapitalize="none"
          />
        </View>
        <View style={styles.rangeInputContainer}>
          <Text style={styles.rangeLabel}>To</Text>
          <TextInput
            style={styles.rangeInput}
            value={surveyRangeEnd}
            onChangeText={setSurveyRangeEnd}
            placeholder="100"
            keyboardType="numeric"
            autoCapitalize="none"
          />
        </View>
      </View>
      <Text style={styles.helpText}>
        Enter survey number range (e.g., 1-100). The system will automatically fetch all surveys in this range.
        {parseInt(surveyRangeEnd) - parseInt(surveyRangeStart) + 1 > 100 && 
          ` ⚠️ Large range: ${parseInt(surveyRangeEnd) - parseInt(surveyRangeStart) + 1} surveys`}
      </Text>

      {/* 6. Toggle for single survey (optional) */}
      <TouchableOpacity 
        style={styles.toggleContainer} 
        onPress={() => setUseRange(!useRange)}
      >
        <View style={[styles.toggleButton, useRange && styles.toggleButtonActive]}>
          <Text style={[styles.toggleText, useRange && styles.toggleTextActive]}>
            {useRange ? '✓' : ''}
          </Text>
        </View>
        <Text style={styles.toggleLabel}>Use survey range (recommended)</Text>
      </TouchableOpacity>

      {!useRange && (
        <>
          <Text style={styles.label}>Single Survey Number (Optional)</Text>
          <TextInput
            style={styles.input}
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Enter single survey number"
            keyboardType="numeric"
            autoCapitalize="none"
          />
          <Text style={styles.helpText}>Enter a single survey number if you don't want to use range.</Text>
        </>
      )}

      {/* 7. Optional Note */}
      <View style={styles.noteBox}>
        <Text style={styles.noteText}>
          ℹ️ Survey Range: Automatically fetches all surveys from start to end.{'\n'}
          ℹ️ Network Switching: System will automatically switch WiFi networks when rate limits hit.{'\n'}
          ℹ️ Article Name and Party Name are optional and omitted per project requirements.
        </Text>
      </View>

      <TouchableOpacity 
        style={[styles.submitBtn, submitting && styles.submitBtnDisabled]} 
        onPress={handleSubmit}
        disabled={submitting || !villageId}
      >
        {submitting ? (
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <ActivityIndicator color="white" style={{ marginRight: 10 }} />
            <Text style={styles.submitBtnText}>Starting Fetch...</Text>
          </View>
        ) : (
          <Text style={styles.submitBtnText}>Start Village Fetch</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: '#f8fafc' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#1e293b', marginBottom: 4 },
  subtitle: { fontSize: 13, color: '#64748b', marginBottom: 20 },
  label: { fontSize: 15, fontWeight: '600', color: '#334155', marginBottom: 6 },
  pickerContainer: { backgroundColor: 'white', borderRadius: 8, marginBottom: 16, borderWidth: 1, borderColor: '#cbd5e1' },
  disabledPicker: { backgroundColor: '#f1f5f9', opacity: 0.6 },
  input: { backgroundColor: 'white', borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 8, padding: 12, fontSize: 16, color: '#1e293b', marginBottom: 6 },
  helpText: { fontSize: 12, color: '#64748b', marginBottom: 16 },
  noteBox: { backgroundColor: '#eff6ff', padding: 12, borderRadius: 8, borderWidth: 1, borderColor: '#bfdbfe', marginBottom: 20 },
  noteText: { fontSize: 13, color: '#1e40af' },
  rangeContainer: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  rangeInputContainer: { flex: 1, marginRight: 10 },
  rangeLabel: { fontSize: 13, color: '#64748b', marginBottom: 4 },
  rangeInput: { backgroundColor: 'white', borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 8, padding: 12, fontSize: 16, color: '#1e293b' },
  toggleContainer: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  toggleButton: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: '#cbd5e1', marginRight: 10, alignItems: 'center', justifyContent: 'center' },
  toggleButtonActive: { backgroundColor: '#2563eb', borderColor: '#2563eb' },
  toggleText: { color: 'transparent', fontSize: 14, fontWeight: 'bold' },
  toggleTextActive: { color: 'white' },
  toggleLabel: { fontSize: 14, color: '#475569' },
  submitBtn: { backgroundColor: '#2563eb', padding: 16, borderRadius: 8, alignItems: 'center', marginTop: 10, marginBottom: 40 },
  submitBtnDisabled: { backgroundColor: '#94a3b8' },
  submitBtnText: { color: 'white', fontWeight: 'bold', fontSize: 16 },
});
