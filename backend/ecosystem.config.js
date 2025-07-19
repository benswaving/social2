module.exports = {
  apps: [{
    name: 'ai-social-creator-backend',
    script: 'src/main.py',
    interpreter: './venv/bin/python',
    cwd: '/var/www/ai-social-creator/backend',
    instances: 1,
    exec_mode: 'fork',
    
    // Environment
    env: {
      FLASK_ENV: 'production',
      PYTHONPATH: '/var/www/ai-social-creator/backend/src'
    },
    
    // Logging
    log_file: '/var/log/ai-social-creator/combined.log',
    out_file: '/var/log/ai-social-creator/out.log',
    error_file: '/var/log/ai-social-creator/error.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    
    // Process management
    restart_delay: 4000,
    max_restarts: 10,
    min_uptime: '10s',
    
    // Monitoring
    watch: false,
    ignore_watch: ['node_modules', 'logs', '*.log'],
    
    // Memory management
    max_memory_restart: '500M',
    
    // Graceful shutdown
    kill_timeout: 5000,
    
    // Health check
    health_check_grace_period: 3000
  }]
};

