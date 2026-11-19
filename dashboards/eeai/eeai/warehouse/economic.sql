-- A private distribution of positive survey weights for each dashboard cell.
WITH responses AS (
  SELECT target_variable_id, target_year, COALESCE(ai_scenario_id, 'unconditional') AS scenario,
         percentile, project_participant_group_name AS cohort, value, weight_within_group,
         COUNT(DISTINCT participant_id) OVER (
           PARTITION BY target_variable_id, target_year, COALESCE(ai_scenario_id, 'unconditional'),
                        percentile, project_participant_group_name
         ) AS respondents
  FROM `mart_eeai.forecast_quantile_standard`
  WHERE policy_id IS NULL AND survey = 'final-survey-full' AND weight_within_group > 0 AND value IS NOT NULL
)
SELECT target_variable_id, target_year, scenario, percentile, cohort, value,
       weight_within_group AS weight, COUNT(*) AS frequency, MAX(respondents) AS respondents,
       COUNT(*) OVER () AS extract_rows
FROM responses GROUP BY 1, 2, 3, 4, 5, 6, 7 ORDER BY 1, 2, 3, 4, 5, 6, 7
