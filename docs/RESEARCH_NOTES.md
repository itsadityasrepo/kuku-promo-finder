# Research notes (what I could verify without watching video)

## How microdrama apps actually advertise
- **DramaBox, US, Jul–Aug 2026 (AdMapix, third-party estimates):** the top 10 ads are 7 unique videos. Lengths are 46–116 s (seven at 46–64 s). **One creative took ~75% of the top-10 impressions.** The leading ad is a chain of beats ending in a **"cut before resolution"**, holding its secret back for a "delayed confrontation". https://www.admapix.com/blog/ad-intelligence/dramabox-ad-strategy-2026
  - What this means for the tool: (1) "cut before the answer" is confirmed as *the* pattern. (2) Spend piles onto one winner, so the job is to give the first test wave **several genuinely different moments** and let the data pick, not to perfect one ranking. That's why the post list caps one clip per story moment. (3) Real ads often run past 60 s; the brief's 20–60 s is stricter, and I follow the brief.
- **ReelShort (Insightrackr):** 89% of creatives are video. The example ad opens straight into the action with no caption and builds suspense through repeated questions. https://blog.insightrackr.com/en/docs/ReelShort-Mobile-Advertising-Intelligence-Analysis
- **Business model (Trends.vc):** free episodes first, then coin unlocks per episode; marketing can be up to ~90% of a title's budget. https://trends.vc/short-drama-apps-hook-funnels-ai-production-cliffhanger-pricing/
- **Not found in public sources:** where the ad tap lands (Ep 1 or the advertised episode) and the paywall position for this show. So "post premise clips first" stays a **hypothesis**, and the tool offers both strategies (`--strategy funnel` / `--strategy peak`) for an A/B test.

## Prices (checked against a third-party summary dated 2026-10-25; verify before quoting)
https://www.morphllm.com/gemini-api-pricing
- gemini-2.5-flash: $0.30 in / $2.50 out per 1M tokens · gemini-2.5-flash-lite: $0.10 / $0.40 · gemini-4-argon (frontier): $2.00 / $10.00.
- Free tier covers 2.5-flash and 2.5-flash-lite among others. **Google uses free-tier content to improve its products**, so free tier is fine for this demo but not for Kuku's unreleased scripts.

## Ad policy categories the flags map to (keyword screens, not policy decisions)
- Meta Advertising Standards: *Violent and Graphic Content*, *Adult Content*. https://transparency.meta.com/policies/ad-standards/objectionable-content/violent-graphic-content
- TikTok Ads: *Violence and Dangerous Activities*. https://ads.tiktok.com/help/article/tiktok-ads-policy-violence-and-dangerous-activities
