# ATS Keyword Gap Analysis

## Viral Shastri Resume vs. Kogneos Backend Engineer JD

---

## Keyword Match Summary

| JD Keyword                 | In Current Resume | Action                                                                   |
| -------------------------- | ----------------- | ------------------------------------------------------------------------ |
| Node.js                    | ✓ Present         | Keep — add "Node.js" explicitly to skills section top                    |
| Python                     | ✓ Present         | Strong — already prominent                                               |
| Flask                      | ✓ Present         | Good                                                                     |
| React.js                   | ✗ Missing         | Add to skills as "working knowledge" (you have freelance exposure)       |
| Next.js                    | ✗ Missing         | Add to skills as "working knowledge"                                     |
| Microservices              | ✓ Present         | Good                                                                     |
| Serverless                 | ✗ Missing         | Add — GAE IS serverless, this is accurate. Use the word explicitly       |
| Event-driven architecture  | ✓ Present         | Good                                                                     |
| PostgreSQL                 | ✓ Present         | Good                                                                     |
| MySQL                      | ✗ Missing         | Skip — don't claim what you haven't used                                 |
| NoSQL                      | ✗ Missing         | Add — Redis IS NoSQL. Add "NoSQL" to skills section                      |
| Firestore                  | ✗ Missing         | Skip — don't claim                                                       |
| Docker                     | ✗ Missing         | Add ONLY if you've used Docker even minimally                            |
| CloudRun                   | ✗ Missing         | Skip — don't claim                                                       |
| GitHub Actions             | ✓ Present         | Good                                                                     |
| CI/CD                      | ✓ Present         | Good                                                                     |
| Git                        | ✓ Present         | Good                                                                     |
| Agile                      | ✓ Present         | Good                                                                     |
| AWS                        | ✗ Missing         | Skip — don't claim. GCP is your cloud                                    |
| Scalable backend services  | ✓ Implied         | Make explicit — use phrase "scalable backend services"                   |
| API design                 | ✗ Missing         | Add "RESTful API design" to skills                                       |
| Containerized environments | ✗ Missing         | Add only if Docker experience exists                                     |
| Concurrency                | ✗ Missing         | Hyper-Y handles concurrent requests — mention if you address concurrency |
| Database optimization      | ✗ Missing         | If you've optimized PostgreSQL queries, mention it                       |

---

## Priority Fixes (High Impact, Quick)

### 1. Add to Skills Section (accurate, adds keywords)

```
Serverless (GAE is serverless — 100% accurate)
NoSQL (Redis is NoSQL — 100% accurate)
RESTful API Design (you built 8 TMS adapters — 100% accurate)
React.js, Next.js (working knowledge — honest framing)
```

### 2. Use These Exact JD Phrases in Your Resume

The ATS searches for their exact terminology. Mirror these:

- "scalable backend services" → use in summary or bullet
- "event-driven workflows" → already present, keep
- "microservices" → already present, keep
- "CI/CD" → already present, keep
- "cross-functional" → already present, keep

### 3. Bullets to Add/Strengthen

Current gap: No explicit mention of **database optimization** or **concurrency handling**.
Hyper-Y handles both — if you've optimized PostgreSQL queries or handled concurrent requests, add one bullet like:

> "Optimized PostgreSQL queries and Redis caching layer to maintain sub-[X]ms response times at 100+ req/sec concurrent load"

---

## Estimated ATS Match Score

**Before fixes:** ~62% (borderline — some recruiters may miss you)
**After fixes:** ~78% (comfortably past threshold)

Key improvement: Adding "serverless", "NoSQL", "RESTful API", "React.js", "Next.js" closes the biggest keyword gaps without fabricating any experience.

---

## What NOT to Add (Honesty Rules)

Do not add these even though they're in the JD:

- Docker (unless you've actually used it)
- CloudRun (you use GAE, not CloudRun)
- AWS (you use GCP)
- Firestore (you use PostgreSQL + Redis)
- MySQL (you use PostgreSQL)

Fabricating stack experience gets exposed in the technical interview. Don't do it.

---

## Final Checklist Before Submitting to Kogneos

- [ ] Add "Serverless" to skills (accurate — GAE is serverless)
- [ ] Add "NoSQL" to skills (accurate — Redis is NoSQL)
- [ ] Add "RESTful API Design" to skills
- [ ] Add "React.js, Next.js (working knowledge)" to skills
- [ ] Check: do you use Docker? If yes, add it
- [ ] Ensure "Node.js" appears in skills section prominently
- [ ] Use phrase "scalable backend services" somewhere in summary or bullets
- [ ] Add university names to education section
- [ ] Run plain-text test: paste resume into Notepad, verify nothing scrambles
- [ ] Filename: Viral_Shastri_Resume_BackendEngineer.pdf
