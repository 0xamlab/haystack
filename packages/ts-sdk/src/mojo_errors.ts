export class MojoRuntimeError extends Error {
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = new.target.name;
    this.code = code;
    this.details = details;
  }
}

export class MojoRuntimeConfigurationError extends MojoRuntimeError {}

export class MojoModuleNotRegisteredError extends MojoRuntimeError {}

export class MojoFunctionNotRegisteredError extends MojoRuntimeError {}

export class MojoExecutionError extends MojoRuntimeError {}
