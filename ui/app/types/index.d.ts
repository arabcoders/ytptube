type ImportedItem = {
  _type: string;
  _version: string;
};

type version_check = {
  app: {
    status: 'up_to_date' | 'update_available' | 'error';
    current_version: string;
    new_version: string;
  };
  ytdlp: {
    status: 'up_to_date' | 'update_available' | 'error';
    current_version: string;
    new_version: string;
  };
};

type TerminalSessionStatus = 'starting' | 'running' | 'completed' | 'interrupted' | 'failed';

type TerminalSessionItem = {
  session_id: string;
  command: string;
  status: TerminalSessionStatus;
  created_at: number | null;
  started_at: number | null;
  finished_at: number | null;
  expires_at: number | null;
  available_until: number | null;
  exit_code: number | null;
  last_sequence: number;
};

type TerminalSessionsResponse = {
  items: Array<TerminalSessionItem>;
};

export {
  ImportedItem,
  TerminalSessionItem,
  TerminalSessionStatus,
  TerminalSessionsResponse,
  version_check,
};
