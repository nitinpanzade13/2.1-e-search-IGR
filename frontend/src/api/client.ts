import axios from 'axios';

// Ensure EXPO_PUBLIC_API_URL is provided by environment
const BASE_URL = process.env.EXPO_PUBLIC_API_URL;

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add interceptors for unified error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    let errorMessage = "An unknown error occurred.";
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      const status = error.response.status;
      const data = error.response.data;
      
      if (status === 400) errorMessage = `Bad Request: ${data.detail || data.message || "Invalid input"}`;
      else if (status === 404) errorMessage = `Not Found: ${data.detail || data.message || "Resource not found"}`;
      else if (status === 422) errorMessage = `Validation Error: ${data.detail || data.message || "Unprocessable entity"}`;
      else if (status === 429) errorMessage = `Rate Limited: ${data.detail || data.message || "Too many requests"}`;
      else if (status === 500) errorMessage = `Server Error: ${data.detail || data.message || "Internal server error"}`;
      else errorMessage = `Error ${status}: ${data.detail || data.message || "Something went wrong"}`;
    } else if (error.request) {
      // The request was made but no response was received
      errorMessage = "Network Error: Unable to reach the server. Please check your connection.";
    } else {
      // Something happened in setting up the request that triggered an Error
      errorMessage = error.message;
    }
    
    return Promise.reject(new Error(errorMessage));
  }
);
