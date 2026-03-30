/**
 * Main entry point for Isolator HA Integration
 * 
 * Exports:
 * - ServiceAccessCard: Main HA custom card (with error boundary + safe loader)
 * - ErrorBoundary: Catches component crashes, prevents HA breakage
 * - SafeLoader: Handles API timeouts, never blocks HA
 * - ServiceAccessEditor: Core editor component
 * - DeployPanel: "Deploy to Pi" button panel (calls HA shell_command)
 * - FleetView: Multi-Pi network dashboard
 * 
 * Safety guarantees:
 * - Single HA instance protection (broken card ≠ broken HA)
 * - Timeout handling (API down ≠ frozen card)
 * - Error isolation (one component crash ≠ all cards broken)
 */

import './error-boundary';
import './safe-loader';
import './service-access-editor';
import './fleet-view';
import './deploy-panel';
import './home-assistant-card';

export { ErrorBoundary } from './error-boundary';
export { SafeLoader } from './safe-loader';
export { ServiceAccessEditor } from './service-access-editor';
export { FleetView } from './fleet-view';
export { DeployPanel } from './deploy-panel';
export { ServiceAccessCard } from './home-assistant-card';
