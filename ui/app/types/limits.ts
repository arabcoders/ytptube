export type SystemLimitsExtractor = {
  name: string;
  limit: number;
  source: string;
  active: number;
  queued: number;
  available: number;
};

export type SystemLimitsResponse = {
  downloads: {
    paused: boolean;
    live_bypasses_limits: boolean;
    global: {
      limit: number;
      active: number;
      available: number;
      live_active: number;
      queued: number;
    };
    per_extractor: {
      default_limit: number;
      items: SystemLimitsExtractor[];
    };
  };
  extraction: {
    concurrency: number;
    timeout_seconds: number;
    info_cache_ttl_seconds: number;
  };
  live: {
    prevent_premiere: boolean;
    premiere_buffer_minutes: number;
  };
};
