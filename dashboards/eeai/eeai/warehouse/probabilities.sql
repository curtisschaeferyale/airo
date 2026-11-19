SELECT target_variable_id, bin_id, project_participant_group_name AS cohort,
 SUM(value * weight_within_group) / SUM(weight_within_group) AS weighted_mean,
 COUNT(DISTINCT participant_id) AS responses
FROM `mart_eeai.forecast_probability_standard`
WHERE policy_id IS NULL AND survey='final-survey-full' AND weight_within_group>0 AND value IS NOT NULL
 AND target_variable_id IN ('physical_systems','reliability','ai_progress_scenario')
GROUP BY 1,2,3 ORDER BY 1,2,3
