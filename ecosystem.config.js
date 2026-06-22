module.exports = {
  apps: [
    {
      name: 'chem-llm',
      cwd: '/var/www/chem-llm',
      script: 'deploy.sh',
      interpreter: 'bash',
      env: {
        NODE_ENV: 'production',
        PORT: 3001
      }
    }
  ]
};
