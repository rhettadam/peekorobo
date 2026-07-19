/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_SEARCH_BASE_URL?: string;
  readonly VITE_ASSETS_BASE_URL?: string;
  readonly VITE_CURRENT_YEAR?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
