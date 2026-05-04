export enum WorkflowStatus {
  VOID = "VOID",
  LOCKED = "LOCKED",
  DRAFTING = "DRAFTING",
  REVIEWING = "REVIEWING",
  FAILED = "FAILED",
  COMMITTED = "COMMITTED",
  STALE = "STALE",
}

export enum LayoutMode {
  STANDARD = "STANDARD",
  WORKBENCH = "WORKBENCH",
  DOCUMENT = "DOCUMENT",
  SELECTION = "SELECTION",
  FOCUS = "FOCUS",
}

export enum BlockType {
  MARKDOWN = "MARKDOWN",
  CODE = "CODE",
  DATA = "DATA",
  FILE = "FILE",
  CONTAINER = "CONTAINER",
}

export enum ActionType {
  PRIMARY = "primary",
  SECONDARY = "secondary",
  DANGER = "danger",
  ICON = "icon",
}

export enum HITLStepStatus {
  AWAITING_INPUT = "AWAITING_INPUT",
  COMPLETED = "COMPLETED",
  CANCELLED = "CANCELLED",
}
