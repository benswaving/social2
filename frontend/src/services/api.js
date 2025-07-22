// API service for communicating with the backend
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3088/api';

class ApiService {
  constructor() {
    this.token = localStorage.getItem('access_token');
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('access_token', token);
    } else {
      localStorage.removeItem('access_token');
    }
  }

  getHeaders() {
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      headers: this.getHeaders(),
      ...options,
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }

      return data;
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Authentication methods
  async register(userData) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async login(credentials) {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  }

  async logout() {
    try {
      await this.request('/auth/logout', { method: 'POST' });
    } finally {
      this.setToken(null);
    }
  }

  // Content generation methods
  async generateContent(contentData) {
    console.log('Frontend sending data to backend:', contentData);
    console.log('JSON stringified:', JSON.stringify(contentData));
    return this.request('/content/generate', {
      method: 'POST',
      body: JSON.stringify(contentData),
    });
  }

  async getContentProject(projectId) {
    return this.request(`/content/projects/${projectId}`);
  }

  async getContentProjects() {
    return this.request('/content/projects');
  }

  async getGeneratedContent(projectId) {
    return this.request(`/content/projects/${projectId}/content`);
  }

  // AI analysis methods
  async analyzeContent(contentData) {
    return this.request('/ai/analyze-content', {
      method: 'POST',
      body: JSON.stringify(contentData),
    });
  }

  async generateHashtags(contentData) {
    return this.request('/ai/generate-hashtags', {
      method: 'POST',
      body: JSON.stringify(contentData),
    });
  }

  async generateImagePrompt(contentData) {
    return this.request('/ai/generate-image-prompt', {
      method: 'POST',
      body: JSON.stringify(contentData),
    });
  }

  async checkTone(contentData) {
    return this.request('/ai/tone-check', {
      method: 'POST',
      body: JSON.stringify(contentData),
    });
  }

  // Social media methods
  async getSocialAccounts() {
    return this.request('/social-accounts');
  }

  async connectSocialAccount(accountData) {
    return this.request('/social-accounts', {
      method: 'POST',
      body: JSON.stringify(accountData),
    });
  }

  async disconnectSocialAccount(accountId) {
    return this.request(`/social-accounts/${accountId}`, {
      method: 'DELETE',
    });
  }

  async publishToAccount(accountId, contentData) {
    return this.request(`/social-accounts/${accountId}/publish`, {
      method: 'POST',
      body: JSON.stringify(contentData),
    });
  }

  async schedulePost(accountId, contentData) {
    return this.request(`/social-accounts/${accountId}/schedule`, {
      method: 'POST',
      body: JSON.stringify(contentData),
    });
  }

  async getScheduledPosts(platform = null) {
    const query = platform ? `?platform=${platform}` : '';
    return this.request(`/scheduled-posts${query}`);
  }

  async cancelScheduledPost(postId) {
    return this.request(`/scheduled-posts/${postId}`, {
      method: 'DELETE',
    });
  }

  async getSupportedPlatforms() {
    return this.request('/platforms');
  }

  // Platform configurations
  async getPlatformConfigs() {
    return this.request('/content/platforms');
  }
}

// Create and export a singleton instance
const apiService = new ApiService();
export default apiService;

