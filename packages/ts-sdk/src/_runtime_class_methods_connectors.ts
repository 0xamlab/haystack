/** Auto-split sub-module of runtime.ts — managed-connector and repository
 * delegation wrappers for the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type {
  ConnectorBrowseResult,
  ConnectorInfo,
  ConnectorListResult,
  ConnectorTestInfo,
  DatasetConnectResult,
  DatasetDeleteResult,
  DatasetDetailResult,
  DatasetListResult,
  DatasetSummaryResult,
  DecisionEnvelope,
  RepositoryApplyRequest,
  RepositoryApplyResponse,
  RepositoryDecisionPlanCreateRequest,
  RepositoryDecisionPlanRevisionResponse,
  RepositoryGraphQueryRequest,
  RepositoryGraphQueryResponse,
  RepositoryIntelligenceCapabilitiesResponse,
  RepositorySimulationRequest,
  RepositorySnapshotCreateRequest,
  RepositorySnapshotResponse,
  RepositoryTriageRequest,
  RepositoryTriageResponse,
} from "./types.js";
import { Runtime } from "./_runtime_class.js";

declare module "./_runtime_class.js" {
  interface Runtime {
    createConnector(request: {
      name: string;
      connectorType: string;
      config?: Record<string, unknown>;
      description?: string;
      visibility?: string;
    }): Promise<ConnectorInfo>;
    listConnectors(options?: { page?: number; limit?: number }): Promise<ConnectorListResult>;
    getConnector(connectorId: string): Promise<ConnectorInfo>;
    updateConnector(
      connectorId: string,
      request: {
        name?: string;
        description?: string;
        visibility?: string;
        config?: Record<string, unknown>;
      },
    ): Promise<ConnectorInfo>;
    testConnector(
      connectorIdOrConnector: string | Record<string, unknown>,
    ): Promise<ConnectorTestInfo>;
    browseConnector(
      connectorIdOrConnector: string | Record<string, unknown>,
    ): Promise<ConnectorBrowseResult>;
    deleteConnector(connectorId: string): Promise<void>;
    createRepositorySnapshot(
      repositoryId: string,
      request: RepositorySnapshotCreateRequest,
    ): Promise<RepositorySnapshotResponse>;
    getRepositoryIntelligenceCapabilities(): Promise<RepositoryIntelligenceCapabilitiesResponse>;
    getRepositorySnapshot(
      repositoryId: string,
      snapshotId: string,
    ): Promise<RepositorySnapshotResponse>;
    triageRepository(
      repositoryId: string,
      request: RepositoryTriageRequest,
    ): Promise<RepositoryTriageResponse>;
    createRepositoryDecisionPlan(
      repositoryId: string,
      request: RepositoryDecisionPlanCreateRequest,
    ): Promise<RepositoryDecisionPlanRevisionResponse>;
    queryRepositoryGraph(
      repositoryId: string,
      request: RepositoryGraphQueryRequest,
    ): Promise<RepositoryGraphQueryResponse>;
    simulateRepository(
      repositoryId: string,
      request: RepositorySimulationRequest,
    ): Promise<DecisionEnvelope>;
    applyRepository(
      repositoryId: string,
      request: RepositoryApplyRequest,
    ): Promise<RepositoryApplyResponse>;
    listDatasets(options?: {
      page?: number;
      limit?: number;
      search?: string;
      status?: string;
      sourceName?: string;
      compact?: boolean;
    }): Promise<DatasetListResult>;
    getDataset(datasetId: string): Promise<DatasetDetailResult>;
    getDatasetSummary(datasetId: string): Promise<DatasetSummaryResult>;
    refreshDataset(datasetId: string): Promise<DatasetConnectResult>;
    deleteDataset(datasetId: string): Promise<DatasetDeleteResult>;
  }
}

Runtime.prototype.createConnector = async function (
  this: Runtime,
  request: {
    name: string;
    connectorType: string;
    config?: Record<string, unknown>;
    description?: string;
    visibility?: string;
  },
): Promise<ConnectorInfo> {
  this.requireApiTransport("createConnector");
  return this.client().createConnector({
    name: request.name,
    connector_type: request.connectorType,
    config: request.config,
    description: request.description,
    visibility: request.visibility,
  });
};

Runtime.prototype.listConnectors = async function (
  this: Runtime,
  options: { page?: number; limit?: number } = {},
): Promise<ConnectorListResult> {
  this.requireApiTransport("listConnectors");
  return this.client().listConnectors(options);
};

Runtime.prototype.getConnector = async function (
  this: Runtime,
  connectorId: string,
): Promise<ConnectorInfo> {
  this.requireApiTransport("getConnector");
  return this.client().getConnector(connectorId);
};

Runtime.prototype.updateConnector = async function (
  this: Runtime,
  connectorId: string,
  request: {
    name?: string;
    description?: string;
    visibility?: string;
    config?: Record<string, unknown>;
  },
): Promise<ConnectorInfo> {
  this.requireApiTransport("updateConnector");
  return this.client().updateConnector(connectorId, {
    name: request.name,
    description: request.description,
    visibility: request.visibility,
    config: request.config,
  });
};

Runtime.prototype.testConnector = async function (
  this: Runtime,
  connectorIdOrConnector: string | Record<string, unknown>,
): Promise<ConnectorTestInfo> {
  this.requireApiTransport("testConnector");
  if (typeof connectorIdOrConnector === "string") {
    return this.client().testConnector(connectorIdOrConnector);
  }
  return this.client().previewTestConnector(
    this.normalizePreviewConnectorPayload(connectorIdOrConnector),
  );
};

Runtime.prototype.browseConnector = async function (
  this: Runtime,
  connectorIdOrConnector: string | Record<string, unknown>,
): Promise<ConnectorBrowseResult> {
  this.requireApiTransport("browseConnector");
  if (typeof connectorIdOrConnector === "string") {
    return this.client().browseConnector(connectorIdOrConnector);
  }
  return this.client().previewBrowseConnector(
    this.normalizePreviewConnectorPayload(connectorIdOrConnector),
  );
};

Runtime.prototype.deleteConnector = async function (
  this: Runtime,
  connectorId: string,
): Promise<void> {
  this.requireApiTransport("deleteConnector");
  await this.client().deleteConnector(connectorId);
};

Runtime.prototype.createRepositorySnapshot = async function (
  this: Runtime,
  repositoryId: string,
  request: RepositorySnapshotCreateRequest,
): Promise<RepositorySnapshotResponse> {
  this.requireApiTransport("createRepositorySnapshot");
  return this.client().createRepositorySnapshot(repositoryId, request);
};

Runtime.prototype.getRepositoryIntelligenceCapabilities = async function (
  this: Runtime,
): Promise<RepositoryIntelligenceCapabilitiesResponse> {
  this.requireApiTransport("getRepositoryIntelligenceCapabilities");
  return this.client().getRepositoryIntelligenceCapabilities();
};

Runtime.prototype.getRepositorySnapshot = async function (
  this: Runtime,
  repositoryId: string,
  snapshotId: string,
): Promise<RepositorySnapshotResponse> {
  this.requireApiTransport("getRepositorySnapshot");
  return this.client().getRepositorySnapshot(repositoryId, snapshotId);
};

Runtime.prototype.triageRepository = async function (
  this: Runtime,
  repositoryId: string,
  request: RepositoryTriageRequest,
): Promise<RepositoryTriageResponse> {
  this.requireApiTransport("triageRepository");
  return this.client().triageRepository(repositoryId, request);
};

Runtime.prototype.createRepositoryDecisionPlan = async function (
  this: Runtime,
  repositoryId: string,
  request: RepositoryDecisionPlanCreateRequest,
): Promise<RepositoryDecisionPlanRevisionResponse> {
  this.requireApiTransport("createRepositoryDecisionPlan");
  return this.client().createRepositoryDecisionPlan(repositoryId, request);
};

Runtime.prototype.queryRepositoryGraph = async function (
  this: Runtime,
  repositoryId: string,
  request: RepositoryGraphQueryRequest,
): Promise<RepositoryGraphQueryResponse> {
  this.requireApiTransport("queryRepositoryGraph");
  return this.client().queryRepositoryGraph(repositoryId, request);
};

Runtime.prototype.simulateRepository = async function (
  this: Runtime,
  repositoryId: string,
  request: RepositorySimulationRequest,
): Promise<DecisionEnvelope> {
  this.requireApiTransport("simulateRepository");
  return this.client().simulateRepository(repositoryId, request);
};

Runtime.prototype.applyRepository = async function (
  this: Runtime,
  repositoryId: string,
  request: RepositoryApplyRequest,
): Promise<RepositoryApplyResponse> {
  this.requireApiTransport("applyRepository");
  return this.client().applyRepository(repositoryId, request);
};

Runtime.prototype.listDatasets = async function (
  this: Runtime,
  options: {
    page?: number;
    limit?: number;
    search?: string;
    status?: string;
    sourceName?: string;
    compact?: boolean;
  } = {},
): Promise<DatasetListResult> {
  this.requireApiTransport("listDatasets");
  return this.client().listDatasets(options);
};

Runtime.prototype.getDataset = async function (
  this: Runtime,
  datasetId: string,
): Promise<DatasetDetailResult> {
  this.requireApiTransport("getDataset");
  return this.client().getDataset(datasetId);
};

Runtime.prototype.getDatasetSummary = async function (
  this: Runtime,
  datasetId: string,
): Promise<DatasetSummaryResult> {
  this.requireApiTransport("getDatasetSummary");
  return this.client().getDatasetSummary(datasetId);
};

Runtime.prototype.refreshDataset = async function (
  this: Runtime,
  datasetId: string,
): Promise<DatasetConnectResult> {
  this.requireApiTransport("refreshDataset");
  return this.client().refreshDataset(datasetId);
};

Runtime.prototype.deleteDataset = async function (
  this: Runtime,
  datasetId: string,
): Promise<DatasetDeleteResult> {
  this.requireApiTransport("deleteDataset");
  return this.client().deleteDataset(datasetId);
};
