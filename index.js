#!/usr/bin/env node

/**
 * Claude Global Skills - Main Entry Point
 * Provides graceful shutdown with 5-second grace period
 */

import { EventEmitter } from 'events';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

class Application extends EventEmitter {
  constructor() {
    super();
    this.isShuttingDown = false;
    this.gracePeriodMs = 5000; // 5 second grace period
    this.activeConnections = new Set();
  }

  /**
   * Initialize the application
   */
  async initialize() {
    console.log('[App] Initializing Claude Global Skills...');
    // Application setup logic would go here
    this.emit('initialized');
  }

  /**
   * Register an active connection/resource
   */
  registerConnection(resource) {
    this.activeConnections.add(resource);
  }

  /**
   * Unregister a connection/resource
   */
  unregisterConnection(resource) {
    this.activeConnections.delete(resource);
  }

  /**
   * Graceful shutdown handler
   */
  async gracefulShutdown(signal) {
    if (this.isShuttingDown) {
      console.log(`[App] Shutdown already in progress, received ${signal}`);
      return;
    }

    this.isShuttingDown = true;
    console.log(`[App] Received ${signal}, starting graceful shutdown...`);

    // Start grace period timeout
    const graceTimer = setTimeout(() => {
      console.error(`[App] Grace period (${this.gracePeriodMs}ms) exceeded, forcing shutdown`);
      this.forceShutdown();
    }, this.gracePeriodMs);

    try {
      // Close active connections
      await this.closeConnections();

      // Emit shutdown event for other components
      this.emit('shutdown');

      // Clean up
      clearTimeout(graceTimer);
      console.log('[App] Graceful shutdown completed successfully');
      process.exit(0);
    } catch (error) {
      clearTimeout(graceTimer);
      console.error('[App] Error during graceful shutdown:', error);
      this.forceShutdown();
    }
  }

  /**
   * Close all active connections
   */
  async closeConnections() {
    if (this.activeConnections.size === 0) {
      console.log('[App] No active connections to close');
      return;
    }

    console.log(`[App] Closing ${this.activeConnections.size} active connection(s)...`);

    const closePromises = Array.from(this.activeConnections).map((connection) => {
      return Promise.resolve()
        .then(() => {
          if (typeof connection.close === 'function') {
            return connection.close();
          } else if (typeof connection.end === 'function') {
            return connection.end();
          } else if (typeof connection.destroy === 'function') {
            return connection.destroy();
          }
        })
        .catch((error) => {
          console.error('[App] Error closing connection:', error.message);
        });
    });

    await Promise.all(closePromises);
    console.log('[App] All connections closed');
  }

  /**
   * Force immediate shutdown
   */
  forceShutdown() {
    console.error('[App] Force shutdown initiated');
    process.exit(1);
  }

  /**
   * Setup signal handlers
   */
  setupSignalHandlers() {
    // SIGTERM - termination signal (graceful)
    process.on('SIGTERM', () => {
      this.gracefulShutdown('SIGTERM');
    });

    // SIGINT - interrupt signal (Ctrl+C)
    process.on('SIGINT', () => {
      this.gracefulShutdown('SIGINT');
    });

    // Handle uncaught exceptions
    process.on('uncaughtException', (error) => {
      console.error('[App] Uncaught exception:', error);
      this.gracefulShutdown('uncaughtException');
    });

    // Handle unhandled promise rejections
    process.on('unhandledRejection', (reason, promise) => {
      console.error('[App] Unhandled rejection at promise:', promise, 'reason:', reason);
      this.gracefulShutdown('unhandledRejection');
    });
  }
}

/**
 * Main entry point
 */
async function main() {
  const app = new Application();

  // Setup signal handlers
  app.setupSignalHandlers();

  try {
    // Initialize application
    await app.initialize();

    // Application is ready
    console.log('[App] Claude Global Skills is ready');
    console.log('[App] Grace period for shutdown: 5 seconds');
    console.log('[App] Use Ctrl+C or send SIGTERM to shutdown gracefully');
  } catch (error) {
    console.error('[App] Failed to initialize:', error);
    process.exit(1);
  }
}

// Only run if this is the main module
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error('[App] Fatal error:', error);
    process.exit(1);
  });
}

export default Application;
export { Application };
