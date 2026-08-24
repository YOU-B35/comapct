/**
 * Shared SSH connection wrapper with retry logic and timeout handling
 * Usage:
 *   const ssh = require('./lib/deploy-ssh');
 *   const conn = await ssh.connect();
 *   const output = await ssh.exec(conn, 'ls -la');
 *   await ssh.sftp(conn).fastPut(local, remote);
 *   conn.end();
 */

const fs = require('fs');
const path = require('path');
const { Client } = require('ssh2');

/**
 * Get SSH connection config from env or defaults
 * ENV: SSH_HOST, SSH_USER, SSH_KEY, SSH_TIMEOUT (ms)
 */
function getSSHConfig() {
  const host = process.env.SSH_HOST || '124.223.27.98';
  const user = process.env.SSH_USER || 'root';
  const keyPath = process.env.SSH_KEY ||
    path.join(process.env.USERPROFILE || process.env.HOME || '/root', '.ssh/lhkp-o3wazsuv');
  const timeout = parseInt(process.env.SSH_TIMEOUT || '60000', 10);

  if (!fs.existsSync(keyPath)) {
    throw new Error(`SSH key not found at: ${keyPath}\n` +
      `Set SSH_KEY env var to override. Example: set SSH_KEY=C:\\path\\to\\key`);
  }

  const stat = fs.statSync(keyPath);
  const mode = (stat.mode & parseInt('777', 8)).toString(8);
  if (mode !== '600' && mode !== '400') {
    console.warn(`[WARN] SSH key permissions should be 0600, got 0${mode}. ` +
      `This may cause ssh2 to reject it. Run: chmod 600 ${keyPath}`);
  }

  return {
    host,
    port: 22,
    username: user,
    privateKey: fs.readFileSync(keyPath),
    readyTimeout: timeout,
  };
}

/**
 * Connect with retry logic
 * maxRetries: number of connection attempts
 * backoffMs: initial backoff (doubles each retry)
 */
async function connect(maxRetries = 3, backoffMs = 2000) {
  const config = getSSHConfig();
  console.log(`[SSH] Connecting to ${config.username}@${config.host}:${config.port} ` +
    `(timeout=${config.readyTimeout}ms, retries=${maxRetries})`);

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const conn = new Client();
      return await new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          conn.end();
          reject(new Error(`Connection timeout after ${config.readyTimeout}ms`));
        }, config.readyTimeout + 5000);

        conn
          .on('ready', () => {
            clearTimeout(timer);
            resolve(conn);
          })
          .on('error', reject)
          .connect(config);
      });
    } catch (err) {
      if (attempt === maxRetries) {
        throw new Error(`SSH connection failed after ${maxRetries} attempts: ${err.message}`);
      }
      const delay = backoffMs * Math.pow(2, attempt - 1);
      console.log(`[SSH] Attempt ${attempt}/${maxRetries} failed, retrying in ${delay}ms: ${err.message}`);
      await new Promise(r => setTimeout(r, delay));
    }
  }
}

/**
 * Execute remote command
 * Returns stdout + stderr combined
 */
async function exec(conn, cmd) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err);
      let out = '';
      stream.on('data', (d) => (out += d.toString()));
      stream.stderr.on('data', (d) => (out += d.toString()));
      stream.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Exit code ${code}:\n${out}`));
        } else {
          resolve(out);
        }
      });
    });
  });
}

/**
 * Get SFTP handle
 */
async function sftp(conn) {
  return new Promise((resolve, reject) => {
    conn.sftp((err, sftp) => {
      if (err) reject(err);
      else resolve(sftp);
    });
  });
}

/**
 * Upload file with retry
 */
async function put(conn, localPath, remotePath, maxRetries = 2) {
  if (!fs.existsSync(localPath)) {
    throw new Error(`Local file not found: ${localPath}`);
  }

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const s = await sftp(conn);
      return await new Promise((resolve, reject) => {
        s.fastPut(localPath, remotePath, { mode: 0o644 }, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });
    } catch (err) {
      if (attempt === maxRetries) throw err;
      console.log(`[SFTP] Upload attempt ${attempt}/${maxRetries} failed, retrying: ${err.message}`);
      await new Promise(r => setTimeout(r, 1000 * attempt));
    }
  }
}

/**
 * Download file with retry
 */
async function get(conn, remotePath, localPath, maxRetries = 2) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const s = await sftp(conn);
      return await new Promise((resolve, reject) => {
        s.fastGet(remotePath, localPath, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });
    } catch (err) {
      if (attempt === maxRetries) throw err;
      console.log(`[SFTP] Download attempt ${attempt}/${maxRetries} failed, retrying: ${err.message}`);
      await new Promise(r => setTimeout(r, 1000 * attempt));
    }
  }
}

module.exports = { getSSHConfig, connect, exec, sftp, put, get };
