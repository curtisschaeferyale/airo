WITH values_by_forecast AS (
 SELECT target_variable_id, target_year, COALESCE(ai_scenario_id,'unconditional') AS scenario, percentile, project_participant_group_name AS cohort, value, SUM(weight_within_group) AS w, COUNT(DISTINCT participant_id) AS n
 FROM `mart_eeai.forecast_quantile_standard`
 WHERE policy_id IS NULL AND survey='final-survey-full' AND weight_within_group>0 AND value IS NOT NULL
 GROUP BY 1,2,3,4,5,6
), ranked AS (
 SELECT *, SUM(w) OVER (cell ORDER BY value) AS cumulative, SUM(w) OVER cell AS total
 FROM values_by_forecast WINDOW cell AS (PARTITION BY target_variable_id,target_year,scenario,percentile,cohort)
)
SELECT target_variable_id,target_year,scenario,percentile,cohort,MIN(IF(cumulative>=total/2,value,NULL)) AS weighted_median,SUM(n) AS responses
FROM ranked GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5
