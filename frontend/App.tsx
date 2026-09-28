import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import HomeScreen from './src/screens/HomeScreen';
import SearchScreen from './src/screens/SearchScreen';
import SearchResultsScreen from './src/screens/SearchResultsScreen';
import RegistrationDetailsScreen from './src/screens/RegistrationDetailsScreen';
import BulkDashboardScreen from './src/screens/admin/BulkDashboardScreen';
import BulkCreateScreen from './src/screens/admin/BulkCreateScreen';
import BulkDetailScreen from './src/screens/admin/BulkDetailScreen';
import { NetworkSettingsScreen } from './src/screens/admin/NetworkSettingsScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator 
        initialRouteName="Home"
        screenOptions={{
          headerStyle: { backgroundColor: '#2563eb' },
          headerTintColor: '#fff',
          headerTitleStyle: { fontWeight: 'bold' },
        }}
      >
        <Stack.Screen name="Home" component={HomeScreen} options={{ title: 'IGR e-Search' }} />
        <Stack.Screen name="Search" component={SearchScreen} options={{ title: 'Search Criteria' }} />
        <Stack.Screen name="SearchResults" component={SearchResultsScreen} options={{ title: 'Search Results' }} />
        <Stack.Screen name="RegistrationDetails" component={RegistrationDetailsScreen} options={{ title: 'Document Details' }} />
        <Stack.Screen name="BulkDashboard" component={BulkDashboardScreen} options={{ title: 'Admin Dashboard' }} />
        <Stack.Screen name="BulkCreate" component={BulkCreateScreen} options={{ title: 'Create Bulk Fetch' }} />
        <Stack.Screen name="BulkDetail" component={BulkDetailScreen} options={{ title: 'Bulk Fetch Details' }} />
        <Stack.Screen name="NetworkSettings" component={NetworkSettingsScreen} options={{ title: 'Network Config' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
