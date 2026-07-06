import axios, { AxiosResponse } from 'axios';
import type { ApiResponse } from '../types';

/**
 * Centralized Axios instance.
 * baseURL is proxied to http://localhost:8000/api/v1 via Vite config.
 * Response interceptor unwraps { code, data, message } envelope.
 */
const client = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor: unwrap unified envelope { code, data, message }
client.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const body = response.data;
    if (body && typeof body.code !== 'undefined') {
      if (body.code !== 0) {
        const errorMsg = body.message || `API error (code ${body.code})`;
        console.error('[API Error]', body.code, errorMsg);
        return Promise.reject(new Error(errorMsg));
      }
      // Return unwrapped data so callers receive the payload directly
      return { ...response, data: body.data };
    }
    // Non-standard response (e.g. blob), return as-is
    return response;
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      const message = (data && (data.message || data.detail)) || error.message;
      console.error('[HTTP Error]', status, message);
      return Promise.reject(new Error(message));
    }
    console.error('[Network Error]', error.message);
    return Promise.reject(new Error('网络连接失败，请检查后端服务是否启动'));
  }
);

export default client;
