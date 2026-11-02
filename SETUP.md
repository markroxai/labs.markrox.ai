# One-time setup checklist

## GitHub
- [x] Create repo `markroxai/labs.markrox.ai` (personal account, MIT)
- [ ] `gh auth login`, then `python scripts/bootstrap.py --issues --series ai-eval`
- [ ] Create one Project board for all labs; group by the `series:*` label, then milestone
- [ ] Settings → Pages → Source: GitHub Actions

## labs.markrox.ai
- [ ] DNS: CNAME record `labs` → `markroxai.github.io`
- [ ] Verify markrox.ai under account Settings → Pages → Verified domains
- [ ] Repo Settings → Pages → Custom domain: `labs.markrox.ai`; enable Enforce HTTPS
- [ ] Confirm `docs/CNAME` contains `labs.markrox.ai`

## markrox.ai
- [ ] Add a tag/category per series (e.g. "AI Eval Labs")
- [ ] Each post links to its lab page; each lab page links back to the post

## Slack
- [x] Create `#dsi-ai-labs` (one channel for all series)
- [ ] Set channel description
- [x] Post AI Eval launch message
- [ ] Cross-post short version to #technology-ai
- [ ] Pin the launch post and the labs.markrox.ai link

## Claude
- [ ] One Claude Project per series, with its `series.yaml` and `plan.md` as knowledge
- [ ] Use Claude Code for builds; the Project for scoping and write-ups

## Housekeeping
- [ ] Confirm company policy on work-account output in a public personal repo/blog
