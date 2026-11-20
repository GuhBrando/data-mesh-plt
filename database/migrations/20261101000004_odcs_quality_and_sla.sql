-- =============================================================================
-- ODCS library quality rules and structured service levels.
--
-- models.quality[] moves from {dimension, column, operator, threshold,
-- description} to {type, dimension, column, metric, operator, value, unit,
-- valid_values, description}. servicelevels moves from four named strings to
-- {"properties": [{"property", "value", "unit"}]}.
--
-- Every library rule written here runs under datacontract-cli 1.2.9, which
-- refuses unit percent on duplicateValues and breaks on two rules sharing a
-- metric and a column. Anything else becomes a text rule that keeps its old
-- values in description.
--
-- Safe to run twice: rules and rows already in the new format are left alone.
-- Atlas renders this file as a Go template, so it must never contain two
-- opening braces in a row. Atlas manages the transaction; do NOT add explicit
-- BEGIN/COMMIT here.
-- =============================================================================

-- 1. Quality rules. Rows with no quality key are not selected and stay as they are.
WITH contract AS (
    SELECT dc.id,
           CASE jsonb_typeof(dc.models -> 'quality')
               WHEN 'array'  THEN dc.models -> 'quality'
               WHEN 'object' THEN jsonb_build_array(dc.models -> 'quality')
               ELSE '[]'::jsonb
           END AS quality,
           CASE jsonb_typeof(dc.models -> 'fields')
               WHEN 'array' THEN dc.models -> 'fields'
               ELSE '[]'::jsonb
           END AS fields
    FROM catalog.data_contracts dc
    WHERE dc.models ? 'quality'
),
item AS (
    SELECT c.id,
           e.ord,
           e.rule,
           c.fields,
           -- COALESCE: type is NULL on an old rule, and ranked sorts this DESC,
           -- where a NULL would come first and beat a rule already in the new format.
           COALESCE(
               jsonb_typeof(e.rule) = 'object'
                   AND e.rule ->> 'type' IN ('library', 'text')
                   AND e.rule ? 'dimension',
               false
           ) AS is_new,
           CASE jsonb_typeof(e.rule) WHEN 'object' THEN e.rule ELSE '{}'::jsonb END AS old
    FROM contract c
    CROSS JOIN LATERAL jsonb_array_elements(c.quality) WITH ORDINALITY AS e(rule, ord)
),
parsed AS (
    SELECT i.*,
           COALESCE(i.old ->> 'column', '') AS col,
           trim(COALESCE(i.old ->> 'description', '')) AS descr,
           EXISTS (
               SELECT 1
               FROM jsonb_array_elements(i.fields) AS f(field)
               WHERE f.field ->> 'name' = i.old ->> 'column'
           ) AS known_column,
           regexp_match(i.old ->> 'threshold', '^\s*(\d+(?:\.\d+)?)\s*(%?)\s*$') AS m
    FROM item i
),
measured AS (
    SELECT p.*,
           p.m[1]::numeric AS t,
           COALESCE(p.m[2], '') = '%' AS has_percent_sign
    FROM parsed p
),
candidate AS (
    SELECT m.*,
           CASE
               WHEN m.is_new THEN m.old ->> 'metric'
               -- 100 - T only means something for a column the contract declares,
               -- a >= rule and a percentage. A bare 0.99 or 1 may be a fraction, and
               -- 100 - T would turn it into "99% of the rows may be null".
               WHEN m.old ->> 'operator' = '>='
                    AND m.known_column
                    AND m.t BETWEEN 0 AND 100
                    AND (m.has_percent_sign OR m.t = 0 OR m.t > 1)
               THEN CASE
                        WHEN m.old ->> 'dimension' = 'completeness' THEN 'nullValues'
                        WHEN m.old ->> 'dimension' = 'uniqueness' AND m.t = 100
                        THEN 'duplicateValues'
                    END
           END AS metric,
           CASE m.old ->> 'dimension'
               WHEN 'completeness' THEN 'completeness'
               WHEN 'uniqueness'   THEN 'uniqueness'
               WHEN 'freshness'    THEN 'timeliness'
               WHEN 'validity'     THEN 'conformity'
               WHEN 'integrity'    THEN 'consistency'
           END AS dimension
    FROM measured m
),
ranked AS (
    SELECT c.*,
           row_number() OVER (
               PARTITION BY c.id, c.metric, c.col
               ORDER BY c.is_new DESC, c.ord
           ) AS metric_rank
    FROM candidate c
),
converted AS (
    SELECT r.id,
           jsonb_agg(
               CASE
                   WHEN r.is_new THEN r.rule
                   WHEN r.metric IS NOT NULL AND r.metric_rank = 1 THEN jsonb_build_object(
                       'type', 'library',
                       'dimension', r.dimension,
                       'column', r.col,
                       'metric', r.metric,
                       'operator', 'mustBeLessOrEqualTo',
                       'value', CASE r.metric
                                    WHEN 'nullValues' THEN to_jsonb(trim_scale(100 - r.t))
                                    ELSE to_jsonb(0)
                                END,
                       'unit', CASE r.metric WHEN 'nullValues' THEN 'percent' ELSE 'rows' END,
                       'valid_values', '[]'::jsonb,
                       'description', r.descr
                   )
                   ELSE jsonb_build_object(
                       'type', 'text',
                       'dimension', r.dimension,
                       'column', CASE WHEN r.known_column THEN r.col ELSE '' END,
                       'metric', NULL::text,
                       'operator', NULL::text,
                       'value', NULL::numeric,
                       'unit', NULL::text,
                       'valid_values', '[]'::jsonb,
                       'description', concat_ws(
                           ' ',
                           NULLIF(r.descr, ''),
                           CASE
                               WHEN r.old ? 'threshold' THEN format(
                                   '[legacy rule: dimension=%s column=%s operator=%s threshold=%s]',
                                   r.old ->> 'dimension', r.col,
                                   r.old ->> 'operator', r.old ->> 'threshold'
                               )
                               ELSE '[legacy rule: ' || r.rule::text || ']'
                           END
                       )
                   )
               END
               ORDER BY r.ord
           ) AS quality
    FROM ranked r
    GROUP BY r.id
)
UPDATE catalog.data_contracts dc
SET models = jsonb_set(dc.models, '{quality}', COALESCE(cv.quality, '[]'::jsonb))
FROM contract c
LEFT JOIN converted cv ON cv.id = c.id
WHERE dc.id = c.id
  AND dc.models -> 'quality' IS DISTINCT FROM COALESCE(cv.quality, '[]'::jsonb);

-- 2. Service levels. A row holding a properties key is already converted. Empty
--    strings are dropped, so a contract with no levels becomes an empty list.
UPDATE catalog.data_contracts dc
SET servicelevels = jsonb_build_object(
    'properties',
    COALESCE(
        (
            SELECT jsonb_agg(
                CASE
                    WHEN s.m IS NULL THEN jsonb_build_object(
                        'property', s.key, 'value', s.val, 'unit', NULL::text
                    )
                    ELSE jsonb_build_object(
                        'property', s.key,
                        'value', to_jsonb(trim_scale(s.m[1]::numeric)),
                        'unit', CASE s.m[2]
                                    WHEN 'percent' THEN '%'
                                    WHEN 'm' THEN 'min'
                                    ELSE s.m[2]
                                END
                    )
                END
                ORDER BY
                    array_position(
                        ARRAY['freshness', 'availability', 'retention', 'latency'], s.key
                    ) NULLS LAST,
                    s.key
            )
            FROM (
                SELECT kv.key,
                       trim(kv.value) AS val,
                       regexp_match(trim(kv.value), '^(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)?$') AS m
                FROM jsonb_each_text(dc.servicelevels) AS kv
                WHERE COALESCE(trim(kv.value), '') <> ''
            ) AS s
        ),
        '[]'::jsonb
    )
)
WHERE jsonb_typeof(dc.servicelevels) = 'object'
  AND NOT dc.servicelevels ? 'properties';

-- 3. New rows must not start in the old format.
ALTER TABLE catalog.data_contracts
    ALTER COLUMN servicelevels SET DEFAULT '{"properties": []}';
