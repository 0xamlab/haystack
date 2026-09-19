// SPDX-License-Identifier: Apache-2.0
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEVICE_ID_HEADER,
  HOSTNAME_HASH_HEADER,
  resolveClientDeviceHeaders,
} from "./client_device_headers.js";

describe("resolveClientDeviceHeaders", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.ALGENTA_DEVICE_ID;
    delete process.env.DE_DEVICE_ID;
    delete process.env.ALGENTA_RUNTIME_DIR;
    delete process.env.HOSTNAME;
    delete process.env.COMPUTERNAME;
  });

  it("prefers linux machine id over weaker node environment hints", () => {
    const originalPlatform = process.platform;
    const machineIds = ["linux-machine-a\n", "linux-machine-b\n"];
    const fsStub = {
      readFileSync: vi.fn((filePath: string, encoding: "utf8") => {
        expect(encoding).toBe("utf8");
        if (filePath === "/etc/machine-id") {
          return machineIds.shift() ?? "linux-machine-b\n";
        }
        if (filePath === "/var/lib/dbus/machine-id") {
          throw new Error("missing alternate machine id");
        }
        throw new Error(`unexpected read path: ${filePath}`);
      }),
      existsSync: vi.fn(() => false),
      mkdirSync: vi.fn(),
      writeFileSync: vi.fn(),
    };
    const osStub = {
      hostname: vi.fn(() => "node-host-001"),
      homedir: vi.fn(() => "/tmp/algenta-home"),
    };
    const pathStub = {
      join: (...parts: string[]) => parts.join("/"),
    };
    vi.spyOn(process, "getBuiltinModule").mockImplementation(
      ((name: string): unknown => {
        if (name === "node:fs" || name === "fs") {
          return fsStub;
        }
        if (name === "node:os" || name === "os") {
          return osStub;
        }
        if (name === "node:path" || name === "path") {
          return pathStub;
        }
        return undefined;
      }) as typeof process.getBuiltinModule,
    );
    Object.defineProperty(process, "platform", { value: "linux" });

    try {
      const first = resolveClientDeviceHeaders("algenta-ts/1.0.4");
      const second = resolveClientDeviceHeaders("algenta-ts/1.0.4");

      expect(first[DEVICE_ID_HEADER]).toHaveLength(32);
      expect(second[DEVICE_ID_HEADER]).toHaveLength(32);
      expect(first[DEVICE_ID_HEADER]).not.toBe(second[DEVICE_ID_HEADER]);
      expect(first[HOSTNAME_HASH_HEADER]).toBeDefined();
      expect(fsStub.writeFileSync).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(process, "platform", { value: originalPlatform });
    }
  });

  it("persists a node install id when machine identity is unavailable", () => {
    const runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "algenta-ts-device-id-"));
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;

    const fsStub = {
      readFileSync: vi.fn((filePath: string, encoding: "utf8") => {
        if (filePath === "/etc/machine-id" || filePath === "/var/lib/dbus/machine-id") {
          throw new Error("missing machine id");
        }
        return fs.readFileSync(filePath, encoding);
      }),
      existsSync: (filePath: string) => fs.existsSync(filePath),
      mkdirSync: (filePath: string, options?: { recursive?: boolean }) =>
        fs.mkdirSync(filePath, options),
      writeFileSync: (filePath: string, data: string, encoding: "utf8") =>
        fs.writeFileSync(filePath, data, encoding),
    };
    const osStub = {
      hostname: () => "",
      homedir: () => runtimeDir,
    };
    const pathStub = {
      join: (...parts: string[]) => path.join(...parts),
    };
    vi.spyOn(process, "getBuiltinModule").mockImplementation(
      ((name: string): unknown => {
        if (name === "node:fs" || name === "fs") {
          return fsStub;
        }
        if (name === "node:os" || name === "os") {
          return osStub;
        }
        if (name === "node:path" || name === "path") {
          return pathStub;
        }
        return undefined;
      }) as typeof process.getBuiltinModule,
    );

    try {
      const first = resolveClientDeviceHeaders("algenta-ts/1.0.4");
      const second = resolveClientDeviceHeaders("algenta-ts/1.0.4");
      const installIdFile = path.join(runtimeDir, "install_id");

      expect(fs.existsSync(installIdFile)).toBe(true);
      expect(fs.readFileSync(installIdFile, "utf8").trim().length).toBeGreaterThan(0);
      expect(first[DEVICE_ID_HEADER]).toHaveLength(32);
      expect(second[DEVICE_ID_HEADER]).toBe(first[DEVICE_ID_HEADER]);
      expect(first[HOSTNAME_HASH_HEADER]).toBeDefined();
      expect(second[HOSTNAME_HASH_HEADER]).toBe(first[HOSTNAME_HASH_HEADER]);
    } finally {
      fs.rmSync(runtimeDir, { recursive: true, force: true });
    }
  });

  it("keeps a hosted fingerprint when ALGENTA_DEVICE_ID is set", () => {
    process.env.ALGENTA_DEVICE_ID = "ts-device-explicit-0001";
    const fsStub = {
      readFileSync: vi.fn((filePath: string, encoding: "utf8") => {
        expect(encoding).toBe("utf8");
        if (filePath === "/etc/machine-id") {
          return "linux-machine-id\n";
        }
        if (filePath === "/var/lib/dbus/machine-id") {
          throw new Error("missing alternate machine id");
        }
        throw new Error(`unexpected read path: ${filePath}`);
      }),
      existsSync: vi.fn(() => false),
      mkdirSync: vi.fn(),
      writeFileSync: vi.fn(),
    };
    const osStub = {
      hostname: vi.fn(() => "node-host-002"),
      homedir: vi.fn(() => "/tmp/algenta-home"),
    };
    const pathStub = {
      join: (...parts: string[]) => parts.join("/"),
    };
    vi.spyOn(process, "getBuiltinModule").mockImplementation(
      ((name: string): unknown => {
        if (name === "node:fs" || name === "fs") {
          return fsStub;
        }
        if (name === "node:os" || name === "os") {
          return osStub;
        }
        if (name === "node:path" || name === "path") {
          return pathStub;
        }
        return undefined;
      }) as typeof process.getBuiltinModule,
    );

    const headers = resolveClientDeviceHeaders("algenta-ts/1.0.4");

    expect(headers[DEVICE_ID_HEADER]).toBe("ts-device-explicit-0001");
    expect(headers[HOSTNAME_HASH_HEADER]).toBeDefined();
  });
});
