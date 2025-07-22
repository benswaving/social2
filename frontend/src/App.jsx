import React, { useState, useEffect } from 'react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Textarea } from './components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Alert, AlertDescription } from './components/ui/alert';
import { Loader2, Sparkles, User, Search, BarChart3, Settings, FileText, Image, Video, Lightbulb, Instagram, Linkedin, Twitter, Facebook } from 'lucide-react';
import apiService from './services/api';
import './App.css';

const PLATFORM_ICONS = {
  instagram: Instagram,
  linkedin: Linkedin,
  twitter: Twitter,
  facebook: Facebook,
  tiktok: Video
};

const PLATFORM_COLORS = {
  instagram: 'from-purple-600 to-pink-600',
  linkedin: 'from-blue-600 to-blue-700',
  twitter: 'from-sky-400 to-blue-500',
  facebook: 'from-blue-600 to-indigo-600',
  tiktok: 'from-red-500 to-pink-500'
};

function App() {
  // State management
  const [currentView, setCurrentView] = useState('generate');
  const [topic, setTopic] = useState('');
  const [tone, setTone] = useState('');
  const [selectedFormats, setSelectedFormats] = useState(['text', 'image']);
  const [selectedPlatforms, setSelectedPlatforms] = useState(['instagram']);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedContent, setGeneratedContent] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [platforms, setPlatforms] = useState({});
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState(null);

  // Check authentication status on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      setIsLoggedIn(true);
      // In a real app, you'd validate the token and get user info
    }
    
    // Load platform configurations
    loadPlatforms();
  }, []);

  const loadPlatforms = async () => {
    try {
      const response = await apiService.getSupportedPlatforms();
      setPlatforms(response.platforms);
    } catch (error) {
      console.error('Failed to load platforms:', error);
    }
  };

  const handleLogin = async () => {
    try {
      // For demo purposes, create a test user
      const response = await apiService.register({
        email: `user${Date.now()}@example.com`,
        password: 'TestPass123',
        first_name: 'Demo',
        last_name: 'User'
      });
      
      apiService.setToken(response.access_token);
      setIsLoggedIn(true);
      setUser(response.user_profile);
      setSuccess('Successfully logged in!');
    } catch (error) {
      setError('Login failed: ' + error.message);
    }
  };

  const handleDemoLogin = async () => {
    try {
      // For demo purposes, create a test user
      const response = await apiService.register({
        email: `user${Date.now()}@example.com`,
        password: 'TestPass123',
        first_name: 'Demo',
        last_name: 'User'
      });
      
      apiService.setToken(response.access_token);
      setIsLoggedIn(true);
      setUser(response.user_profile);
      return response;
    } catch (error) {
      console.error('Demo login failed:', error);
      throw error;
    }
  };

  const handleLogout = () => {
    apiService.setToken(null);
    setIsLoggedIn(false);
    setUser(null);
    setGeneratedContent(null);
  };

  const handleFormatToggle = (format) => {
    setSelectedFormats(prev => 
      prev.includes(format) 
        ? prev.filter(f => f !== format)
        : [...prev, format]
    );
  };

  const handlePlatformToggle = (platform) => {
    setSelectedPlatforms(prev => 
      prev.includes(platform) 
        ? prev.filter(p => p !== platform)
        : [...prev, platform]
    );
  };

  const handleGenerate = async () => {
    if (!topic.trim()) {
      setError('Please enter a topic');
      return;
    }

    if (selectedPlatforms.length === 0) {
      setError('Please select at least one platform');
      return;
    }

    // Auto-login if not logged in or token expired
    if (!isLoggedIn) {
      try {
        await handleDemoLogin();
      } catch (loginError) {
        setError('Failed to authenticate. Please try again.');
        return;
      }
    }

    // Frontend validation
    if (!topic || topic.trim().length < 10) {
      setError('Please enter a topic/prompt of at least 10 characters');
      return;
    }
    
    if (!selectedPlatforms || selectedPlatforms.length === 0) {
      setError('Please select at least one platform');
      return;
    }

    setIsGenerating(true);
    setError('');
    setSuccess('');

    try {
      const response = await apiService.generateContent({
        prompt: topic.trim(),
        platforms: selectedPlatforms,
        content_types: selectedFormats,
        tone: tone || undefined,
        title: `Content voor ${selectedPlatforms.join(', ')}`
      });

      setSuccess('Content generation started! Project ID: ' + response.project_id);
      
      // Poll for results with multiple attempts - content-type aware
      const getMaxAttempts = (contentTypes) => {
        if (contentTypes.includes('video')) return 40; // 2 minutes for video
        if (contentTypes.includes('image')) return 20; // 1 minute for images
        return 10; // 30 seconds for text only
      };
      
      const maxAttempts = getMaxAttempts(selectedFormats);
      const pollForContent = async (projectId, attempt = 1, maxAttemptsOverride = maxAttempts) => {
        try {
          console.log(`Polling attempt ${attempt}/${maxAttemptsOverride} for project ${projectId}`);
          const contentResponse = await apiService.getGeneratedContent(projectId);
          
          if (contentResponse && contentResponse.length > 0) {
            console.log('Content found!', contentResponse);
            setGeneratedContent(contentResponse);
            setSuccess('Content generated successfully!');
          } else if (attempt < maxAttemptsOverride) {
            console.log('No content yet, trying again in 3 seconds...');
            setTimeout(() => pollForContent(projectId, attempt + 1, maxAttemptsOverride), 3000);
          } else {
            console.log('Max polling attempts reached, no content found');
            setError('Content generation took too long. Please refresh and try again.');
          }
        } catch (error) {
          console.error('Failed to fetch generated content:', error);
          if (attempt < maxAttemptsOverride) {
            setTimeout(() => pollForContent(projectId, attempt + 1, maxAttemptsOverride), 3000);
          } else {
            setError('Failed to retrieve generated content.');
          }
        }
      };
      
      // Start polling after 2 seconds
      setTimeout(() => pollForContent(response.project_id), 2000);

    } catch (error) {
      console.error('Content generation error:', error);
      
      // Handle token expiry
      if (error.message.includes('Token has expired') || error.message.includes('401')) {
        try {
          await handleDemoLogin();
          // Retry the request
          const response = await apiService.generateContent({
            prompt: topic,
            platforms: selectedPlatforms,
            content_types: selectedFormats,
            tone: tone || undefined,
            title: `Content voor ${selectedPlatforms.join(', ')}`
          });
          
          setSuccess('Content generation started! Project ID: ' + response.project_id);
          
          // Poll for results with multiple attempts (retry case) - content-type aware
          const maxAttemptsRetry = getMaxAttempts(selectedFormats);
          const pollForContentRetry = async (projectId, attempt = 1, maxAttemptsOverride = maxAttemptsRetry) => {
            try {
              console.log(`Retry polling attempt ${attempt}/${maxAttemptsOverride} for project ${projectId}`);
              const contentResponse = await apiService.getGeneratedContent(projectId);
              
              if (contentResponse && contentResponse.length > 0) {
                console.log('Content found on retry!', contentResponse);
                setGeneratedContent(contentResponse);
                setSuccess('Content generated successfully!');
              } else if (attempt < maxAttemptsOverride) {
                console.log('No content yet on retry, trying again in 3 seconds...');
                setTimeout(() => pollForContentRetry(projectId, attempt + 1, maxAttemptsOverride), 3000);
              } else {
                console.log('Max retry polling attempts reached, no content found');
                setError('Content generation took too long. Please refresh and try again.');
              }
            } catch (error) {
              console.error('Failed to fetch generated content on retry:', error);
              if (attempt < maxAttemptsOverride) {
                setTimeout(() => pollForContentRetry(projectId, attempt + 1, maxAttemptsOverride), 3000);
              } else {
                setError('Failed to retrieve generated content.');
              }
            }
          };
          
          // Start retry polling after 2 seconds
          setTimeout(() => pollForContentRetry(response.project_id), 2000);
          
        } catch (retryError) {
          setError('Authentication failed. Please refresh the page.');
        }
      } else {
        setError('Content generation failed: ' + error.message);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const formatOptions = [
    { id: 'text', label: 'Article', icon: FileText, color: 'bg-blue-500' },
    { id: 'image', label: 'Image', icon: Image, color: 'bg-purple-500' },
    { id: 'video', label: 'Video', icon: Video, color: 'bg-red-500' },
    { id: 'idea', label: 'Idea', icon: Lightbulb, color: 'bg-yellow-500' }
  ];

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-slate-800/50 border-slate-700">
          <CardHeader className="text-center">
            <div className="flex items-center justify-center gap-2 mb-4">
              <div className="w-10 h-10 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-white">Content Generator</h1>
            </div>
            <CardDescription className="text-slate-300">
              Log in to start generating AI-powered social media content
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button 
              onClick={handleLogin} 
              className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
            >
              Demo Login
            </Button>
            {error && (
              <Alert className="mt-4 border-red-500/50 bg-red-500/10">
                <AlertDescription className="text-red-400">{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-800/30 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-xl font-bold text-white">Content Generator</h1>
            </div>
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                className="text-slate-300 hover:text-white"
              >
                <User className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Navigation Tabs */}
        <Tabs value={currentView} onValueChange={setCurrentView} className="mb-8">
          <TabsList className="grid w-full grid-cols-4 bg-slate-800/50 border-slate-700">
            <TabsTrigger value="generate" className="data-[state=active]:bg-purple-600">
              <Sparkles className="w-4 h-4 mr-2" />
              Generate
            </TabsTrigger>
            <TabsTrigger value="schedule">
              <Settings className="w-4 h-4 mr-2" />
              Schedule
            </TabsTrigger>
            <TabsTrigger value="analytics">
              <BarChart3 className="w-4 h-4 mr-2" />
              Analytics
            </TabsTrigger>
            <TabsTrigger value="settings">
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </TabsTrigger>
          </TabsList>

          <TabsContent value="generate" className="space-y-6">
            {/* Main Content Generation Interface */}
            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold text-white mb-4">Generate Content</h2>
              <p className="text-slate-300 text-lg">Creëer AI-gedreven content voor al je social media platforms</p>
            </div>

            {/* Topic Input */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-6">
                <div className="space-y-4">
                  <Input
                    placeholder="Enter a topic..."
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="bg-slate-700/50 border-yellow-500/50 text-white placeholder-slate-400 text-lg h-14"
                  />
                  <Button 
                    onClick={handleGenerate}
                    disabled={isGenerating || !topic.trim()}
                    className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 h-14 text-lg font-semibold"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        Genereren...
                      </>
                    ) : (
                      'Generate'
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Format Selection */}
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-white">Format</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {formatOptions.map((format) => {
                  const Icon = format.icon;
                  const isSelected = selectedFormats.includes(format.id);
                  return (
                    <Card
                      key={format.id}
                      className={`cursor-pointer transition-all duration-200 ${
                        isSelected 
                          ? 'bg-slate-700/70 border-purple-500 ring-2 ring-purple-500/50' 
                          : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                      }`}
                      onClick={() => handleFormatToggle(format.id)}
                    >
                      <CardContent className="p-6 text-center">
                        <div className={`w-12 h-12 rounded-full ${format.color} flex items-center justify-center mx-auto mb-3`}>
                          <Icon className="w-6 h-6 text-white" />
                        </div>
                        <p className="text-white font-medium">{format.label}</p>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>

            {/* Tone Input */}
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-white">Tone</h3>
              <Input
                placeholder="Enter a tone..."
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="bg-slate-700/50 border-teal-500/50 text-white placeholder-slate-400"
              />
            </div>

            {/* Platform Selection */}
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-white">Platforms</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {Object.entries(platforms).map(([platformId, platform]) => {
                  const Icon = PLATFORM_ICONS[platformId] || FileText;
                  const isSelected = selectedPlatforms.includes(platformId);
                  return (
                    <Card
                      key={platformId}
                      className={`cursor-pointer transition-all duration-200 ${
                        isSelected 
                          ? 'bg-slate-700/70 border-purple-500 ring-2 ring-purple-500/50' 
                          : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                      }`}
                      onClick={() => handlePlatformToggle(platformId)}
                    >
                      <CardContent className="p-4 text-center">
                        <div className={`w-10 h-10 rounded-full bg-gradient-to-r ${PLATFORM_COLORS[platformId]} flex items-center justify-center mx-auto mb-2`}>
                          <Icon className="w-5 h-5 text-white" />
                        </div>
                        <p className="text-white font-medium text-sm">{platform.name}</p>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>

            {/* Selected Options Summary */}
            {(selectedFormats.length > 0 || selectedPlatforms.length > 0) && (
              <Card className="bg-slate-800/30 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white">Selected Options</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {selectedFormats.length > 0 && (
                      <div>
                        <p className="text-slate-300 text-sm mb-2">Formats:</p>
                        <div className="flex flex-wrap gap-2">
                          {selectedFormats.map(format => (
                            <Badge key={format} variant="secondary" className="bg-purple-600/20 text-purple-300">
                              {formatOptions.find(f => f.id === format)?.label}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {selectedPlatforms.length > 0 && (
                      <div>
                        <p className="text-slate-300 text-sm mb-2">Platforms:</p>
                        <div className="flex flex-wrap gap-2">
                          {selectedPlatforms.map(platform => (
                            <Badge key={platform} variant="secondary" className="bg-purple-600/20 text-purple-300">
                              {platforms[platform]?.name || platform}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Status Messages */}
            {isGenerating && (
              <Alert className="border-blue-500/50 bg-blue-500/10">
                <AlertDescription className="text-blue-400">
                  🤖 Generating content... This may take a few seconds.
                </AlertDescription>
              </Alert>
            )}

            {error && (
              <Alert className="border-red-500/50 bg-red-500/10">
                <AlertDescription className="text-red-400">{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="border-green-500/50 bg-green-500/10">
                <AlertDescription className="text-green-400">{success}</AlertDescription>
              </Alert>
            )}

            {/* Generated Content Display */}
            {generatedContent && Array.isArray(generatedContent) && generatedContent.length > 0 && (
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white">Generated Content</CardTitle>
                  <CardDescription className="text-slate-300">
                    Your AI-generated content is ready!
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {Array.isArray(generatedContent) && generatedContent.length > 0 ? (
                      generatedContent.map((content, index) => (
                        <div key={index} className="p-4 bg-slate-700/30 rounded-lg">
                          <div className="flex items-center gap-2 mb-3">
                            <Badge className="bg-purple-600/20 text-purple-300">
                              {content.platform}
                            </Badge>
                            <Badge variant="outline" className="border-slate-600 text-slate-300">
                              {content.content_type}
                            </Badge>
                          </div>
                          <div className="space-y-3">
                            <p className="text-white leading-relaxed">{content.text_content}</p>
                            {content.hashtags && (
                              <p className="text-blue-400 text-sm font-medium">{content.hashtags}</p>
                            )}
                            <div className="flex items-center gap-4 text-xs text-slate-400">
                              <span>Created: {content.created_at ? new Date(content.created_at).toLocaleString() : 'N/A'}</span>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8">
                        <p className="text-slate-400">No content generated yet.</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="schedule">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Schedule Posts</CardTitle>
                <CardDescription className="text-slate-300">
                  Schedule your content for optimal posting times
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-slate-400">Scheduling functionality coming soon...</p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analytics">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Analytics</CardTitle>
                <CardDescription className="text-slate-300">
                  Track your content performance across platforms
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-slate-400">Analytics dashboard coming soon...</p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="settings">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white">Settings</CardTitle>
                <CardDescription className="text-slate-300">
                  Configure your account and preferences
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-slate-400">Settings panel coming soon...</p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default App;

