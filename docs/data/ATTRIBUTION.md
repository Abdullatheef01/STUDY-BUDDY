# Data Attribution — Skills Taxonomy

## `data/taxonomy/skills_taxonomy.json`

**Source:** Curated in-house by the STUDY-BUDDY team.

**How it was built:**
1. Started from `data/skills_db.csv` (306 skills, in-house curated list).
2. `scripts/build_skills_taxonomy.py` enriches every skill with:
   - auto-generated spelling variants (dot/space/hyphen/compact forms,
     e.g. `reactjs`, `react.js`, `react js` for React),
   - hand-written alias/hierarchy enrichment for ~70 high-traffic skills
     (frameworks, cloud services, DSA topics, Indian-market tools such as
     Postman, Figma, Tally).
3. Reproducible — re-run the script to regenerate the JSON.

**Not sourced from ESCO or O*NET.** The roadmap (ENG-06) suggested building
from ESCO (CC BY 4.0) and O*NET (CC BY 4.0); we chose an in-house curated
taxonomy instead to keep the dataset small, focused on the Indian student /
developer job market, and free of attribution/licensing complexity. If we
adopt ESCO/O*NET concepts in the future, attribution will be added here and
in the app footer per their CC BY 4.0 requirements.

## `data/skills_db.csv`

In-house curated skill list (306 skills). No third-party source.

## License of this data

The taxonomy JSON and CSV are part of the STUDY-BUDDY repository and are
released under the repository's MIT license, consistent with their
in-house origin.

## See also

- `docs/data/sources.md` — every external API/feed with ToS links, rate
  limits, and review dates (LEG-02).
