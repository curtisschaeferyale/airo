WITH responses AS (
  SELECT target_variable_id, bin_id, project_participant_group_name AS cohort, value, weight_within_group,
         COUNT(DISTINCT participant_id) OVER (
           PARTITION BY target_variable_id, bin_id, project_participant_group_name
         ) AS respondents
  FROM `mart_eeai.forecast_probability_standard`
  WHERE policy_id IS NULL AND survey = 'final-survey-full' AND weight_within_group > 0 AND value IS NOT NULL
    AND target_variable_id IN ('physical_systems', 'reliability', 'ai_progress_scenario')
)
SELECT target_variable_id, bin_id, cohort, value, weight_within_group AS weight, COUNT(*) AS frequency, MAX(respondents) AS respondents,
       COUNT(*) OVER () AS extract_rows
FROM responses GROUP BY 1, 2, 3, 4, 5 ORDER BY 1, 2, 3, 4, 5
