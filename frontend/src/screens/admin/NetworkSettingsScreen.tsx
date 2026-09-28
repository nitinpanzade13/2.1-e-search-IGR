import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, TextInput, Switch, Alert, ScrollView } from 'react-native';
import * as networkApi from '../../api/network';
import { NetworkConfig, NetworkConfigCreate } from '../../api/network';

export const NetworkSettingsScreen = () => {
  const [configs, setConfigs] = useState<NetworkConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  
  const [formData, setFormData] = useState<NetworkConfigCreate>({
    profile_name: '',
    interface_name: 'Wi-Fi',
    priority: 10,
    is_enabled: true,
    connection_timeout: 30,
    validation_timeout: 10,
  });

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const data = await networkApi.getNetworkConfigs();
      setConfigs(data);
    } catch (e) {
      console.error(e);
      Alert.alert('Error', 'Failed to load network configurations');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!formData.profile_name.trim()) {
      Alert.alert('Validation Error', 'Profile name is required');
      return;
    }
    
    setLoading(true);
    try {
      if (editingId) {
        await networkApi.updateNetworkConfig(editingId, formData);
      } else {
        await networkApi.createNetworkConfig(formData);
      }
      setEditingId(null);
      setFormData({
        profile_name: '',
        interface_name: 'Wi-Fi',
        priority: 10,
        is_enabled: true,
        connection_timeout: 30,
        validation_timeout: 10,
      });
      await loadConfigs();
    } catch (e: any) {
      console.error(e);
      Alert.alert('Error', e?.message || 'Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (item: NetworkConfig) => {
    setEditingId(item.id);
    setFormData({
      profile_name: item.profile_name,
      interface_name: item.interface_name,
      priority: item.priority,
      is_enabled: item.is_enabled,
      connection_timeout: item.connection_timeout,
      validation_timeout: item.validation_timeout,
    });
  };

  const handleDelete = async (id: string) => {
    try {
      await networkApi.deleteNetworkConfig(id);
      await loadConfigs();
    } catch (e) {
      console.error(e);
      Alert.alert('Error', 'Failed to delete configuration');
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.header}>Admin Network Settings</Text>
      <Text style={styles.subtitle}>Configure approved Windows OS-managed Wi-Fi profiles for legitimate failover. No passwords required here; Windows manages the authentication.</Text>

      <View style={styles.formContainer}>
        <Text style={styles.formTitle}>{editingId ? 'Edit Configuration' : 'Add New Configuration'}</Text>
        
        <View style={styles.inputGroup}>
          <Text style={styles.label}>OS Wi-Fi Profile Name (Required)</Text>
          <TextInput
            style={styles.input}
            value={formData.profile_name}
            onChangeText={(text) => setFormData({...formData, profile_name: text})}
            placeholder="e.g. Office-WiFi"
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Interface Name</Text>
          <TextInput
            style={styles.input}
            value={formData.interface_name}
            onChangeText={(text) => setFormData({...formData, interface_name: text})}
            placeholder="e.g. Wi-Fi"
          />
        </View>

        <View style={styles.row}>
          <View style={[styles.inputGroup, { flex: 1, marginRight: 10 }]}>
            <Text style={styles.label}>Priority (Lower = Higher Prio)</Text>
            <TextInput
              style={styles.input}
              value={String(formData.priority)}
              onChangeText={(text) => setFormData({...formData, priority: parseInt(text) || 0})}
              keyboardType="numeric"
            />
          </View>

          <View style={[styles.inputGroup, { flex: 1, alignItems: 'center', justifyContent: 'center' }]}>
            <Text style={styles.label}>Enabled</Text>
            {/* React Native Switch doesn't exist out of the box in basic text, using a toggle button fallback if Switch errors, but Switch is standard */}
            <TouchableOpacity 
              style={[styles.toggleBtn, formData.is_enabled ? styles.toggleOn : styles.toggleOff]}
              onPress={() => setFormData({...formData, is_enabled: !formData.is_enabled})}
            >
              <Text style={styles.toggleText}>{formData.is_enabled ? 'ON' : 'OFF'}</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.row}>
          <View style={[styles.inputGroup, { flex: 1, marginRight: 10 }]}>
            <Text style={styles.label}>Connection Timeout (s)</Text>
            <TextInput
              style={styles.input}
              value={String(formData.connection_timeout)}
              onChangeText={(text) => setFormData({...formData, connection_timeout: parseInt(text) || 30})}
              keyboardType="numeric"
            />
          </View>

          <View style={[styles.inputGroup, { flex: 1 }]}>
            <Text style={styles.label}>Validation Timeout (s)</Text>
            <TextInput
              style={styles.input}
              value={String(formData.validation_timeout)}
              onChangeText={(text) => setFormData({...formData, validation_timeout: parseInt(text) || 10})}
              keyboardType="numeric"
            />
          </View>
        </View>

        <View style={styles.row}>
          <TouchableOpacity style={styles.saveBtn} onPress={handleSave} disabled={loading}>
            <Text style={styles.btnText}>{loading ? 'Saving...' : 'Save Configuration'}</Text>
          </TouchableOpacity>
          
          {editingId && (
            <TouchableOpacity 
              style={styles.cancelBtn} 
              onPress={() => {
                setEditingId(null);
                setFormData({
                  profile_name: '', interface_name: 'Wi-Fi', priority: 10, is_enabled: true, connection_timeout: 30, validation_timeout: 10
                });
              }}
            >
              <Text style={styles.btnText}>Cancel Edit</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      <Text style={styles.listHeader}>Configured Networks</Text>
      {configs.length === 0 ? (
        <Text style={styles.emptyText}>No network configurations found.</Text>
      ) : (
        configs.map(item => (
          <View key={item.id} style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>{item.profile_name}</Text>
              <View style={[styles.badge, item.is_enabled ? styles.badgeOn : styles.badgeOff]}>
                <Text style={styles.badgeText}>{item.is_enabled ? 'ENABLED' : 'DISABLED'}</Text>
              </View>
            </View>
            <Text style={styles.cardDetail}>Interface: {item.interface_name} | Priority: {item.priority}</Text>
            
            <View style={styles.cardActions}>
              <TouchableOpacity style={styles.editBtn} onPress={() => handleEdit(item)}>
                <Text style={styles.btnText}>Edit</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.deleteBtn} onPress={() => handleDelete(item.id)}>
                <Text style={styles.btnText}>Delete</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))
      )}
    </ScrollView>
  );
};

// Generic React Native styles
const styles: any = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#f5f5f5',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#666',
    marginBottom: 20,
  },
  formContainer: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 8,
    marginBottom: 30,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  formTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 15,
  },
  inputGroup: {
    marginBottom: 15,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 5,
    color: '#333',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 4,
    padding: 10,
    fontSize: 14,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 15,
  },
  toggleBtn: {
    paddingVertical: 8,
    paddingHorizontal: 20,
    borderRadius: 4,
  },
  toggleOn: {
    backgroundColor: '#4CAF50',
  },
  toggleOff: {
    backgroundColor: '#f44336',
  },
  toggleText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  saveBtn: {
    backgroundColor: '#2196F3',
    padding: 12,
    borderRadius: 4,
    flex: 1,
    alignItems: 'center',
  },
  cancelBtn: {
    backgroundColor: '#9e9e9e',
    padding: 12,
    borderRadius: 4,
    flex: 1,
    alignItems: 'center',
    marginLeft: 10,
  },
  btnText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  listHeader: {
    fontSize: 20,
    fontWeight: '600',
    marginBottom: 15,
  },
  emptyText: {
    fontStyle: 'italic',
    color: '#888',
  },
  card: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
    borderLeftWidth: 4,
    borderLeftColor: '#2196F3',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 5,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeOn: {
    backgroundColor: '#e8f5e9',
  },
  badgeOff: {
    backgroundColor: '#ffebee',
  },
  badgeText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#333',
  },
  cardDetail: {
    fontSize: 12,
    color: '#666',
    marginBottom: 10,
  },
  cardActions: {
    flexDirection: 'row',
  },
  editBtn: {
    backgroundColor: '#ff9800',
    padding: 8,
    borderRadius: 4,
    marginRight: 10,
  },
  deleteBtn: {
    backgroundColor: '#f44336',
    padding: 8,
    borderRadius: 4,
  },
});
