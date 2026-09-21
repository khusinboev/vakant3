/**
 * Whether the currently open article/tip/category editor has unsaved changes.
 * A module-level flag rather than lifted React state: `ContentPage`'s
 * Articles/Tips/Categories sub-tab switch needs to ask "is it safe to unmount
 * the active tab right now?" without threading a callback through three
 * layers (`ContentPage` -> `<X>Tab` -> `<X>Editor`) for a single boolean that
 * only ever has one reader at a time (only one editor can be open at once).
 */
let dirty = false;

export function setContentDirty(value: boolean): void {
  dirty = value;
}

export function isContentDirty(): boolean {
  return dirty;
}
