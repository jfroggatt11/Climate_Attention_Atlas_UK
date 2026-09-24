# Decision log

| Date | Decision | Reason | Revisit when |
| --- | --- | --- | --- |
| 2026-09-23 | Keep GDELT news, Bluesky panel, search and MODIS as separate measures. | Units and denominators are not interchangeable. | Never merge without a documented comparability audit. |
| 2026-09-23 | Use a seed Bluesky panel and label it “posts from monitored Bluesky accounts”. | Public AppView makes a narrow demo possible while avoiding an unsupported national claim. | After T&E reviews account DIDs and panel coverage. |
| 2026-09-23 | Treat all topic phrases as draft test definitions. | Native-speaker and precision/recall review has not happened. | After language and classifier validation. |
| 2026-09-23 | Use country-scale MODIS MOD13C2 NDVI anomaly for first demo. | It is already available and supports physical-context display with baseline metadata. | After separately validated local/land-cover processing. |
| 2026-09-23 | Keep collection, aggregation, Supabase sync and frontend export as separate commands. | A Netlify build must never imply a data refresh. | Preserve this boundary in production scheduling. |
| 2026-09-23 | Use non-GCP deployment with Netlify + Supabase/Postgres. | Matches the pilot architecture constraint and T&E ownership model. | Only with explicit architecture approval. |
| 2026-09-24 | Label every checked-in release as `fixture` and synthetic until live provider captures are approved. | The repository contains generated demonstration values, not a research observation release. | After capped live GDELT, reviewed Bluesky, MODIS and approved context feeds are captured and validated. |
| 2026-09-24 | Define GDELT shares from a hashed per-day captured URL universe and Bluesky shares from the observed post IDs for that day. | Arithmetic and provenance must be checkable before interpreting a denominator. | Revisit when live collectors emit provider-native capture manifests. |
