import "@testing-library/jest-dom";

// jsdom does not implement DragEvent — polyfill it so drag-drop tests work
if (typeof globalThis.DragEvent === "undefined") {
  class DragEvent extends MouseEvent {
    dataTransfer: DataTransfer | null;
    constructor(type: string, init?: DragEventInit) {
      super(type, init);
      this.dataTransfer = init?.dataTransfer ?? null;
    }
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).DragEvent = DragEvent;
}

if (typeof globalThis.DataTransfer === "undefined") {
  class DataTransfer {
    private _data: Record<string, string> = {};
    effectAllowed = "uninitialized";
    dropEffect = "none";
    getData(format: string) { return this._data[format] ?? ""; }
    setData(format: string, data: string) { this._data[format] = data; }
    clearData(format?: string) {
      if (format) delete this._data[format];
      else this._data = {};
    }
    get types() { return Object.keys(this._data); }
    files = [] as unknown as FileList;
    items = [] as unknown as DataTransferItemList;
    setDragImage() {}
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).DataTransfer = DataTransfer;
}
