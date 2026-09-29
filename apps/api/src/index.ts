import { buildApp } from './app.js';

const app = buildApp();

const start = async () => {
  try {
    await app.listen({ port: 3000, host: '0.0.0.0' });
    console.log('Server listening on http://0.0.0.0:3000');
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
};

start();
