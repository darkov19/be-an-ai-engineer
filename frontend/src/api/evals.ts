export interface EvalRun {
  id: number;
  run_timestamp: string;
  prompt_version: string;
  extraction_schema_version: string;
  overall_accuracy: number | string;
  overall_precision: number | string;
  overall_recall: number | string;
  overall_f1: number | string;
  accuracy_regression: boolean;
  metrics: {
    field_metrics: Record<string, { precision: number; recall: number; f1: number }>;
    num_samples: number;
    prior_f1: number | null;
    split: string;
  };
  created_at: string;
}

export interface DetailedDiff {
  eval_id: string;
  expected: Record<string, any>;
  actual: Record<string, any> | null;
  matching_status: Record<string, boolean>;
  mismatched_fields: string[];
  metrics: Record<string, { precision: number; recall: number; f1: number }>;
  overall_f1: number;
  extraction_error: string | null;
}

export interface EvalLatestSummary {
  run_id: number;
  run_timestamp: string;
  prompt_version: string;
  schema_version: string;
  split: string;
  overall_metrics: {
    precision: number;
    recall: number;
    f1: number;
  };
  accuracy_regression: boolean;
  field_metrics: Record<string, { precision: number; recall: number; f1: number }>;
  detailed_diffs: DetailedDiff[];
}

export async function fetchEvalsHistory(): Promise<EvalRun[]> {
  const response = await fetch('/api/v1/evals');
  if (!response.ok) {
    throw new Error('Failed to fetch evaluation history');
  }
  const payload = await response.json();
  return payload.data;
}

export async function fetchLatestEvalSummary(): Promise<EvalLatestSummary> {
  const response = await fetch('/api/v1/evals/latest');
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('SUMMARY_NOT_FOUND');
    }
    throw new Error('Failed to fetch latest evaluation summary');
  }
  const payload = await response.json();
  return payload.data;
}

export interface RunEvalParams {
  split: string;
  prompt_version: string;
  dry_run?: boolean;
}

export async function runEvaluationApi(params: RunEvalParams): Promise<{ task_id: string }> {
  const response = await fetch('/api/v1/evals/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    throw new Error('Failed to start evaluation run');
  }
  return response.json();
}
